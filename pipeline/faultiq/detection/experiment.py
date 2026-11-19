"""Phase 3 detection experiment over the processed LBNL data (ADR 0021).

Simulated set: detectors learn from the fault-free file's training days only, the threshold is
tuned on the validation days, and results come from the test days (shared by all files, so no test
hour ever overlaps training). Experimental (ORNL) set: four folds; each season is tested once, with
the threshold tuned on the next season and the detectors trained on the other two.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Protocol

import polars as pl

import faultiq
from faultiq.detection import detectors as d
from faultiq.detection.evaluate import (
    MAX_FALSE_ALARM_RATE,
    auc,
    breakdown,
    confusion,
    coverage,
    predict,
    tune_threshold,
)
from faultiq.detection.windows import (
    MIN_MINUTES,
    SEASONS,
    SIM_BLOCKS,
    WINDOW,
    WINDOW_KEYS,
    add_minute_context,
    season_fold,
    sim_split,
    window_table,
)

DETECTION_VERSION = "0.1.0"
log = logging.getLogger("faultiq.detection")


class Detector(Protocol):
    name: str

    def fit(self, normal: pl.DataFrame) -> Any: ...
    def score(self, df: pl.DataFrame) -> pl.DataFrame: ...


@dataclass(frozen=True)
class Spec:
    family: str
    point_set: str
    make: Callable[[], Detector]

    @property
    def key(self) -> str:
        return f"{self.family}/{self.point_set}"


def _sim_limits(point_set: str) -> Detector:
    return d.LimitRules(list(d.SIM_LIMIT_SIGNALS[point_set]))


def _sim_model(point_set: str) -> Detector:
    cfg = d.SIM_MODEL[point_set]
    return d.NormalModel(list(cfg["inputs"]), list(cfg["targets"]))


def _exp_rules(point_set: str) -> Detector:
    return d.EconomizerRules(point_set)


def _exp_model(point_set: str) -> Detector:
    cfg = d.EXP_MODEL[point_set]
    return d.NormalModel(list(cfg["inputs"]), list(cfg["targets"]))


def sim_specs() -> list[Spec]:
    return [
        spec
        for ps in ("basic", "all")
        for spec in (
            Spec("limit_rules", ps, partial(_sim_limits, ps)),
            Spec("normal_model", ps, partial(_sim_model, ps)),
        )
    ]


def exp_specs() -> list[Spec]:
    return [
        spec
        for ps in ("basic", "all")
        for spec in (
            Spec("economizer_rules", ps, partial(_exp_rules, ps)),
            Spec("normal_model", ps, partial(_exp_model, ps)),
        )
    ]


def _manifest(processed: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = json.loads((processed / "manifest.json").read_text())["files"]
    return files


def _load(processed: Path, entry: dict[str, Any]) -> pl.DataFrame:
    return add_minute_context(pl.read_parquet(processed / entry["output"]), entry["label"])


def _score_file(minutes: pl.DataFrame, fitted: dict[str, Detector]) -> pl.DataFrame:
    """Window table for one file, with one score and explanation column pair per detector."""
    windows = window_table(minutes)
    for key, det in fitted.items():
        ws = d.window_scores(minutes, det.score(minutes), WINDOW_KEYS).rename(
            {"score": f"score:{key}", "top_signal": f"top:{key}"}
        )
        windows = windows.join(ws, on=WINDOW_KEYS, how="left")
    return windows


def _evaluate(
    val: pl.DataFrame, test: pl.DataFrame, key: str
) -> tuple[float, dict[str, Any], pl.DataFrame]:
    v = val.filter(pl.col("evaluable"))
    threshold, val_metrics = tune_threshold(v[f"score:{key}"], v["is_fault"])
    t = test.filter(pl.col("evaluable"))
    t = t.with_columns(
        alarm=predict(t[f"score:{key}"], threshold),
        score=pl.col(f"score:{key}"),
        top_signal=pl.col(f"top:{key}"),
    )
    return threshold, val_metrics.to_dict(), t


def run_simulated(processed: Path) -> dict[str, Any]:
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "simulated" and e["output"]
    ]
    baseline = next(e for e in entries if e["label"]["fault"] == "fault_free")
    normal = _load(processed, baseline).filter(sim_split(pl.col("window_start")) == "train")
    fitted = {s.key: s.make().fit(normal) for s in sim_specs()}

    tables = []
    for e in entries:
        log.info("scoring", extra={"file": e["source_file"]})
        tables.append(_score_file(_load(processed, e), fitted))
    windows = pl.concat(tables, how="diagonal_relaxed").with_columns(
        split=sim_split(pl.col("window_start"))
    )

    out: dict[str, Any] = {
        "coverage": coverage(windows.filter(pl.col("split") == "test")),
        "detectors": {},
    }
    for spec in sim_specs():
        key = spec.key
        val = windows.filter(pl.col("split") == "val")
        test = windows.filter(pl.col("split") == "test")
        threshold, val_metrics, scored = _evaluate(val, test, key)
        out["detectors"][key] = {
            "threshold": round(threshold, 4),
            "validation": val_metrics,
            "test": {
                **confusion(scored["is_fault"], scored["alarm"]).to_dict(),
                "auc": auc(scored[f"score:{key}"], scored["is_fault"]),
            },
            **breakdown(scored),
        }
    out["windows"] = {
        split: {
            "evaluable": int(
                windows.filter((pl.col("split") == split) & pl.col("evaluable")).height
            )
        }
        for split in SIM_BLOCKS
    }
    return out


def run_experimental(processed: Path) -> dict[str, Any]:
    entries = [
        e for e in _manifest(processed) if e["label"]["dataset"] == "experimental" and e["output"]
    ]
    by_season: dict[str, list[dict[str, Any]]] = {s: [] for s in SEASONS}
    for e in entries:
        by_season[e["label"]["season"]].append(e)

    tested: dict[str, list[pl.DataFrame]] = {s.key: [] for s in exp_specs()}
    thresholds: dict[str, dict[str, float]] = {s.key: {} for s in exp_specs()}
    all_test_windows = []
    for test_season in SEASONS:
        roles = season_fold(test_season)
        train_seasons = [s for s, r in roles.items() if r == "train"]
        normal = pl.concat(
            [
                _load(processed, e)
                for s in train_seasons
                for e in by_season[s]
                if e["label"]["fault"] == "fault_free"
            ],
            how="diagonal_relaxed",
        )
        fitted = {s.key: s.make().fit(normal) for s in exp_specs()}
        scored = {}
        for role in ("val", "test"):
            season = next(s for s, r in roles.items() if r == role)
            scored[role] = pl.concat(
                [_score_file(_load(processed, e), fitted) for e in by_season[season]],
                how="diagonal_relaxed",
            )
        all_test_windows.append(scored["test"])
        for spec in exp_specs():
            threshold, _, t = _evaluate(scored["val"], scored["test"], spec.key)
            thresholds[spec.key][test_season] = round(threshold, 4)
            tested[spec.key].append(t)

    windows = pl.concat(all_test_windows, how="diagonal_relaxed")
    out: dict[str, Any] = {"coverage": coverage(windows), "detectors": {}}
    for spec in exp_specs():
        t = pl.concat(tested[spec.key], how="diagonal_relaxed")
        out["detectors"][spec.key] = {
            "thresholds_by_test_season": thresholds[spec.key],
            "test": {
                **confusion(t["is_fault"], t["alarm"]).to_dict(),
                "auc": auc(t[f"score:{spec.key}"], t["is_fault"]),
            },
            **breakdown(t),
        }
    out["windows"] = {"test_evaluable": int(windows.filter(pl.col("evaluable")).height)}
    return out


def run(processed: Path) -> dict[str, Any]:
    return {
        "detection_version": DETECTION_VERSION,
        "pipeline_version": faultiq.PIPELINE_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
        "window": WINDOW,
        "min_minutes": MIN_MINUTES,
        "min_applicable_minutes": d.MIN_APPLICABLE,
        "max_false_alarm_rate_on_validation": MAX_FALSE_ALARM_RATE,
        "splits": {
            "simulated": {k: f"days {lo}-{hi - 1}" for k, (lo, hi) in SIM_BLOCKS.items()},
            "experimental": (
                "leave one season out; threshold tuned on the next season; trained on the other two"
            ),
        },
        "simulated": run_simulated(processed),
        "experimental": run_experimental(processed),
    }
