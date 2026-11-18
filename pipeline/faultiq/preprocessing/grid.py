"""Regular time grid without filling (ADR 0020).

Each file is put on a regular grid at its own sampling interval. Missing minutes become explicit
rows with `observed = False` and null values: nothing is interpolated. A gap longer than
`split_gap_minutes` starts a new `segment` instead of inserting thousands of empty rows, so later
windowed features never reach across a long outage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import polars as pl


@dataclass
class GridReport:
    input_rows: int
    null_timestamp_rows: int
    step_seconds: int
    snapped_timestamps: int
    duplicates_dropped: int
    segments: int
    inserted_missing_rows: int
    output_rows: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_step_seconds(ts: pl.Series) -> int:
    """The file's sampling interval: the most common positive step, rounded to whole seconds."""
    steps = ts.diff().dt.total_seconds().drop_nulls()
    steps = steps.filter(steps > 0)
    if steps.len() == 0:
        return 60
    return int(steps.mode().sort()[0])


def to_regular_grid(
    df: pl.DataFrame, split_gap_minutes: int = 60
) -> tuple[pl.DataFrame, GridReport]:
    input_rows = df.height
    df = df.filter(pl.col("timestamp").is_not_null())
    null_ts = input_rows - df.height
    step = detect_step_seconds(df["timestamp"])
    every = f"{step}s"

    # Snap to the grid, then keep the first reading per grid point.
    snapped = df.with_columns(pl.col("timestamp").dt.round(every).alias("_snapped"))
    n_snapped = int((snapped["_snapped"] != snapped["timestamp"]).sum())
    snapped = snapped.drop("timestamp").rename({"_snapped": "timestamp"})
    deduped = snapped.unique(subset="timestamp", keep="first", maintain_order=True).sort(
        "timestamp"
    )
    dups = snapped.height - deduped.height

    split_after = timedelta(minutes=max(split_gap_minutes, 4 * step // 60))
    deduped = deduped.with_columns(
        (pl.col("timestamp").diff() > split_after)
        .fill_null(False)
        .cum_sum()
        .cast(pl.Int32)
        .alias("segment"),
        pl.lit(True).alias("observed"),
    )
    gridded = (
        deduped.upsample(time_column="timestamp", every=every, group_by="segment")
        .with_columns(
            pl.col("segment").forward_fill(),
            pl.col("observed").fill_null(False),
            *([pl.col("qc_dropout").fill_null(False)] if "qc_dropout" in deduped.columns else []),
        )
        .sort("timestamp")
    )
    report = GridReport(
        input_rows=input_rows,
        null_timestamp_rows=null_ts,
        step_seconds=step,
        snapped_timestamps=n_snapped,
        duplicates_dropped=dups,
        segments=int(gridded["segment"].n_unique()) if gridded.height else 0,
        inserted_missing_rows=gridded.height - deduped.height,
        output_rows=gridded.height,
    )
    return gridded, report
