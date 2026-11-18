"""Per-minute physics features (ADR 0020: physics only in Phase 2, windows wait for Phase 3).

Each feature is added only when its input roles exist, so the same function serves every dataset
and every user export. Features are null wherever an input is missing or the physics is
undefined (for example the outdoor-air fraction when outdoor and return air are too close).

Which features are "basic points only" (ADR 0018) is recorded in `FEATURE_INPUTS`.
"""

from __future__ import annotations

import polars as pl

from faultiq.features.refrigerant import saturation_temp_c

OAF_MIN_SPREAD_K = 5.0  # below this |OAT - RAT| the mixing equation is too sensitive to noise
MIN_CAPACITY_W = 500.0

# feature -> roles it needs. Used to decide availability and basic-points eligibility.
FEATURE_INPUTS: dict[str, tuple[str, ...]] = {
    "oaf_temp": ("mat", "rat", "oat"),
    "oaf_flow": ("oa_flow", "sa_flow"),
    "rat_minus_sat": ("rat", "sat"),
    "mat_minus_sat": ("mat", "sat"),
    "zone_temp_error": ("zone_temp", "zone_temp_sp"),
    "superheat": ("refg_suct_temp", "refg_suct_pres"),
    "subcooling": ("refg_cond_pres", "refg_cond_temp"),
    "condensing_approach": ("refg_disc_pres", "oat"),
    "comp_power_per_capacity": ("power_comp", "cap_total"),
    "sensible_heat_ratio": ("cap_sensible", "cap_total"),
    "vav_sat_min": ("vav_sat",),
    "sat_minus_vav_sat_min": ("sat", "vav_sat"),
}


def _has(cols: set[str], roles: tuple[str, ...]) -> bool:
    return all(
        r in cols or (r == "vav_sat" and any(c.startswith("vav_sat_") for c in cols)) for r in roles
    )


def add_physics_features(df: pl.DataFrame) -> pl.DataFrame:
    cols = set(df.columns)
    exprs: list[pl.Expr] = []

    if _has(cols, FEATURE_INPUTS["oaf_temp"]):
        spread = pl.col("oat") - pl.col("rat")
        exprs.append(
            pl.when(spread.abs() >= OAF_MIN_SPREAD_K)
            .then((pl.col("mat") - pl.col("rat")) / spread)
            .otherwise(None)
            .alias("oaf_temp")
        )
    if _has(cols, FEATURE_INPUTS["oaf_flow"]):
        exprs.append(
            pl.when(pl.col("sa_flow") > 0)
            .then(pl.col("oa_flow") / pl.col("sa_flow"))
            .alias("oaf_flow")
        )
    if _has(cols, FEATURE_INPUTS["rat_minus_sat"]):
        exprs.append((pl.col("rat") - pl.col("sat")).alias("rat_minus_sat"))
    if _has(cols, FEATURE_INPUTS["mat_minus_sat"]):
        exprs.append((pl.col("mat") - pl.col("sat")).alias("mat_minus_sat"))
    if _has(cols, FEATURE_INPUTS["zone_temp_error"]):
        exprs.append((pl.col("zone_temp") - pl.col("zone_temp_sp")).alias("zone_temp_error"))

    # Refrigerant features need absolute pressure on a single circuit (simulated set). The field
    # set's per-circuit pressures are left out: their gauge/absolute basis is undocumented.
    if _has(cols, FEATURE_INPUTS["superheat"]):
        exprs.append(
            (pl.col("refg_suct_temp") - saturation_temp_c(pl.col("refg_suct_pres"))).alias(
                "superheat"
            )
        )
    if _has(cols, FEATURE_INPUTS["subcooling"]):
        exprs.append(
            (saturation_temp_c(pl.col("refg_cond_pres")) - pl.col("refg_cond_temp")).alias(
                "subcooling"
            )
        )
    if _has(cols, FEATURE_INPUTS["condensing_approach"]):
        exprs.append(
            (saturation_temp_c(pl.col("refg_disc_pres")) - pl.col("oat")).alias(
                "condensing_approach"
            )
        )
    if _has(cols, FEATURE_INPUTS["comp_power_per_capacity"]):
        exprs.append(
            pl.when(pl.col("cap_total") > MIN_CAPACITY_W)
            .then(pl.col("power_comp") / pl.col("cap_total"))
            .alias("comp_power_per_capacity")
        )
    if _has(cols, FEATURE_INPUTS["sensible_heat_ratio"]):
        exprs.append(
            pl.when(pl.col("cap_total") > MIN_CAPACITY_W)
            .then(pl.col("cap_sensible") / pl.col("cap_total"))
            .alias("sensible_heat_ratio")
        )

    vav = sorted(c for c in cols if c.startswith("vav_sat_"))
    if vav:
        # The coldest VAV discharge is the closest independent reading of true supply air (reheat
        # only warms it). Its gap to the RTU's own SAT reading is the bias check signal.
        exprs.append(pl.min_horizontal([pl.col(c) for c in vav]).alias("vav_sat_min"))
    out = df.with_columns(exprs) if exprs else df
    if vav and "sat" in cols:
        out = out.with_columns(
            (pl.col("sat") - pl.col("vav_sat_min")).alias("sat_minus_vav_sat_min")
        )
    return out
