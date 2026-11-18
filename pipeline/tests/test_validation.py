from __future__ import annotations

import tomllib
from pathlib import Path

from faultiq.ingestion.loader import load_csv
from faultiq.ingestion.mapping import parse_mapping
from faultiq.validation.rules import validate
from tests.helpers import USER_COLUMNS, USER_MAPPING_TOML, minutes, user_rows, write_csv

MAPPING = parse_mapping(tomllib.loads(USER_MAPPING_TOML))


def codes(result) -> set[str]:  # type: ignore[no-untyped-def]
    return {i.code for i in result.issues}


def test_clean_file_is_accepted(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "ok.csv", USER_COLUMNS, user_rows(30))
    result = validate(load_csv(path, MAPPING))
    assert result.status == "accepted"
    assert result.issues == []


def test_units_are_converted_by_mapping(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "ok.csv", USER_COLUMNS, user_rows(3))
    row = load_csv(path, MAPPING).data.row(0, named=True)
    assert abs(row["sat"] - 12.7778) < 1e-3  # 55 F
    assert row["oa_damper_cmd"] == 0.1  # 10 %
    assert row["power_fan"] == 1200.0  # 1.2 kW


def test_empty_file_is_quarantined(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "empty.csv", USER_COLUMNS, [])
    result = validate(load_csv(path, MAPPING))
    assert result.status == "quarantined"
    assert "empty_file" in codes(result)


def test_out_of_order_timestamps_are_quarantined(tmp_path: Path) -> None:
    rows = user_rows(5)
    rows[2][0], rows[3][0] = rows[3][0], rows[2][0]
    result = validate(load_csv(write_csv(tmp_path / "order.csv", USER_COLUMNS, rows), MAPPING))
    assert result.status == "quarantined"
    assert "timestamps_out_of_order" in codes(result)
    assert any("Sort the export by time" in i.message for i in result.issues)


def test_missing_required_role_is_quarantined(tmp_path: Path) -> None:
    from dataclasses import replace

    no_comp = replace(
        MAPPING, points={k: v for k, v in MAPPING.points.items() if v.role != "comp_stage"}
    )
    path = write_csv(tmp_path / "nocomp.csv", USER_COLUMNS, user_rows(5))
    result = validate(load_csv(path, no_comp))
    assert result.status == "quarantined"
    assert any("comp_stage or power_comp" in i.message for i in result.issues)


def test_mostly_empty_required_role_is_quarantined(tmp_path: Path) -> None:
    rows = user_rows(10)
    for r in rows[:8]:
        r[1] = "NAN"
    result = validate(load_csv(write_csv(tmp_path / "sat.csv", USER_COLUMNS, rows), MAPPING))
    assert result.status == "quarantined"
    assert "required_role_mostly_empty" in codes(result)


def test_imperfections_are_warnings_not_errors(tmp_path: Path) -> None:
    rows = user_rows(40)
    rows[5][1] = "inf"  # infinite SAT
    rows[6][2] = 500.0  # implausible OAT (500 F)
    rows[7][3] = "abc"  # unreadable RAT
    rows[9][0] = rows[8][0]  # duplicate timestamp
    for r in rows[20:24]:
        r[4] = "NAN"  # 10% missing MAT
    rows = rows[:30] + [
        [ts, *r[1:]] for ts, r in zip(minutes(10, "2024-06-01 09:00:00"), rows[30:], strict=True)
    ]
    result = validate(load_csv(write_csv(tmp_path / "messy.csv", USER_COLUMNS, rows), MAPPING))
    assert result.status == "accepted_with_warnings"
    expected = {"infinite_values", "out_of_range_values", "unreadable_values"}
    expected |= {"duplicate_timestamps", "gaps", "missing_values"}
    assert expected <= codes(result)
    assert all(i.severity == "warning" for i in result.issues)
