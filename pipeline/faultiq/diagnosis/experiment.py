"""Phase 4 diagnosis experiment over the processed LBNL data (ADR 0022).

Same splits as Phase 3, so no test hour is ever seen in training:
- simulated: train on days 0-59, choose the model and the confidence cut-off on days 61-80, test
  on days 82-99,
- ORNL: four folds, each season tested once, tuned on the next season, trained on the other two.

Two views of the test hours:
- main: every diagnosable hour whose fault could show (and every diagnosable normal hour). This
  measures the diagnoser alone.
- end to end: only the hours Phase 3's normal-behaviour detector alarmed on, as a user would see
  them. Here the diagnoser can also dismiss a false alarm by answering "no supported fault".
"""

from __future__ import annotations

import logging
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
    SEASONS,
    SIM_BLOCKS,
    SIM_START,
    WINDOW,
    WINDOW_KEYS,
    season_fold,
    sim_split,
    window_table,
)
from faultiq.diagnosis.classify import (
    ADOPT_MARGIN,
    INCONCLUSIVE,
    MIN_NAMED,
    TARGET_PRECISION,
    Classifier,
    decide,
    matrix,
    tune_cutoff,
)
from faultiq.diagnosis.evaluate import (
    answers,
    by_severity,
    calibration_error,
    confusion,
    evidence,
    macro_f1,
    per_class,
)
from faultiq.diagnosis.features import (
    NORMAL,
    POINT_SETS,
    feature_columns,
    is_diagnosable,
    window_features,
)

DIAGNOSIS_VERSION = "0.1.0"
FAMILIES = ("logistic", "lightgbm")
NOT_DIAGNOSABLE = "not_diagnosable"
log = logging.getLogger("faultiq.diagnosis")

# Train hours (main view only), then every validation and test hour of the fold.
Fold = tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]


def fit_normal_models(normal: pl.DataFrame, config: dict[str, Any]) -> dict[str, d.NormalModel]:
    return {
        ps: d.NormalModel(list(config[ps]["inputs"]), list(config[ps]["targets"])).fit(normal)
        for ps in POINT_SETS
    }


def build_windows(
    minutes: pl.DataFrame,
    dataset: str,
    models: dict[str, d.NormalModel],
    rules: d.EconomizerRules | None,
) -> pl.DataFrame:
    """Window table with labels, diagnosis features and the Phase 3 detector score per point set."""
    w = window_table(minutes).join(
        window_features(minutes, dataset, models, rules), on=WINDOW_KEYS, how="left"
    )
    for ps, model in models.items():
        ws = d.window_scores(minutes, model.score(minutes), WINDOW_KEYS)
        w = w.join(
            ws.select(*WINDOW_KEYS, pl.col("score").alias(f"detect:{ps}")),
            on=WINDOW_KEYS,
            how="left",
        )
    diagnosable = is_diagnosable().fill_null(False)
    return w.with_columns(
        diagnosable=diagnosable,
        # Main view: a faulty hour counts only if its fault could show (Phase 3 observability).
        in_main=diagnosable & (~pl.col("is_fault") | (pl.col("n_observable") >= MIN_MINUTES)),
    )


def crossfit_windows(
    groups: list[pl.DataFrame],
    dataset: str,
    config: dict[str, Any],
    rules: d.EconomizerRules | None,
) -> pl.DataFrame:
    """Fault-free training windows scored out of fold: each group by models fit on the others.

    Without this, the classifier learns "normal" from hours the normal model was fitted on, whose
    residuals are near zero. New normal hours never look that clean, so it would call them faults.
    """
    out = []
    for i, part in enumerate(groups):
        others = pl.concat([g for j, g in enumerate(groups) if j != i], how="diagonal_relaxed")
        out.append(build_windows(part, dataset, fit_normal_models(others, config), rules))
    return pl.concat(out, how="diagonal_relaxed")


def _labels(*frames: pl.DataFrame) -> list[str]:
    faults = sorted({f for fr in frames for f in fr["fault"].unique().to_list()} - {NORMAL})
    return [NORMAL, *faults]


def _top(proba: np.ndarray, classes: np.ndarray) -> np.ndarray:
    return np.asarray(classes[proba.argmax(axis=1)]) if len(proba) else np.array([])


