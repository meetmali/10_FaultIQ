"""Detectors: two transparent rule baselines and one normal-behaviour model (ADR 0021).

Every detector learns only from fault-free training minutes, then gives each minute one or more
non-negative scores (null where the score doesn't apply). A window's score is the largest
per-signal mean over its applicable steady minutes, and the signal that produced it is kept as
the explanation. Higher means more abnormal; the alarm threshold is tuned later on validation data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from faultiq.detection.windows import ECON_SETPOINT_C

MIN_APPLICABLE = 10  # minutes a signal needs inside a window before it can score that window

# Point sets (ADR 0018). Basic points are what a typical BAS records.
SIM_LIMIT_SIGNALS = {
    "basic": ["sat", "rat_minus_sat", "zone_temp_error"],
    "all": [
        "sat", "rat_minus_sat", "zone_temp_error", "superheat", "subcooling",
        "condensing_approach", "refg_suct_pres", "refg_disc_pres", "power_comp",
        "comp_power_per_capacity", "sensible_heat_ratio", "sa_flow",
    ],
}  # fmt: skip
SIM_MODEL = {
    "basic": {"inputs": ["oat", "rat", "comp_stage"], "targets": ["sat"]},
    "all": {
        "inputs": ["oat", "rat", "comp_stage", "ra_rh"],
        "targets": [
            "sat",
            "sa_flow",
            "refg_suct_pres",
            "refg_disc_pres",
            "refg_disc_temp",
            "power_comp",
        ],
    },
}
EXP_MODEL = {
    "basic": {
        "inputs": ["oat", "rat", "occupied", "compressor_on_num", "zone_cool_sp"],
        "targets": ["oa_damper_cmd", "sat"],
    },
    "all": {
        "inputs": ["oat", "rat", "occupied", "compressor_on_num", "zone_cool_sp", "sat"],
        "targets": ["oa_damper_cmd", "vav_sat_min"],
    },
}


def _steady() -> pl.Expr:
    return pl.col("steady").fill_null(False)


ENVELOPE_QUANTILES = (0.01, 0.99)
# Only conditions the equipment cannot influence. A fault that drives the zone warmer than any
# normal day must still be scored: guarding on return air or compressor stage would let the most
# severe faults hide behind the guard (found in Phase 3 error analysis).
WEATHER_CONDITIONS = ("oat",)
Envelope = dict[str, tuple[float, float]]


def fit_envelope(normal: pl.DataFrame, columns: list[str]) -> Envelope:
    """The range of operating conditions seen in fault-free training (1st to 99th percentile)."""
    steady = normal.filter(_steady())
    env: Envelope = {}
    for c in columns:
        if c in steady.columns and steady[c].drop_nulls().len():
            lo = float(steady[c].quantile(ENVELOPE_QUANTILES[0]) or 0)
            hi = float(steady[c].quantile(ENVELOPE_QUANTILES[1]) or 0)
            env[c] = (lo, hi)
    return env


def within(env: Envelope) -> pl.Expr:
    """True where every condition lies inside the training envelope. Outside, detectors abstain:
    a model must not judge conditions it never saw (it would flag the weather, not a fault)."""
    if not env:
        return pl.lit(True)
    return pl.all_horizontal(
        [pl.col(c).is_between(lo, hi).fill_null(False) for c, (lo, hi) in env.items()]
    )


@dataclass
class LimitRules:
    """Statistical limit checks: each signal's normal 1st-99th percentile range per operating mode.

    A minute scores by how far a signal sits outside its normal range, in units of that range's
    width. Transparent and easy to explain ("rat_minus_sat was 4.1 K; normal in cooling is 10.5 to
    13.5 K"), but blind to weather: the ranges are wide because they ignore conditions.
    """

    signals: list[str]
    name: str = "limit_rules"
    limits: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)
    envelope: Envelope = field(default_factory=dict)
    condition_columns: tuple[str, ...] = WEATHER_CONDITIONS

    def fit(self, normal: pl.DataFrame) -> LimitRules:
        self.envelope = fit_envelope(normal, list(self.condition_columns))
        steady = normal.filter(_steady())
        for (mode,), part in steady.group_by(["operating_mode"]):
            for s in self.signals:
                if s not in part.columns:
                    continue
                values = part[s].drop_nulls()
                if values.len() < 100:
                    continue
                lo, hi = float(values.quantile(0.01) or 0), float(values.quantile(0.99) or 0)
                self.limits[(str(mode), s)] = (lo, hi)
        return self

    def score(self, df: pl.DataFrame) -> pl.DataFrame:
        exprs = []
        for s in self.signals:
            if s not in df.columns:
                continue
            expr = pl.lit(None, dtype=pl.Float64)
            for (mode, sig), (lo, hi) in self.limits.items():
                if sig != s:
                    continue
                width = max(hi - lo, 1e-6)
                exceed = pl.max_horizontal(
                    pl.lit(0.0), (pl.col(s) - hi) / width, (lo - pl.col(s)) / width
                )
                expr = (
                    pl.when(pl.col("operating_mode").cast(pl.Utf8) == mode)
                    .then(exceed)
                    .otherwise(expr)
                )
            exprs.append(
                pl.when(_steady() & within(self.envelope)).then(expr).alias(f"{self.name}:{s}")
            )
        return df.select(exprs)


@dataclass
class EconomizerRules:
    """Physics rules in the style of Title 24 economizer FDD and Guideline 36 (ORNL set).

    Uses the documented control sequence (economizer enabled below 10 deg C), so nothing is learned
    except the alarm threshold. Each rule scores 1 for a violating minute, 0 for a compliant one,
    null where it doesn't apply.
    """

    point_set: str
    name: str = "economizer_rules"
    margin_k: float = 1.0
    damper_min: float = 0.15
    vav_tolerance_k: float = 1.0

    def fit(self, normal: pl.DataFrame) -> EconomizerRules:
        return self

    def score(self, df: pl.DataFrame) -> pl.DataFrame:
        on = _steady() & pl.col("fan_on").fill_null(False)
        warm = pl.col("oat") > ECON_SETPOINT_C + self.margin_k
        cool = pl.col("oat") < ECON_SETPOINT_C - self.margin_k
        open_ = pl.col("oa_damper_cmd") > self.damper_min
        cooling = pl.col("compressor_on").fill_null(False)
        rules = [
            # Economizing when it should not: damper open while outdoor air is too warm.
            pl.when(on & warm)
            .then(open_.cast(pl.Float64))
            .alias(f"{self.name}:economizing_when_should_not"),
            # Not economizing when it should: mechanical cooling with free cooling available.
            pl.when(on & cool & cooling)
            .then((~open_).cast(pl.Float64))
            .alias(f"{self.name}:not_economizing_when_should"),
        ]
        if self.point_set == "all" and "sat_minus_vav_sat_min" in df.columns:
            rules.append(
                pl.when(on & cooling)
                .then(
                    (pl.col("sat_minus_vav_sat_min").abs() > self.vav_tolerance_k).cast(pl.Float64)
                )
                .alias(f"{self.name}:sat_disagrees_with_vav")
            )
        return df.select(rules)


@dataclass
class NormalModel:
    """Normal-behaviour model: predict what each target should read from operating conditions.

    One smooth regression per target (quadratic terms and interactions, ridge-regularised), trained
    on fault-free steady minutes only. Gradient-boosted trees were tried first and rejected: they
    memorised the training weeks, and their fault-free error grew 3 to 5 times on later weeks, while
    the smooth model stays within 1 to 3 times. A minute scores |observed - expected| divided by the
    typical fault-free error, so every target is on the same footing. The expected value is also
    the evidence Phase 5 shows users.
    """

    inputs: list[str]
    targets: list[str]
    name: str = "normal_model"
    models: dict[str, Any] = field(default_factory=dict)
    scales: dict[str, float] = field(default_factory=dict)
    envelope: Envelope = field(default_factory=dict)
    alpha: float = 1.0

    @staticmethod
    def _prepare(df: pl.DataFrame) -> pl.DataFrame:
        if "compressor_on" in df.columns and "compressor_on_num" not in df.columns:
            df = df.with_columns(
                pl.col("compressor_on").cast(pl.Float64).alias("compressor_on_num")
            )
        return df

    def _complete(self) -> pl.Expr:
        return pl.all_horizontal([pl.col(c).is_not_null() for c in self.inputs])

    def fit(self, normal: pl.DataFrame) -> NormalModel:
        steady = self._prepare(normal).filter(_steady())
        self.inputs = [c for c in self.inputs if c in steady.columns]
        self.envelope = fit_envelope(steady, [c for c in WEATHER_CONDITIONS if c in self.inputs])
        for t in self.targets:
            if t not in steady.columns:
                continue
            part = steady.filter(self._complete() & pl.col(t).is_not_null())
            if part.height < 200:
                continue
            x, y = part.select(self.inputs).to_numpy(), part[t].to_numpy()
            model = make_pipeline(StandardScaler(), PolynomialFeatures(2), Ridge(alpha=self.alpha))
            model.fit(x, y)
            resid = y - model.predict(x)
            mad = float(np.median(np.abs(resid - np.median(resid)))) * 1.4826
            # Floor the scale at 2% of the target's normal spread: a target with few distinct
            # values (fan flow at fixed speeds) can be fitted perfectly, and a zero scale would
            # turn any tiny difference into a huge anomaly.
            spread = float(np.quantile(y, 0.95) - np.quantile(y, 0.05))
            self.models[t] = model
            self.scales[t] = max(mad, 0.02 * spread, 1e-6)
        return self

    def expected(self, df: pl.DataFrame) -> pl.DataFrame:
        df = self._prepare(df)
        complete = df.select(self._complete().alias("_c"))["_c"].to_numpy()
        x = np.nan_to_num(df.select(self.inputs).to_numpy().astype(float))
        out = {}
        for t, m in self.models.items():
            pred = m.predict(x) if len(x) else np.array([])
            out[f"expected:{t}"] = pl.Series(np.where(complete, pred, np.nan)).fill_nan(None)
        return pl.DataFrame(out)

    def score(self, df: pl.DataFrame) -> pl.DataFrame:
        prepared = self._prepare(df)
        expected = self.expected(prepared)
        cols = []
        for t in self.models:
            z = ((prepared[t] - expected[f"expected:{t}"]).abs() / self.scales[t]).alias(
                f"{self.name}:{t}"
            )
            cols.append(z)
        scored = pl.DataFrame(cols) if cols else pl.DataFrame()
        applicable = prepared.select((_steady() & within(self.envelope)).alias("_ok"))["_ok"]
        return scored.select([pl.when(applicable).then(pl.col(c)).alias(c) for c in scored.columns])


def window_scores(
    minutes: pl.DataFrame, minute_scores: pl.DataFrame, keys: list[str]
) -> pl.DataFrame:
    """Window score: max over signals of each signal's mean over applicable window minutes."""
    signals = minute_scores.columns
    joined = pl.concat([minutes.select(keys), minute_scores], how="horizontal")
    agg = joined.group_by(keys).agg(
        [
            pl.when(pl.col(s).count() >= MIN_APPLICABLE).then(pl.col(s).mean()).alias(s)
            for s in signals
        ]
    )
    score = pl.max_horizontal([pl.col(s) for s in signals])
    top: Any = pl.when(score.is_null()).then(None)
    for s in signals:
        top = top.when(pl.col(s) == score).then(pl.lit(s.split(":", 1)[1]))
    return agg.select([*keys, score.alias("score"), top.alias("top_signal")])
