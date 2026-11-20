"""The bounded diagnostic workflow (ADR 0023): six fixed steps, no open-ended agent.

1. Validate input: the minutes must come from the Phase 2 pipeline (grid, modes, features).
2. Inspect operating context: steady and diagnosable minutes per hour.
3. Detect: Phase 3 normal-model score against its frozen threshold.
4. Diagnose: Phase 4 classifier with its frozen confidence cut-off.
5. Collect evidence: top signals per event, with expected values where a baseline applies.
6. Explain: template statements, then the claim checker. A result that fails is never emitted.

`Diagnoser` holds everything learned from training data, so explaining a new file never looks at
its label. Labels are used only to train and to evaluate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

import faultiq
from faultiq.detection import detectors as d
from faultiq.detection.evaluate import predict, tune_threshold
from faultiq.detection.experiment import _load, _manifest
from faultiq.detection.windows import (
    MIN_MINUTES,
    SIM_BLOCKS,
    SIM_START,
    add_minute_context,
    season_fold,
    sim_split,
)
from faultiq.diagnosis.classify import INCONCLUSIVE, Classifier, decide, matrix, tune_cutoff
from faultiq.diagnosis.experiment import (
    DIAGNOSIS_VERSION,
    NOT_DIAGNOSABLE,
    build_windows,
    crossfit_windows,
    fit_normal_models,
)
from faultiq.diagnosis.features import (
    EXP_FEATURES,
    NORMAL,
    SIM_FEATURES,
    diagnosable_expr,
    feature_columns,
)
from faultiq.explain import evidence as ev
from faultiq.explain.check import ExplanationError, check_result
from faultiq.explain.library import FaultLibrary, fault_library
from faultiq.explain.narrate import statements
from faultiq.explain.schema import Alternative, DiagnosticResult, FaultEvent, ModelOutput

# Model family per dataset, as adopted on validation data in ADR 0022 (frozen with diagnosis 0.1.0).
ADOPTED = {"simulated": "lightgbm", "experimental": "logistic"}
RUNNING = {"simulated": "compressor", "experimental": "supply fan"}
TOP_ALTERNATIVES = 3
REQUIRED_COLUMNS = ("timestamp", "steady", "operating_mode", "fan_on", "compressor_on")


@dataclass
class Diagnoser:
    """Everything learned from training data for one dataset and point set, frozen."""

    dataset: str
    point_set: str
    models: dict[str, d.NormalModel]
    rules: d.EconomizerRules | None
    classifier: Classifier
    cutoff: float
    detector_threshold: float
    ranges: ev.NormalRanges
    precision: dict[str, float] = field(default_factory=dict)

    @property
    def columns(self) -> list[str]:
        return feature_columns(self.dataset, self.point_set)

    @property
    def residual_model(self) -> dict[str, str]:
        specs = SIM_FEATURES if self.dataset == "simulated" else EXP_FEATURES
        return {t: ps for ps, t in specs[self.point_set].residuals}

    @property
    def supported_faults(self) -> list[str]:
        return [str(c) for c in self.classifier.classes if c != NORMAL]


def _finish(
    dataset: str,
    point_set: str,
    models: dict[str, d.NormalModel],
    rules: d.EconomizerRules | None,
    train: pl.DataFrame,
    val: pl.DataFrame,
) -> Diagnoser:
    """Fit the adopted classifier, its cut-off, the detector threshold and normal ranges."""
    cols = feature_columns(dataset, point_set)
    train = train.filter(pl.col("in_main"))
    clf = Classifier(ADOPTED[dataset], cols).fit(matrix(train, cols), train["fault"].to_numpy())
    val_main = val.filter(pl.col("in_main"))
    pv = clf.proba(matrix(val_main, cols))
    truth = val_main["fault"].to_numpy()
    cutoff = tune_cutoff(pv, truth, clf.classes)
    answers = decide(pv, clf.classes, cutoff)
    precision = {
        str(c): round(float((truth[answers == c] == c).mean()), 4)
        for c in clf.classes
        if c != NORMAL and (answers == c).sum() >= 10
    }
    val_eval = val.filter(pl.col("evaluable"))
    threshold, _ = tune_threshold(val_eval[f"detect:{point_set}"], val_eval["is_fault"])
    # Normal ranges come from fault-free validation hours: scored by the same models used at
    # inference and never seen in training (training normals are cross-fitted by other models).
    normal_val = val_main.filter(pl.col("fault") == NORMAL)
    return Diagnoser(
        dataset, point_set, models, rules, clf, cutoff, threshold,
        ev.normal_ranges(normal_val, cols), precision,
    )  # fmt: skip


def fit_simulated(processed: Path, point_set: str = "all") -> Diagnoser:
    """Train on days 0-59, tune on days 61-80 (ADR 0022 splits)."""
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "simulated" and e["output"]
    ]
    base = next(e for e in entries if e["label"]["fault"] == NORMAL)
    normal = _load(processed, base).filter(sim_split(pl.col("window_start")) == "train")
    models = fit_normal_models(normal, d.SIM_MODEL)
    tables = []
    for e in entries:
        w = build_windows(_load(processed, e), "simulated", models, None)
        tables.append(w.filter(sim_split(pl.col("window_start")) != "train") if e is base else w)
    day = (pl.col("window_start") - pl.lit(SIM_START)).dt.total_days()
    half = SIM_BLOCKS["train"][1] // 2
    halves = [normal.filter(day < half), normal.filter(day >= half)]
    tables.append(crossfit_windows(halves, "simulated", d.SIM_MODEL, None))
    w = pl.concat(tables, how="diagonal_relaxed").with_columns(
        split=sim_split(pl.col("window_start"))
    )
    split = pl.col("split")
    return _finish(
        "simulated", point_set, models, None, w.filter(split == "train"), w.filter(split == "val")
    )


def fit_experimental(processed: Path, test_season: str, point_set: str = "all") -> Diagnoser:
    """The ORNL fold that holds `test_season` out (ADR 0022 splits), for evaluation."""
    return fit_experimental_roles(processed, season_fold(test_season), point_set)


def fit_experimental_roles(
    processed: Path, roles: dict[str, str], point_set: str = "all"
) -> Diagnoser:
    """ORNL diagnoser for any season roles. A production model has no test season: three
    seasons train and one validates (ADR 0024)."""
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "experimental" and e["output"]
    ]
    train_seasons = [s for s, r in roles.items() if r == "train"]
    normal_by_season = [
        pl.concat(
            [
                _load(processed, e)
                for e in entries
                if e["label"]["season"] == s and e["label"]["fault"] == NORMAL
            ],
            how="diagonal_relaxed",
        )
        for s in train_seasons
    ]
    models = fit_normal_models(pl.concat(normal_by_season, how="diagonal_relaxed"), d.EXP_MODEL)
    rules = d.EconomizerRules("all")
    train: list[pl.DataFrame] = []
    val: list[pl.DataFrame] = []
    for e in entries:
        role = roles[e["label"]["season"]]
        if role == "test" or (role == "train" and e["label"]["fault"] == NORMAL):
            continue
        w = build_windows(_load(processed, e), "experimental", models, rules)
        (train if role == "train" else val).append(w)
    train.append(crossfit_windows(normal_by_season, "experimental", d.EXP_MODEL, rules))
    return _finish(
        "experimental", point_set, models, rules,
        pl.concat(train, how="diagonal_relaxed"), pl.concat(val, how="diagonal_relaxed"),
    )  # fmt: skip


def as_recorded(t: datetime | None) -> datetime | None:
    """Source timestamps carry no time zone, and point mappings don't declare one yet. They are
    kept exactly as recorded and marked UTC, so every consumer reads the same wall-clock numbers
    (a naive time would be shifted by each reader's local zone). ADR 0025."""
    return None if t is None else t.replace(tzinfo=UTC) if t.tzinfo is None else t


def unlabelled(source: str) -> dict[str, object]:
    """Minute context for explaining a file: the label is unknown by design."""
    return {"source_name": source, "fault": "unknown", "intensity": None, "season": None}


def score_hours(
    minutes: pl.DataFrame, diag: Diagnoser
) -> tuple[pl.DataFrame, np.ndarray, np.ndarray]:
    """Steps 2-4: hourly context, detector alarm and diagnosis answer, plus contributions and
    class probabilities."""
    hours = build_windows(minutes, diag.dataset, diag.models, diag.rules).sort("window_start")
    cols = diag.columns
    x = matrix(hours, cols)
    proba = diag.classifier.proba(x)
    contrib = diag.classifier.contributions(x, proba)
    classes = diag.classifier.classes
    top = classes[proba.argmax(axis=1)] if len(proba) else np.array([])
    hours = hours.with_columns(
        top_class=pl.Series(top, dtype=pl.Utf8),
        confidence=pl.Series(proba.max(axis=1) if len(proba) else [], dtype=pl.Float64),
        answer=pl.Series(decide(proba, classes, diag.cutoff), dtype=pl.Utf8),
        scored=pl.col("n_steady") >= MIN_MINUTES,
    ).with_columns(
        answer=pl.when(pl.col("diagnosable")).then("answer").otherwise(pl.lit(NOT_DIAGNOSABLE)),
        alarm=predict(hours[f"detect:{diag.point_set}"], diag.detector_threshold)
        & pl.col("scored"),
    )
    return hours, contrib, proba


def _kind(answer: str) -> str:
    if answer == NORMAL:
        return "no_supported_fault"
    if answer in (INCONCLUSIVE, NOT_DIAGNOSABLE):
        return answer
    return "fault"


def _event(
    n: int,
    rows: list[int],
    answer: str,
    hours: pl.DataFrame,
    contrib: np.ndarray,
    proba: np.ndarray,
    minutes: pl.DataFrame,
    diag: Diagnoser,
    library: FaultLibrary,
) -> FaultEvent:
    eh = hours[rows]
    kind = _kind(answer)
    fault = answer if kind == "fault" else None
    in_event = pl.col("window_start").is_in(eh["window_start"].to_list())
    em = minutes.filter(in_event)
    diagnosable = em.select(diagnosable_expr(diag.dataset).alias("_d"))["_d"]
    steady = em["steady"].fill_null(False)

    top_class = answer if kind == "fault" else eh["top_class"].mode().sort().first()
    conf = eh.filter(pl.col("top_class") == top_class)["confidence"].median()
    if kind in ("fault", "inconclusive"):
        evidence = ev.diagnosis_evidence(
            eh, contrib[rows], diag.columns, em, diagnosable,
            diag.models, diag.residual_model, diag.ranges,
        )  # fmt: skip
    else:
        evidence = ev.detector_evidence(em, steady, diag.models[diag.point_set], diag.ranges)
    alternatives: list[Alternative] = []
    if kind != "not_diagnosable" and len(proba):
        # Mean probability of every class over the event's hours: the "possible alternatives".
        mean = proba[rows].mean(axis=0)
        alternatives = [
            Alternative(fault=str(diag.classifier.classes[i]), probability=round(float(mean[i]), 4))
            for i in np.argsort(-mean)[:TOP_ALTERNATIVES]
        ]
    model = ModelOutput(
        alternatives=alternatives,
        answer=answer if kind == "fault" else kind,
        top_class=None if kind == "not_diagnosable" else str(top_class),
        confidence=None if kind == "not_diagnosable" else round(float(conf or 0.0), 4),  # type: ignore[arg-type]
        cutoff=None if not np.isfinite(diag.cutoff) else round(diag.cutoff, 4),
        validation_precision=diag.precision.get(answer) if kind == "fault" else None,
        detector_score=round(float(eh[f"detect:{diag.point_set}"].max() or 0.0), 4),  # type: ignore[arg-type]
        detector_threshold=round(diag.detector_threshold, 4),
        model_family=diag.classifier.family,
    )
    ctx = ev.context(em, diagnosable, RUNNING[diag.dataset])
    start = as_recorded(eh["window_start"].min())  # type: ignore[arg-type]
    end = as_recorded(eh["window_start"].max() + ev.HOUR)  # type: ignore[operator,arg-type]
    return FaultEvent(
        id=f"event-{n}", start=start, end=end, hours=eh.height, kind=kind,
        fault=fault, fault_title=library.title(fault) if fault else None,
        model=model, context=ctx, evidence=evidence,
        checks=list(library.faults[fault].checks) if fault else [],
        statements=statements(kind, fault, start, end, eh.height, model, ctx, evidence, library),
    )  # fmt: skip


def explain(
    minutes: pl.DataFrame, diag: Diagnoser, source: str, library: FaultLibrary | None = None
) -> DiagnosticResult:
    """Run the workflow on one processed file and return a checked result."""
    return analyse_file(minutes, diag, source, library)[0]


def analyse_file(
    minutes: pl.DataFrame, diag: Diagnoser, source: str, library: FaultLibrary | None = None
) -> tuple[DiagnosticResult, pl.DataFrame]:
    """The workflow, plus its hour-by-hour table (context, features, alarm, answer), which the
    chart series reuse so the timelines show exactly what the workflow decided."""
    missing = [c for c in REQUIRED_COLUMNS if c not in minutes.columns]
    if missing:  # step 1: only Phase 2 output is accepted
        raise ValueError(f"{source}: not a processed file, missing {missing}")
    library = library or fault_library()
    minutes = add_minute_context(minutes, unlabelled(source))
    hours, contrib, proba = score_hours(minutes, diag)
    groups = ev.group_events(hours)
    events = [
        _event(i + 1, g.rows, g.answer, hours, contrib, proba, minutes, diag, library)
        for i, g in enumerate(groups)
    ]
    cited = sorted({c.source for e in events for c in e.checks})
    result = DiagnosticResult(
        pipeline_version=faultiq.PIPELINE_VERSION,
        diagnosis_version=DIAGNOSIS_VERSION,
        source=source,
        dataset=diag.dataset,
        point_set=diag.point_set,
        period_start=as_recorded(minutes["timestamp"].min()),  # type: ignore[arg-type]
        period_end=as_recorded(minutes["timestamp"].max()),  # type: ignore[arg-type]
        hours_total=hours.height,
        hours_scored=int(hours["scored"].sum()),
        hours_alarmed=int(hours["alarm"].sum()),
        supported_faults=diag.supported_faults,
        library_review_status=library.review_status,
        events=events,
        sources=[library.sources[s] for s in cited],
    )
    problems = check_result(result, library)
    if problems:  # step 6: fail closed
        raise ExplanationError("; ".join(problems[:5]))
    return result, hours


def as_json(result: DiagnosticResult) -> dict[str, Any]:
    return result.model_dump(mode="json")
