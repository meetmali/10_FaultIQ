from __future__ import annotations

from datetime import datetime

import polars as pl

from faultiq.preprocessing.grid import detect_step_seconds, to_regular_grid
from faultiq.preprocessing.operating_state import STEADY_DELAY_MINUTES, add_operating_state


def frame(timestamps: list[str], **cols: list[object]) -> pl.DataFrame:
    ts = pl.Series(
        "timestamp", [datetime.fromisoformat(t) for t in timestamps], dtype=pl.Datetime("us")
    )
    return pl.DataFrame({"timestamp": ts, **cols, "qc_dropout": [False] * len(timestamps)})


def test_missing_minutes_are_inserted_and_flagged_not_filled() -> None:
    df = frame(
        ["2024-01-01 00:00:00", "2024-01-01 00:01:00", "2024-01-01 00:04:00"],
        sat=[12.0, 12.5, 13.0],
    )
    out, rep = to_regular_grid(df)
    assert out.height == 5
    assert out["observed"].to_list() == [True, True, False, False, True]
    assert out["sat"].to_list() == [12.0, 12.5, None, None, 13.0]  # never interpolated
    assert rep.inserted_missing_rows == 2
    assert rep.segments == 1


def test_long_gap_starts_a_new_segment_without_filler_rows() -> None:
    df = frame(
        ["2024-01-01 00:00:00", "2024-01-01 00:01:00", "2024-01-03 00:00:00"], sat=[1.0, 2.0, 3.0]
    )
    out, rep = to_regular_grid(df, split_gap_minutes=60)
    assert out.height == 3
    assert out["segment"].to_list() == [0, 0, 1]
    assert rep.segments == 2
    assert rep.inserted_missing_rows == 0


def test_duplicates_keep_first_and_are_counted() -> None:
    df = frame(
        ["2024-01-01 00:00:00", "2024-01-01 00:00:00", "2024-01-01 00:01:00"], sat=[1.0, 9.0, 2.0]
    )
    out, rep = to_regular_grid(df)
    assert out["sat"].to_list() == [1.0, 2.0]
    assert rep.duplicates_dropped == 1


def test_fifteen_minute_exports_keep_their_own_interval() -> None:
    df = frame(
        ["2024-01-01 00:00:00", "2024-01-01 00:15:00", "2024-01-01 00:45:00"], sat=[1.0, 2.0, 3.0]
    )
    assert detect_step_seconds(df["timestamp"]) == 900
    out, rep = to_regular_grid(df)
    assert rep.step_seconds == 900
    assert out.height == 4  # 00:30 inserted as missing


def test_timestamps_are_snapped_to_the_grid() -> None:
    df = frame(
        ["2024-01-01 00:00:00", "2024-01-01 00:01:00", "2024-01-01 00:02:02"], sat=[1.0, 2.0, 3.0]
    )
    out, rep = to_regular_grid(df)
    assert rep.snapped_timestamps == 1
    assert out["timestamp"][-1] == datetime(2024, 1, 1, 0, 2)


def states(**cols: list[object]) -> pl.DataFrame:
    n = len(next(iter(cols.values())))
    ts = [f"2024-01-01 00:{i:02d}:00" for i in range(n)]
    gridded, _ = to_regular_grid(frame(ts, **cols))
    return add_operating_state(gridded)


def test_modes_from_equipment_signals() -> None:
    out = states(
        sa_flow=[0.0, 1.0, 1.0, 1.0, 1.0, 1.0, None],
        comp_stage=[0.1, 0.1, 0.1, 1.0, 1.0, 0.1, 1.0],
        oa_damper_cmd=[0.1, 0.1, 0.5, 0.5, 0.1, 0.1, 0.1],
        gas_flow=[0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0],
    )
    assert out["operating_mode"].cast(pl.Utf8).to_list() == [
        "off", "fan_only", "economizer", "economizer_cooling", "cooling", "heating", "unknown",
    ]  # fmt: skip


def test_compressor_from_circuit_power_when_no_stage_signal() -> None:
    out = states(power_fan=[300.0, 300.0], power_comp_1=[0.0, 0.0], power_comp_2=[0.0, 3000.0])
    assert out["compressor_on"].to_list() == [False, True]


def test_steady_only_after_the_delay_and_clock_restarts_on_mode_change() -> None:
    n = 25
    stage = [1.0] * 15 + [0.1] * 10  # cooling for 15 min, then fan only
    out = states(sa_flow=[1.0] * n, comp_stage=stage)
    steady = out["steady"].to_list()
    assert steady[STEADY_DELAY_MINUTES - 1] is False
    assert steady[STEADY_DELAY_MINUTES] is True
    assert out["mode_minutes"][15] == 0.0  # new mode
    assert steady[15] is False and steady[24] is False  # only 9 minutes into fan_only


def test_off_is_never_steady() -> None:
    out = states(sa_flow=[0.0] * 20, comp_stage=[0.1] * 20)
    assert not any(out["steady"].to_list())


def test_unobserved_minutes_are_unknown_and_break_the_run() -> None:
    df = frame(
        [f"2024-01-01 00:{i:02d}:00" for i in [*range(8), *range(10, 25)]],
        sa_flow=[1.0] * 23,
        comp_stage=[1.0] * 23,
    )
    gridded, _ = to_regular_grid(df)
    out = add_operating_state(gridded)
    assert out.filter(~pl.col("observed"))["operating_mode"].cast(pl.Utf8).to_list() == [
        "unknown",
        "unknown",
    ]
    assert out.filter(pl.col("timestamp") == datetime(2024, 1, 1, 0, 10))["mode_minutes"][0] == 0.0
