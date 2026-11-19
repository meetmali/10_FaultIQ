"""Hourly windows, fault observability and evaluation splits (ADR 0021).

A fault can only be detected when the equipment it affects is working: a refrigerant fault needs
the compressor running, a stuck damper needs the fan on. Each minute gets an `observable` flag for
its file's fault, and each hour becomes one window. Faulty windows count for scoring only when at
least `MIN_MINUTES` minutes were observable; fault-free windows count when at least that many
minutes were steady. Everything else is reported as coverage, never silently dropped.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

WINDOW = "1h"
MIN_MINUTES = 30
ECON_SETPOINT_C = 10.0  # documented ORNL economizer enable setpoint (50 deg F)

REFRIGERANT_FAULTS = frozenset(
    {
        "condenser_fouling",
        "evaporator_fouling",
        "liquid_line_restriction",
        "suction_line_restriction",
        "refrigerant_overcharge",
        "refrigerant_undercharge",
        "compressor_staging",
    }
)

# Simulated time blocks (days since 2018-07-20 00:00), with one-day gaps between them.
SIM_START = datetime(2018, 7, 20)
SIM_BLOCKS = {"train": (0, 60), "val": (61, 81), "test": (82, 101)}
SEASONS = ("Fall_2020", "Spring_2021", "Summer_2021", "Winter_2022")


def observable_expr(fault: str, intensity: float | None, columns: set[str]) -> pl.Expr:
    """Minutes where `fault` could physically show. Fault-free files: every steady minute."""
    steady = pl.col("steady").fill_null(False)
    if fault == "fault_free":
        return steady
    if fault in REFRIGERANT_FAULTS:
        return steady & pl.col("compressor_on").fill_null(False)
    fan = pl.col("fan_on").fill_null(False)
    if fault == "oa_damper_stuck":
        occupied = (
            (pl.col("occupied") == 1).fill_null(False) if "occupied" in columns else pl.lit(True)
        )
        return steady & fan & occupied
    if fault == "economizer_setpoint_offset" and intensity is not None:
        # Behaviour differs only when outdoor air sits between the correct and the wrong setpoint.
        lo, hi = sorted((ECON_SETPOINT_C, ECON_SETPOINT_C + intensity))
        return steady & fan & pl.col("oat").is_between(lo, hi)
    if fault == "sat_sensor_bias":
        return steady & fan
    return steady


def add_minute_context(df: pl.DataFrame, label: dict[str, object]) -> pl.DataFrame:
    fault = str(label["fault"])
    raw_intensity = label.get("intensity")
    intensity = float(raw_intensity) if isinstance(raw_intensity, int | float) else None
    return df.with_columns(
        observable=observable_expr(fault, intensity, set(df.columns)),
        window_start=pl.col("timestamp").dt.truncate(WINDOW),
        file=pl.lit(str(label["source_name"])),
        fault=pl.lit(fault),
        intensity=pl.lit(intensity, dtype=pl.Float64),
        season=pl.lit(label.get("season"), dtype=pl.Utf8),
    )


WINDOW_KEYS = ["file", "window_start"]


def window_table(minutes: pl.DataFrame) -> pl.DataFrame:
    """One row per file-hour with labels, coverage counts and the dominant steady mode."""
    base = minutes.group_by(WINDOW_KEYS).agg(
        pl.col("fault").first(),
        pl.col("intensity").first(),
        pl.col("season").first(),
        pl.col("steady").fill_null(False).sum().alias("n_steady"),
        pl.col("observable").sum().alias("n_observable"),
    )
    dominant = (
        minutes.filter(pl.col("steady").fill_null(False))
        .group_by([*WINDOW_KEYS, "operating_mode"])
        .len()
        .sort("len", descending=True)
        .group_by(WINDOW_KEYS)
        .agg(pl.col("operating_mode").first().cast(pl.Utf8).alias("mode"))
    )
    out = base.join(dominant, on=WINDOW_KEYS, how="left").with_columns(
        is_fault=pl.col("fault") != "fault_free",
    )
    return out.with_columns(
        evaluable=pl.when(pl.col("is_fault"))
        .then(pl.col("n_observable") >= MIN_MINUTES)
        .otherwise(pl.col("n_steady") >= MIN_MINUTES)
    ).sort(WINDOW_KEYS)


def sim_split(window_start: pl.Expr) -> pl.Expr:
    """Simulated set: contiguous day blocks shared by every file, so no test hour meets training."""
    day = (window_start - pl.lit(SIM_START)).dt.total_days()
    expr = pl.lit(None, dtype=pl.Utf8)
    for name, (lo, hi) in SIM_BLOCKS.items():
        expr = pl.when((day >= lo) & (day < hi)).then(pl.lit(name)).otherwise(expr)
    return expr


def season_fold(test_season: str) -> dict[str, str]:
    """ORNL: test on one season, tune on the next, train on the other two."""
    i = SEASONS.index(test_season)
    val = SEASONS[(i + 1) % len(SEASONS)]
    return {s: ("test" if s == test_season else "val" if s == val else "train") for s in SEASONS}
