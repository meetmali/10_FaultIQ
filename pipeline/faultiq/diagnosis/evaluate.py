"""Diagnosis metrics on held-out windows (ADR 0022).

Macro-F1 weighs every class equally, so a rare fault counts as much as a common one. It is
measured on the raw most-likely class. The answers a user sees (with "inconclusive" allowed) are
measured separately: how often a fault is named, and how often a named fault is right.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from faultiq.diagnosis.classify import INCONCLUSIVE
from faultiq.diagnosis.features import NORMAL


def macro_f1(truth: np.ndarray, pred: np.ndarray, labels: list[str]) -> float:
    if len(truth) == 0:
        return 0.0
    return round(float(f1_score(truth, pred, labels=labels, average="macro", zero_division=0)), 4)


def per_class(truth: np.ndarray, pred: np.ndarray, labels: list[str]) -> list[dict[str, Any]]:
    p, r, f, n = precision_recall_fscore_support(truth, pred, labels=labels, zero_division=0)
    return [
        {"class": c, "windows": int(n[i]), "precision": round(float(p[i]), 4),
         "recall": round(float(r[i]), 4), "f1": round(float(f[i]), 4)}
        for i, c in enumerate(labels)
    ]  # fmt: skip


def confusion(truth: np.ndarray, pred: np.ndarray, labels: list[str]) -> dict[str, Any]:
    """Rows are the true class, columns the predicted class."""
    cm = confusion_matrix(truth, pred, labels=labels) if len(truth) else np.zeros((0, 0))
    return {"labels": labels, "matrix": cm.astype(int).tolist()}


def calibration_error(proba: np.ndarray, truth: np.ndarray, classes: np.ndarray) -> float:
    """Expected calibration error of the top class, 10 equal-width bins. 0 means a stated 80%
    confidence is right 80% of the time."""
    if len(truth) == 0:
        return 0.0
    top = proba.max(axis=1)
    right = classes[proba.argmax(axis=1)] == truth
    bins = np.minimum((top * 10).astype(int), 9)
    err = sum(
        abs(top[bins == b].mean() - right[bins == b].mean()) * (bins == b).mean()
        for b in range(10)
        if (bins == b).any()
    )
    return round(float(err), 4)


def answers(truth: np.ndarray, answer: np.ndarray) -> dict[str, Any]:
    """What the user sees, with inconclusive allowed."""
    named = (answer != NORMAL) & (answer != INCONCLUSIVE)
    answered = answer != INCONCLUSIVE
    faulty = truth != NORMAL
    n = len(truth)

    def share(mask: np.ndarray, of: np.ndarray) -> float | None:
        return round(float(mask[of].mean()), 4) if of.any() else None

    return {
        "windows": n,
        "answered_share": share(answered, np.ones(n, dtype=bool)),
        "named_fault_precision": share(answer == truth, named),
        "faulty_windows": {
            "correct_fault": share(answer == truth, faulty),
            "wrong_fault": share(named & (answer != truth), faulty),
            "said_no_fault": share(answer == NORMAL, faulty),
            "inconclusive": share(answer == INCONCLUSIVE, faulty),
        },
        "normal_windows": {
            "said_no_fault": share(answer == NORMAL, ~faulty),
            "named_a_fault": share(named, ~faulty),
            "inconclusive": share(answer == INCONCLUSIVE, ~faulty),
        },
    }


def by_severity(scored: pl.DataFrame) -> list[dict[str, Any]]:
    """Per fault and intensity: how often the answer was right, wrong, normal or inconclusive."""
    return (
        scored.filter(pl.col("fault") != NORMAL)
        .group_by(["fault", "intensity"])
        .agg(
            pl.len().alias("windows"),
            (pl.col("answer") == pl.col("fault")).mean().alias("correct"),
            (pl.col("answer") == INCONCLUSIVE).mean().alias("inconclusive"),
            (pl.col("answer") == NORMAL).mean().alias("said_no_fault"),
            (pl.col("predicted") == pl.col("fault")).mean().alias("top_class_correct"),
        )
        .sort(["fault", "intensity"])
        .to_dicts()
    )


def evidence(scored: pl.DataFrame) -> list[dict[str, Any]]:
    """Most common deciding feature for each named fault (the explanation Phase 5 will show)."""
    return (
        scored.filter((pl.col("answer") != NORMAL) & (pl.col("answer") != INCONCLUSIVE))
        .group_by(["answer", "top_feature"])
        .len()
        .sort(["answer", "len"], descending=[False, True])
        .group_by("answer", maintain_order=True)
        .head(3)
        .to_dicts()
    )