def _assess(folds_in: list[Fold], cols: list[str], point_set: str) -> dict[str, Any]:
    """Fit both candidates per fold, adopt one on validation, then score the test hours."""
    fitted: dict[str, list[tuple[Classifier, np.ndarray, np.ndarray]]] = {f: [] for f in FAMILIES}
    folds = [(tr, va, te, va.filter(pl.col("in_main"))) for tr, va, te in folds_in]
    for train, _, test, val in folds:
        x, y = matrix(train, cols), train["fault"].to_numpy()
        for fam in FAMILIES:
            clf = Classifier(fam, cols).fit(x, y)
            fitted[fam].append((clf, clf.proba(matrix(val, cols)), clf.proba(matrix(test, cols))))

    labels = _labels(*(f for fold in folds_in for f in fold))
    val_truth = np.concatenate([v["fault"].to_numpy() for *_, v in folds])
    main_masks = [t["in_main"].to_numpy() for _, _, t, _ in folds]
    test_truth = np.concatenate(
        [t["fault"].to_numpy()[m] for (_, _, t, _), m in zip(folds, main_masks, strict=True)]
    )

    def pooled(fam: str, test: bool) -> np.ndarray:
        preds = []
        for i, (clf, pv, pt) in enumerate(fitted[fam]):
            p = _top(pt if test else pv, clf.classes)
            preds.append(p[main_masks[i]] if test else p)
        return np.concatenate(preds)

    val_f1 = {f: macro_f1(val_truth, pooled(f, test=False), labels) for f in FAMILIES}
    test_f1 = {f: macro_f1(test_truth, pooled(f, test=True), labels) for f in FAMILIES}
    chosen = "lightgbm" if val_f1["lightgbm"] >= val_f1["logistic"] + ADOPT_MARGIN else "logistic"

    scored_parts, cutoffs = [], []
    for (_, val_all, test, val), (clf, pv, pt) in zip(folds, fitted[chosen], strict=True):
        cutoff = tune_cutoff(pv, val["fault"].to_numpy(), clf.classes)
        cutoffs.append(cutoff)
        answer = decide(pt, clf.classes, cutoff)
        # Phase 3's alarm threshold, re-derived exactly as Phase 3 did (same hours, same budget).
        val_eval = val_all.filter(pl.col("evaluable"))
        threshold, _ = tune_threshold(val_eval[f"detect:{point_set}"], val_eval["is_fault"])
        scored_parts.append(
            test.with_columns(
                predicted=pl.Series(_top(pt, clf.classes), dtype=pl.Utf8),
                confidence=pl.Series(pt.max(axis=1) if len(pt) else [], dtype=pl.Float64),
                answer=pl.Series(answer, dtype=pl.Utf8),
                top_feature=pl.Series(clf.top_feature(matrix(test, cols), pt), dtype=pl.Utf8),
                alarm=predict(test[f"detect:{point_set}"], threshold) & test["evaluable"],
            ).with_columns(
                answer=pl.when(pl.col("diagnosable"))
                .then(pl.col("answer"))
                .otherwise(pl.lit(NOT_DIAGNOSABLE))
            )
        )
    scored = pl.concat(scored_parts, how="diagonal_relaxed")
    main = scored.filter(pl.col("in_main"))
    m_truth, m_pred = main["fault"].to_numpy(), main["predicted"].to_numpy()
    m_proba_parts = [pt[m] for (_, _, pt), m in zip(fitted[chosen], main_masks, strict=True)]
    classes = fitted[chosen][0][0].classes
    return {
        "adopted": chosen,
        "validation_macro_f1": val_f1,
        "test_macro_f1": test_f1,
        "confidence_cutoffs": [None if not np.isfinite(c) else round(c, 4) for c in cutoffs],
        "main": {
            "per_class": per_class(m_truth, m_pred, labels),
            "confusion": confusion(m_truth, m_pred, labels),
            "calibration_error": calibration_error(np.concatenate(m_proba_parts), m_truth, classes),
            "answers": answers(m_truth, main["answer"].to_numpy()),
            "by_severity": by_severity(main),
            "evidence": evidence(main),
        },
        "end_to_end": end_to_end(scored),
        "coverage": coverage(scored),
    }


def end_to_end(scored: pl.DataFrame) -> dict[str, Any]:
    """What happened to each hour the Phase 3 detector alarmed on."""
    flagged = scored.filter(pl.col("alarm"))
    outcome = (
        pl.when(pl.col("answer") == NOT_DIAGNOSABLE).then(pl.lit(NOT_DIAGNOSABLE))
        .when(pl.col("answer") == INCONCLUSIVE).then(pl.lit(INCONCLUSIVE))
        .when(pl.col("answer") == pl.col("fault")).then(
            pl.when(pl.col("is_fault")).then(pl.lit("correct_fault")).otherwise(pl.lit("said_no_fault"))
        )
        .when(pl.col("answer") == NORMAL).then(pl.lit("said_no_fault"))
        .otherwise(pl.lit("named_a_fault"))
    )  # fmt: skip
    out: dict[str, Any] = {}
    for name, part in (("faulty_alarms", flagged.filter(pl.col("is_fault"))),
                       ("false_alarms", flagged.filter(~pl.col("is_fault")))):  # fmt: skip
        counts = part.select(outcome.alias("o"))["o"].value_counts()
        out[name] = {
            "windows": part.height,
            **{
                str(r["o"]): round(r["count"] / part.height, 4) for r in counts.sort("o").to_dicts()
            },
        }
    return out


