"""Fault classifiers and the confidence cut-off (ADR 0022).

Two candidates per dataset and point set, chosen on validation data only (ADR 0011):
- a multinomial logistic regression, the transparent baseline,
- LightGBM, adopted only if it beats the baseline's validation macro-F1 by `ADOPT_MARGIN`.

The classifier always picks its most likely class. That answer is shown only when its probability
reaches a cut-off tuned on validation windows, the lowest one at which named faults are right at
least `TARGET_PRECISION` of the time. Below it the result is "inconclusive": an honest "I can't
tell" is cheaper for a technician than a confident wrong fault.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl
from lightgbm import LGBMClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from faultiq.diagnosis.features import NORMAL

TARGET_PRECISION = 0.90  # named faults must be right at least 9 times in 10 on validation data
MIN_NAMED = 10  # a cut-off must name at least this many validation windows to count as tested
ADOPT_MARGIN = 0.01  # LightGBM must beat the baseline's validation macro-F1 by this much
INCONCLUSIVE = "inconclusive"
SEED = 0


def matrix(windows: pl.DataFrame, columns: list[str]) -> np.ndarray:
    """Feature matrix in a fixed column order; a column the data lacks is all missing."""
    present = windows.with_columns(
        [pl.lit(None, dtype=pl.Float64).alias(c) for c in columns if c not in windows.columns]
    )
    return present.select(columns).cast(pl.Float64).to_numpy()


@dataclass
class Classifier:
    """A fitted model plus the names it needs to explain itself."""

    family: str
    columns: list[str]
    model: Any = None
    classes: np.ndarray = field(default_factory=lambda: np.array([]))

    def fit(self, x: np.ndarray, y: np.ndarray) -> Classifier:
        if self.family == "logistic":
            self.model = Pipeline(
                [
                    ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
                ]
            )
        else:
            self.model = LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                num_leaves=15,
                min_child_samples=20,
                class_weight="balanced",
                random_state=SEED,
                n_jobs=1,
                deterministic=True,
                force_col_wise=True,
                verbose=-1,
            )
        self.model.fit(x, y)
        self.classes = np.asarray(self.model.classes_)
        return self

    def proba(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0:
            return np.zeros((0, len(self.classes)))
        return np.asarray(self.model.predict_proba(x))

    def top_feature(self, x: np.ndarray, proba: np.ndarray) -> list[str | None]:
        """The feature that pushed hardest toward the predicted class, per window (ADR 0016)."""
        if len(x) == 0:
            return []
        k = proba.argmax(axis=1)
        n = len(self.columns)
        if self.family == "logistic":
            scaled = self.model[:-1].transform(x)
            contrib = scaled[:, None, :n] * self.model[-1].coef_[None, :, :n]
        else:
            raw = np.asarray(self.model.predict(x, pred_contrib=True))
            contrib = raw.reshape(len(x), len(self.classes), n + 1)[:, :, :n]
        picked = contrib[np.arange(len(x)), k]
        return [self.columns[i] for i in picked.argmax(axis=1)]


def tune_cutoff(
    proba: np.ndarray, truth: np.ndarray, classes: np.ndarray, target: float = TARGET_PRECISION
) -> float:
    """Lowest confidence at which named faults are right at least `target` of the time."""
    top, pred = proba.max(axis=1), classes[proba.argmax(axis=1)]
    named = pred != NORMAL
    for t in np.unique(top[named]):  # ascending: the lowest cut-off that works answers most often
        keep = named & (top >= t)
        if keep.sum() >= MIN_NAMED and (pred[keep] == truth[keep]).mean() >= target:
            return float(t)
    return float("inf")  # never confident enough on validation: never name a fault


def decide(proba: np.ndarray, classes: np.ndarray, cutoff: float) -> np.ndarray:
    """The answer per window: a fault, `fault_free` (no supported fault) or inconclusive."""
    if len(proba) == 0:
        return np.array([], dtype=object)
    pred = classes[proba.argmax(axis=1)].astype(object)
    pred[proba.max(axis=1) < cutoff] = INCONCLUSIVE
    return pred
