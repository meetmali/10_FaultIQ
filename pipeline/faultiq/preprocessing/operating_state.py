"""Operating mode and steady state (ADR 0020).

Each minute gets equipment flags (fan, compressor, heating, economizer), one operating mode, the
minutes spent in that mode so far, and a `steady` flag: steady once the mode has not changed for
`STEADY_DELAY_MINUTES`, in the spirit of ASHRAE Guideline 36 FDD delays. Fault rules and scoring
use only steady minutes, so start-up transients don't raise false alarms.
"""

from __future__ import annotations

import polars as pl

STEADY_DELAY_MINUTES = 10
FAN_FLOW_ON_M3S = 0.05  # about 106 cfm
FAN_POWER_ON_W = 50.0
COMP_STAGE_ON = 0.1  # the simulated set records "off" as 0.1
COMP_POWER_ON_W = 200.0
ECON_DAMPER_ON = 0.15  # above a typical 10% minimum position

MODES = ("off", "fan_only", "economizer", "cooling", "economizer_cooling", "heating", "unknown")
THRESHOLDS = {
    "steady_delay_minutes": STEADY_DELAY_MINUTES,
    "fan_flow_on_m3s": FAN_FLOW_ON_M3S,
    "fan_power_on_w": FAN_POWER_ON_W,
    "comp_stage_on": COMP_STAGE_ON,
    "comp_power_on_w": COMP_POWER_ON_W,
    "econ_damper_on": ECON_DAMPER_ON,
}


def _fan_on(cols: set[str]) -> pl.Expr:
    flow = pl.col("sa_flow") > FAN_FLOW_ON_M3S if "sa_flow" in cols else None
    power = pl.col("power_fan") > FAN_POWER_ON_W if "power_fan" in cols else None
    if flow is not None and power is not None:
        return pl.coalesce(flow, power)
    return flow if flow is not None else power if power is not None else pl.lit(None, pl.Boolean)


def _compressor_on(cols: set[str]) -> pl.Expr:
    if "comp_stage" in cols:
        return pl.col("comp_stage") > COMP_STAGE_ON
    watts = sorted(c for c in cols if c == "power_comp" or c.startswith("power_comp_"))
    if watts:
        # Any one circuit drawing power means the compressor runs; all-null stays unknown.
        return pl.any_horizontal([pl.col(c) > COMP_POWER_ON_W for c in watts])
    return pl.lit(None, pl.Boolean)


def add_operating_state(df: pl.DataFrame) -> pl.DataFrame:
    cols = set(df.columns)
    heating = (pl.col("gas_flow") > 0) if "gas_flow" in cols else pl.lit(False)
    economizer = (
        (pl.col("oa_damper_cmd") > ECON_DAMPER_ON) if "oa_damper_cmd" in cols else pl.lit(False)
    )
    out = df.with_columns(
        _fan_on(cols).alias("fan_on"),
        _compressor_on(cols).alias("compressor_on"),
        heating.fill_null(False).alias("heating_on"),
        economizer.fill_null(False).alias("economizer_on"),
    )
    mode = (
        pl.when(
            ~pl.col("observed") | pl.col("fan_on").is_null() | pl.col("compressor_on").is_null()
        )
        .then(pl.lit("unknown"))
        .when(~pl.col("fan_on"))
        .then(pl.lit("off"))
        .when(pl.col("heating_on"))
        .then(pl.lit("heating"))
        .when(pl.col("compressor_on") & pl.col("economizer_on"))
        .then(pl.lit("economizer_cooling"))
        .when(pl.col("compressor_on"))
        .then(pl.lit("cooling"))
        .when(pl.col("economizer_on"))
        .then(pl.lit("economizer"))
        .otherwise(pl.lit("fan_only"))
    )
    out = out.with_columns(mode.cast(pl.Enum(MODES)).alias("operating_mode"))

    # A run is a stretch of identical mode within one segment; the clock restarts at each new run.
    new_run = (pl.col("operating_mode") != pl.col("operating_mode").shift(1)) | (
        pl.col("segment") != pl.col("segment").shift(1)
    )
    out = out.with_columns(new_run.fill_null(True).cum_sum().alias("_run"))
    out = out.with_columns(
        (
            (pl.col("timestamp") - pl.col("timestamp").first().over("_run")).dt.total_seconds()
            / 60.0
        ).alias("mode_minutes")
    )
    steady = (pl.col("mode_minutes") >= STEADY_DELAY_MINUTES) & ~pl.col("operating_mode").is_in(
        ["off", "unknown"]
    )
    return out.with_columns(steady.alias("steady")).drop("_run")
