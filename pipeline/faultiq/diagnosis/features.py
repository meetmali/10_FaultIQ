"""Hourly diagnosis features: what the equipment did, not what the weather was (ADR 0022).

A window is diagnosable when the equipment the supported faults act on was running for at least
`MIN_MINUTES` steady minutes: the compressor for the simulated refrigerant faults, the supply fan
for the ORNL air-side faults. The rule uses no label, so it works the same on new data.

Features are behaviour only:
- medians of physics features that are differences or ratios (superheat, mixed minus supply air),
- medians of signed residuals from the Phase 3 normal-behaviour models (observed minus expected,
  in units of typical error), so "suction pressure 3 errors below normal" is one number,
- the share of minutes breaking each economizer rule (ORNL).

Raw readings and operating conditions (outdoor air, return air, occupancy) are left out on purpose.
Faulty windows are only kept where their fault could show, so the setpoint-offset windows all sit
in a narrow outdoor-air band; a classifier given outdoor air would learn the band, not the fault.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from faultiq.detection.detectors import MIN_APPLICABLE, EconomizerRules, NormalModel
from faultiq.detection.windows import MIN_MINUTES, WINDOW_KEYS

NORMAL = "fault_free"  # the "no supported fault" class
POINT_SETS = ("basic", "all")


@dataclass(frozen=True)
class FeatureSpec:
    medians: tuple[str, ...]
    residuals: tuple[tuple[str, str], ...]  # (normal model point set, target)
    rules: bool = False

    def columns(self) -> list[str]:
        cols = [f"med:{c}" for c in self.medians] + [f"resid:{t}" for _, t in self.residuals]
        return cols


SIM_FEATURES = {
    "basic": FeatureSpec(("rat_minus_sat", "zone_temp_error"), (("basic", "sat"),)),
    "all": FeatureSpec(
        (
            "rat_minus_sat", "zone_temp_error", "superheat", "subcooling", "condensing_approach",
            "comp_power_per_capacity", "sensible_heat_ratio",
        ),
        tuple(
            ("all", t)
            for t in ("sat", "sa_flow", "refg_suct_pres", "refg_disc_pres", "refg_disc_temp",
                      "power_comp")
        ),
    ),
}  # fmt: skip
EXP_FEATURES = {
    "basic": FeatureSpec(
        ("oaf_temp", "mat_minus_sat", "rat_minus_sat"),
        (("basic", "oa_damper_cmd"), ("basic", "sat")),
        rules=True,
    ),
    "all": FeatureSpec(
        ("oaf_temp", "mat_minus_sat", "rat_minus_sat", "sat_minus_vav_sat_min"),
        (("basic", "oa_damper_cmd"), ("basic", "sat"), ("all", "vav_sat_min")),
        rules=True,
    ),
}
RULE_NAMES = {
    "basic": ("economizing_when_should_not", "not_economizing_when_should"),
    "all": ("economizing_when_should_not", "not_economizing_when_should", "sat_disagrees_with_vav"),
}


def feature_columns(dataset: str, point_set: str) -> list[str]:
    spec = (SIM_FEATURES if dataset == "simulated" else EXP_FEATURES)[point_set]
    cols = spec.columns()
    if spec.rules:
        cols += [f"rule:{r}" for r in RULE_NAMES[point_set]]
    return cols


def diagnosable_expr(dataset: str) -> pl.Expr:
    """Minutes the supported faults could act on, decided without the label."""
    running = "compressor_on" if dataset == "simulated" else "fan_on"
    return pl.col("steady").fill_null(False) & pl.col(running).fill_null(False)


def window_features(
    minutes: pl.DataFrame,
    dataset: str,
    models: dict[str, NormalModel],
    rules: EconomizerRules | None = None,
) -> pl.DataFrame:
    """One row per file-hour: `n_diagnosable` plus every feature either point set uses."""
    specs = SIM_FEATURES if dataset == "simulated" else EXP_FEATURES
    medians = sorted({c for s in specs.values() for c in s.medians if c in minutes.columns})
    targets: dict[str, str] = {}  # feature target -> model point set (first spec wins)
    for s in specs.values():
        for ps, t in s.residuals:
            targets.setdefault(t, ps)

    parts = [minutes.select([*WINDOW_KEYS, *medians, diagnosable_expr(dataset).alias("_diag")])]
    resid_cols = []
    for ps in dict.fromkeys(targets.values()):
        r = models[ps].residuals(minutes)
        keep = [f"resid:{t}" for t, p in targets.items() if p == ps and f"resid:{t}" in r.columns]
        parts.append(r.select(keep))
        resid_cols += keep
    rule_cols = []
    if rules is not None:
        scored = rules.score(minutes)
        scored = scored.rename({c: "rule:" + c.split(":", 1)[1] for c in scored.columns})
        parts.append(scored)
        rule_cols = scored.columns
    frame = pl.concat(parts, how="horizontal")

    d = pl.col("_diag")

    def over_diag(c: str, how: str) -> pl.Expr:
        v = pl.col(c).filter(d)
        agg = v.median() if how == "median" else v.mean()
        return pl.when(v.count() >= MIN_APPLICABLE).then(agg).alias(c)

    return frame.group_by(WINDOW_KEYS).agg(
        d.sum().alias("n_diagnosable"),
        *[over_diag(c, "median").alias(f"med:{c}") for c in medians],
        *[over_diag(c, "median") for c in resid_cols],
        *[over_diag(c, "mean") for c in rule_cols],
    )


def is_diagnosable() -> pl.Expr:
    return pl.col("n_diagnosable") >= MIN_MINUTES
