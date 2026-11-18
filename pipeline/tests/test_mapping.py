from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from faultiq.ingestion.mapping import (
    MappingError,
    bundled_mapping,
    draft_mapping_toml,
    load_mapping,
    parse_mapping,
    suggest_roles,
)
from faultiq.ingestion.roles import base_role, role_kind
from tests.helpers import USER_MAPPING_TOML


def test_user_mapping_loads(tmp_path: Path) -> None:
    path = tmp_path / "rtu.toml"
    path.write_text(USER_MAPPING_TOML)
    m = load_mapping(path)
    assert m.name == "test_rtu"
    assert m.points["SAT (F)"].role == "sat"
    assert m.points["OA Damper %"].unit == "percent"
    assert m.excluded == {"Spare AI": "not connected"}


@pytest.mark.parametrize("name", ["lbnl_simulated", "lbnl_experimental", "lbnl_field"])
def test_bundled_lbnl_mappings_are_valid(name: str) -> None:
    m = bundled_mapping(name)
    assert m.timestamp_column == "Datetime"
    assert len(m.points) >= 24


def test_experimental_mapping_includes_vav_discharge_temperatures() -> None:
    roles = {p.role for p in bundled_mapping("lbnl_experimental").points.values()}
    assert {f"vav_sat_{r}" for r in ("102", "206")} <= roles


def test_every_problem_is_reported_at_once() -> None:
    data = tomllib.loads(
        """
        name = "bad"
        [timestamp]
        column = "t"
        [points]
        "A" = { role = "not_a_role", unit = "degF" }
        "B" = { role = "sat", unit = "TODO" }
        "C" = { role = "sat", unit = "W" }
        "D" = { role = "oat", unit = "degF" }
        "E" = { role = "oat", unit = "degC" }
        "F" = { role = "rat" }
        """
    )
    with pytest.raises(MappingError) as exc:
        parse_mapping(data)
    message = str(exc.value)
    for fragment in ('unknown role "not_a_role"', 'unknown unit "TODO"', "is a power unit",
                     'already mapped from "D"', "needs both role and unit"):  # fmt: skip
        assert fragment in message


def test_mapped_and_excluded_overlap_is_rejected() -> None:
    data = {
        "name": "x",
        "timestamp": {"column": "t"},
        "points": {"A": {"role": "sat", "unit": "degC"}},
        "excluded": {"A": "dead"},
    }
    with pytest.raises(MappingError, match="both mapped and excluded"):
        parse_mapping(data)


def test_invalid_toml_is_a_mapping_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("name = ")
    with pytest.raises(MappingError, match="not valid TOML"):
        load_mapping(path)


def test_role_suffixes() -> None:
    assert base_role("power_comp_1") == "power_comp"
    assert base_role("vav_sat_102") == "vav_sat"
    assert base_role("zone_temp_sp") == "zone_temp_sp"
    assert role_kind("refg_suct_pres_2") == "pressure"
    assert base_role("nonsense") is None


@pytest.mark.parametrize(
    ("column", "role"),
    [
        ("SAT", "sat"), ("DA-T", "sat"), ("Supply Air Temp", "sat"), ("RTU_SA_TEMP", "sat"),
        ("OAT", "oat"), ("Outside Air Temperature", "oat"), ("RTU_OA_TEMP", "oat"),
        ("RA Temp", "rat"), ("MAT", "mat"), ("Zone Temp", "zone_temp"),
        ("Zone Temp Setpoint", "zone_temp_sp"), ("ZA_TEMP_SPT", "zone_temp_sp"),
        ("OA Damper Cmd", "oa_damper_cmd"), ("RTU_OA_DMPR_DM", "oa_damper_cmd"),
        ("Comp Stage", "comp_stage"), ("RTU_STG_STA", "comp_stage"), ("Occupied Mode", "occupied"),
        ("RTU_COMP_WATT_1", "power_comp_1"), ("Supply Fan kW", "power_fan"),
    ],
)  # fmt: skip
def test_suggestions_for_common_point_names(column: str, role: str) -> None:
    assert suggest_roles([column])[column].role == role


def test_first_column_keeps_a_role() -> None:
    suggestions = suggest_roles(["SAT", "DA-T"])
    assert suggestions["SAT"].role == "sat"
    assert "DA-T" not in suggestions


def test_draft_needs_review_before_it_loads(tmp_path: Path) -> None:
    draft = draft_mapping_toml(["Timestamp", "SAT (°F)", "Outside Air Temp", "Mystery 7"])
    assert 'column = "Timestamp"' in draft
    assert '"SAT (°F)" = { role = "sat", unit = "degF" }' in draft
    assert '"Outside Air Temp" = { role = "oat", unit = "TODO" }' in draft
    assert '# "Mystery 7"' in draft
    path = tmp_path / "draft.toml"
    path.write_text(draft)
    with pytest.raises(MappingError, match="TODO"):
        load_mapping(path)
