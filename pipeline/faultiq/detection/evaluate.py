"""Threshold tuning on validation data and held-out metrics (ADR 0021).

The alarm threshold is the only tuned parameter. It is set on validation windows to the lowest
value that keeps false alarms within a budget (`MAX_FALSE_ALARM_RATE` of normal windows), then
frozen before the test windows are scored. Maximising F1 instead was tried first and rejected:
with 24 faulty files to 1 fault-free file, "alarm on everything" scores F1 = 0.98. Precision and
F1 depend on how common faults are in the test set, so the headline metrics are recall at the
false-alarm budget and ROC-AUC, which do not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
from sklearn.metrics import roc_auc_score

MAX_FALSE_ALARM_RATE = 0.05  # at most 1 in 20 normal hours may raise an alarm on validation data


@dataclass(frozen=True)
class Metrics:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def fpr(self) -> float:
        return self.fp / (self.fp + self.tn) if self.fp + self.tn else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": round(self.precision, 4), "recall": round(self.recall, 4),
            "f1": round(self.f1, 4), "false_positive_rate": round(self.fpr, 4),
        }  # fmt: skip


def confusion(labels: pl.Series, predictions: pl.Series) -> Metrics:
    y = labels.cast(pl.Boolean).to_numpy()
    p = predictions.cast(pl.Boolean).to_numpy()
    return Metrics(
        tp=int((y & p).sum()),
        fp=int((~y & p).sum()),
        fn=int((y & ~p).sum()),
        tn=int((~y & ~p).sum()),
    )


def predict(scores: pl.Series, threshold: float) -> pl.Series:
    """Alarm when the score exceeds the threshold. No score (nothing applicable) means no alarm."""
    return (scores > threshold).fill_null(False)


def tune_threshold(
    scores: pl.Series, labels: pl.Series, max_fpr: float = MAX_FALSE_ALARM_RATE
) -> tuple[float, Metrics]:
    """Lowest threshold whose false-alarm rate on validation windows stays within `max_fpr`."""
    finite = scores.drop_nulls().unique().sort().to_numpy()
    never = float(finite.max()) if finite.size else float("inf")
    best_t = never
    for t in finite[::-1]:  # high to low: keep lowering while false alarms stay within budget
        if confusion(labels, predict(scores, float(t))).fpr <= max_fpr:
            best_t = float(t)
        else:
            break
    return best_t, confusion(labels, predict(scores, best_t))


def auc(scores: pl.Series, labels: pl.Series) -> float | None:
    """ROC-AUC: chance a faulty window outscores a normal one. Unscorable windows rank lowest."""
    y = labels.cast(pl.Boolean).to_numpy()
    if y.all() or not y.any():
        return None
    s = scores.fill_null(float("-inf")).to_numpy()
    s = np.where(
        np.isfinite(s), s, np.nanmin(s[np.isfinite(s)]) - 1 if np.isfinite(s).any() else 0.0
    )
    return round(float(roc_auc_score(y, s)), 4)


def _null_share(frame: pl.DataFrame) -> float:
    """Share of windows with no score, i.e. where the detector abstained."""
    if frame.height == 0:
        return 0.0
    return round(float(frame.select(pl.col("score").is_null().mean()).item()), 4)


def breakdown(test: pl.DataFrame) -> dict[str, Any]:
    """Recall per fault and intensity, and false alarms per operating mode, on test windows."""
    faults = (
        test.filter(pl.col("is_fault"))
        .group_by(["fault", "intensity"])
        .agg(
            pl.len().alias("windows"),
            pl.col("alarm").mean().alias("recall"),
            pl.col("score").is_null().mean().alias("abstained"),
        )
        .sort(["fault", "intensity"])
    )
    fp = (
        test.filter(~pl.col("is_fault"))
        .group_by("mode")
        .agg(pl.len().alias("windows"), pl.col("alarm").mean().alias("false_alarm_rate"))
        .sort("mode")
    )
    top = (
        test.filter(pl.col("alarm"))
        .group_by(["fault", "top_signal"])
        .len()
        .sort(["fault", "len"], descending=[False, True])
    )
    return {
        "abstained_share": {
            "faulty": _null_share(test.filter(pl.col("is_fault"))),
            "normal": _null_share(test.filter(~pl.col("is_fault"))),
        },
        "recall_by_fault": faults.to_dicts(),
        "false_alarms_by_mode": fp.to_dicts(),
        "alarm_signals": top.to_dicts(),
    }


def coverage(windows: pl.DataFrame) -> list[dict[str, Any]]:
    """Share of each fault's windows in which the fault could be observed (and so scored)."""
    return (
        windows.group_by("fault")
        .agg(pl.len().alias("windows"), pl.col("evaluable").mean().alias("observable_share"))
        .sort("fault")
        .to_dicts()
    )