def coverage(scored: pl.DataFrame) -> list[dict[str, Any]]:
    """Per class: test hours, and the share that entered the main view."""
    return (
        scored.group_by("fault")
        .agg(
            pl.len().alias("test_windows"),
            pl.col("in_main").sum().alias("main_windows"),
            pl.col("diagnosable").mean().alias("diagnosable_share"),
        )
        .sort("fault")
        .to_dicts()
    )


def run_simulated(processed: Path) -> dict[str, Any]:
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "simulated" and e["output"]
    ]
    baseline = next(e for e in entries if e["label"]["fault"] == NORMAL)
    normal = _load(processed, baseline).filter(sim_split(pl.col("window_start")) == "train")
    models = fit_normal_models(normal, d.SIM_MODEL)
    tables = []
    for e in entries:
        log.info("featurising", extra={"file": e["source_file"]})
        w = build_windows(_load(processed, e), "simulated", models, None)
        if e is baseline:  # its training hours are replaced by out-of-fold ones below
            w = w.filter(sim_split(pl.col("window_start")) != "train")
        tables.append(w)
    day = (pl.col("window_start") - pl.lit(SIM_START)).dt.total_days()
    half = SIM_BLOCKS["train"][1] // 2
    halves = [normal.filter(day < half), normal.filter(day >= half)]
    tables.append(crossfit_windows(halves, "simulated", d.SIM_MODEL, None))
    windows = pl.concat(tables, how="diagonal_relaxed").with_columns(
        split=sim_split(pl.col("window_start"))
    )
    train = windows.filter((pl.col("split") == "train") & pl.col("in_main"))
    val = windows.filter(pl.col("split") == "val")
    test = windows.filter(pl.col("split") == "test")
    out: dict[str, Any] = {}
    for ps in POINT_SETS:
        cols = feature_columns("simulated", ps)
        # Validation for the classifier is the main view; the detector threshold uses `evaluable`.
        out[ps] = _assess([(train, val, test)], cols, ps)
    out["windows"] = {
        s: int(windows.filter((pl.col("split") == s) & pl.col("in_main")).height)
        for s in SIM_BLOCKS
    }
    return out


def run_experimental(processed: Path) -> dict[str, Any]:
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "experimental" and e["output"]
    ]
    by_season: dict[str, list[dict[str, Any]]] = {s: [] for s in SEASONS}
    for e in entries:
        by_season[e["label"]["season"]].append(e)

    folds: dict[str, list[Fold]] = {ps: [] for ps in POINT_SETS}
    for test_season in SEASONS:
        roles = season_fold(test_season)
        normal_by_season = [
            pl.concat(
                [_load(processed, e) for e in by_season[s] if e["label"]["fault"] == NORMAL],
                how="diagonal_relaxed",
            )
            for s, r in roles.items()
            if r == "train"
        ]
        models = fit_normal_models(pl.concat(normal_by_season, how="diagonal_relaxed"), d.EXP_MODEL)
        rules = d.EconomizerRules("all")
        by_role: dict[str, list[pl.DataFrame]] = {"train": [], "val": [], "test": []}
        for season, role in roles.items():
            for e in by_season[season]:
                if role == "train" and e["label"]["fault"] == NORMAL:
                    continue  # replaced by out-of-fold windows below
                by_role[role].append(
                    build_windows(_load(processed, e), "experimental", models, rules)
                )
        by_role["train"].append(
            crossfit_windows(normal_by_season, "experimental", d.EXP_MODEL, rules)
        )
        train, val, test = (pl.concat(by_role[r], how="diagonal_relaxed") for r in by_role)
        log.info("fold ready", extra={"test_season": test_season, "train_windows": train.height})
        for ps in POINT_SETS:
            folds[ps].append((train.filter(pl.col("in_main")), val, test))
    out: dict[str, Any] = {}
    for ps in POINT_SETS:
        out[ps] = _assess(folds[ps], feature_columns("experimental", ps), ps)
        out[ps]["confidence_cutoffs"] = dict(
            zip(SEASONS, out[ps]["confidence_cutoffs"], strict=True)
        )
    return out


def run(processed: Path) -> dict[str, Any]:
    return {
        "diagnosis_version": DIAGNOSIS_VERSION,
        "pipeline_version": faultiq.PIPELINE_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
        "window": WINDOW,
        "min_minutes": MIN_MINUTES,
        "target_named_fault_precision": TARGET_PRECISION,
        "min_named_validation_windows": MIN_NAMED,
        "adopt_margin": ADOPT_MARGIN,
        "simulated": run_simulated(processed),
        "experimental": run_experimental(processed),
    }
