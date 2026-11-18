"""Tests for the LBNL loader. Synthetic CSV fixtures only: the licensed raw data is never needed,
except for the optional smoke test at the bottom, which skips when data/raw is absent."""

from __future__ import annotations

from pathlib import Path

import pytest

from faultiq.ingestion.lbnl import (
    SchemaError,
    UnknownFileError,
    load_lbnl_file,
    parse_file_name,
)
from faultiq.ingestion.roles import EXPERIMENTAL, FIELD, SIMULATED


def write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> Path:
    lines = [",".join(columns)] + [",".join("" if v is None else str(v) for v in r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def ts(minute: int) -> str:
    return f"2020-01-01 00:{minute:02d}:00"


# ---------- file names ----------


@pytest.mark.parametrize(
    ("name", "dataset", "fault", "intensity", "unit", "season", "site"),
    [
        ("RTU_sim_baseline.csv", "simulated", "fault_free", None, None, None, None),
        ("RTU_sim_condfouling30.csv", "simulated", "condenser_fouling", 30.0, "%", None, None),
        (
            "RTU_sim_liquidpipe04bar.csv",
            "simulated",
            "liquid_line_restriction",
            4.0,
            "bar",
            None,
            None,
        ),
        (
            "RTU_sim_suctionpipe09bar.csv",
            "simulated",
            "suction_line_restriction",
            9.0,
            "bar",
            None,
            None,
        ),
        ("ERTU_Winter_2022.csv", "experimental", "fault_free", None, None, "Winter_2022", None),
        (
            "SA_temp_bias_-4_Fall_2020.csv",
            "experimental",
            "sat_sensor_bias",
            -4.0,
            "delta_C",
            "Fall_2020",
            None,
        ),
        (
            "Inc_Eco_SP_2_Spring_2021.csv",
            "experimental",
            "economizer_setpoint_offset",
            2.0,
            "delta_C",
            "Spring_2021",
            None,
        ),
        (
            "OA_damper_stuck_005_Summer_2021.csv",
            "experimental",
            "oa_damper_stuck",
            5.0,
            "%",
            "Summer_2021",
            None,
        ),
        ("Site1_Staging_Fault.csv", "field", "compressor_staging", None, None, None, "site1"),
        ("Site2_Undercharged40.csv", "field", "refrigerant_undercharge", 40.0, "%", None, "site2"),
        ("Site2_Unfaulted.csv", "field", "fault_free", None, None, None, "site2"),
    ],
)
def test_parse_file_name(name, dataset, fault, intensity, unit, season, site) -> None:  # type: ignore[no-untyped-def]
    label = parse_file_name(name)
    assert (label.dataset, label.fault, label.intensity, label.intensity_unit) == (
        dataset,
        fault,
        intensity,
        unit,
    )
    assert (label.season, label.site) == (season, site)
    assert label.is_fault_free == (fault == "fault_free")


@pytest.mark.parametrize(
    "name", ["RTU_sim_unknown10.csv", "random.csv", "OA_damper_stuck_050.csv", "Site1.csv"]
)
def test_unknown_file_names_are_rejected(name: str) -> None:
    with pytest.raises(UnknownFileError):
        parse_file_name(name)


# ---------- simulated ----------


def sim_file(tmp_path: Path, **overrides: object) -> Path:
    cols = ["Datetime", *SIMULATED]
    base = {c: 1.0 for c in SIMULATED}
    base.update(
        {
            "RTU_SA_TEMP": 32.0,
            "RTU_RA_TEMP": 212.0 - 140.0,
            "RTU_OA_TEMP": 50.0,
            "RTU_SA_FLOW": 1000.0,
            "RTU_REFG_SUCT_PRES": 14500000.0,
            "RTU_STG_STA": 0.1,
            "RTU_REFG_DISC_PRES": 25000000.0,
            "RTU_REFG_COND_PRES": 24000000.0,
            "ZA_TEMP": 72.0,
            "ZA_TEMP_SPT": 73.4,
            "RTU_SA_HUM": 50.0,
            "RTU_RA_HUM": 50.0,
            "RTU_OA_HUM": 50.0,
            "ZA_HUM": 50.0,
            "RTU_REFG_DISC_TEMP": 150.0,
            "RTU_REFG_COND_TEMP": 90.0,
            "RTU_REFG_SUCT_TEMP": 50.0,
        }
    )
    base.update(overrides)  # type: ignore[arg-type]
    rows = [[ts(i), *[base[c] for c in SIMULATED]] for i in range(3)]
    return write_csv(tmp_path / "RTU_sim_baseline.csv", cols, rows)


def test_simulated_units_are_converted(tmp_path: Path) -> None:
    lf = load_lbnl_file(sim_file(tmp_path))
    row = lf.data.row(0, named=True)
    assert row["sat"] == pytest.approx(0.0)
    assert row["rat"] == pytest.approx(22.2222, abs=1e-3)
    assert row["sa_flow"] == pytest.approx(0.471947)
    # psia x 1e5 -> kPa: 145 psia is about 999.7 kPa
    assert row["refg_suct_pres"] == pytest.approx(999.74, abs=0.01)
    assert row["comp_stage"] == pytest.approx(0.1)  # "off" stays 0.1, as recorded
    assert lf.report.rows == 3
    assert lf.report.pipeline_version
    assert len(lf.report.sha256) == 64


def test_loading_is_deterministic(tmp_path: Path) -> None:
    path = sim_file(tmp_path)
    first, second = load_lbnl_file(path), load_lbnl_file(path)
    assert first.data.equals(second.data)
    assert first.report.to_dict() == second.report.to_dict()


def test_missing_documented_column_is_a_schema_error(tmp_path: Path) -> None:
    cols = ["Datetime", *[c for c in SIMULATED if c != "RTU_SA_TEMP"]]
    path = write_csv(tmp_path / "RTU_sim_baseline.csv", cols, [[ts(0), *[1.0] * (len(cols) - 1)]])
    with pytest.raises(SchemaError, match="RTU_SA_TEMP"):
        load_lbnl_file(path)


def test_timestamp_problems_are_counted_not_fixed(tmp_path: Path) -> None:
    path = sim_file(tmp_path)
    lines = path.read_text().splitlines()
    lines[2] = lines[2].replace(ts(1), ts(0))  # duplicate of the first timestamp
    lines[3] = lines[3].replace(ts(2), ts(9))  # 9-minute gap after the duplicate
    lines.append(lines[1].replace(ts(0), "not-a-time"))
    path.write_text("\n".join(lines) + "\n")
    report = load_lbnl_file(path).report
    assert report.rows == 4
    assert report.timestamp_unparsed == 1
    assert report.duplicate_timestamps >= 1
    assert report.non_increasing_steps >= 1
    assert report.gaps_over_1min >= 1


# ---------- experimental ----------


def exp_file(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    cols = ["Datetime", *EXPERIMENTAL, "TERM_RM_TEMP_102"]
    normal = {c: 1 for c in EXPERIMENTAL}
    normal.update(
        {
            "RTU_OA_DMPR_DM": 50,
            "RTU_RA_DMPR_DM": 50.0,
            "RTU_OA_TEMP": 50.0,
            "RTU_MA_TEMP": 60.0,
            "RTU_SA_TEMP": 55.0,
            "RTU_RA_TEMP": 70.0,
            "RTU_SA_FLOW": 2000,
            "OCCU_MOD": 1,
            "TERM_RM_TEMP_HSPT": 68.0,
            "TERM_RM_TEMP_CSPT": 75.0,
            "TERM_RM_TEMP_102": 71.0,
        }
    )
    out = []
    for i, r in enumerate(rows):
        merged = {**normal, **r}
        out.append([ts(i), *[merged[c] for c in cols[1:]]])
    return write_csv(tmp_path / "OA_damper_stuck_050_Fall_2020.csv", cols, out)


def test_experimental_quality_issues_are_flagged(tmp_path: Path) -> None:
    path = exp_file(
        tmp_path,
        [
            {},  # normal row
            {"RTU_SA_TEMP": "NAN", "RTU_RA_TEMP": "NAN"},  # documented missing token
            {"RTU_SA_FLOW": "inf"},  # infinite airflow
            {
                "RTU_OA_TEMP": 0,
                "RTU_RA_TEMP": 0,
                "TERM_RM_TEMP_102": 0,
                "RTU_SA_TEMP": 0,
            },  # dropout
        ],
    )
    lf = load_lbnl_file(path)
    r, d = lf.report, lf.data
    assert d["oa_damper_cmd"][0] == pytest.approx(0.5)  # percent -> fraction
    assert r.source_nulls["sat"] == 1
    assert r.infinite_values["sa_flow"] == 1
    assert d["sa_flow"][2] is None
    assert r.dropout_rows == 1
    assert d["qc_dropout"].to_list() == [False, False, False, True]
    assert d["oat"][3] is None and d["sat"][3] is None  # dropout zeros never survive as 0 deg F
    assert "TERM_RM_TEMP_102" in r.unmapped_columns


# ---------- field ----------


def test_field_dead_sensor_excluded_and_invalid_pressure_nulled(tmp_path: Path) -> None:
    cols = ["Datetime", *FIELD, "ZA_HUM"]
    row = {c: 20.0 for c in FIELD}
    row.update({"RTU_REFG_DISC_PRES_2": -9.98, "RTU_SA_FLOW": 1000.0, "ZA_HUM": -15.0})
    path = write_csv(tmp_path / "Site2_Unfaulted.csv", cols, [[ts(0), *[row[c] for c in cols[1:]]]])
    lf = load_lbnl_file(path)
    assert "ZA_HUM" in lf.report.excluded_columns
    assert "zone_rh" not in lf.data.columns
    assert lf.report.out_of_range["refg_disc_pres_2"] == 1
    assert lf.data["refg_disc_pres_2"][0] is None
    assert lf.data["refg_suct_pres_1"][0] == pytest.approx(2000.0)  # bar -> kPa


# ---------- optional smoke test on the real dataset ----------

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "LBNL_FDD_Data_Sets_RTU_all_3"


@pytest.mark.skipif(not RAW.exists(), reason="LBNL dataset not downloaded into data/raw")
def test_real_dataset_file_names_all_parse() -> None:
    files = sorted(RAW.rglob("*.csv"))
    assert len(files) == 81
    datasets = [parse_file_name(p.name).dataset for p in files]
    assert (
        datasets.count("simulated"),
        datasets.count("experimental"),
        datasets.count("field"),
    ) == (25, 52, 4)
