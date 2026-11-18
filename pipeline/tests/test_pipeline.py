from __future__ import annotations

import json
import tomllib
from pathlib import Path

import polars as pl
import pytest

from faultiq.__main__ import main
from faultiq.ingestion.mapping import parse_mapping
from faultiq.pipeline import process_file, process_lbnl
from tests.helpers import USER_COLUMNS, USER_MAPPING_TOML, user_rows, write_csv

MAPPING = parse_mapping(tomllib.loads(USER_MAPPING_TOML))


def test_accepted_file_produces_parquet_report_and_hashes(tmp_path: Path) -> None:
    src = write_csv(tmp_path / "rtu.csv", USER_COLUMNS, user_rows(30))
    out = tmp_path / "out"
    outcome = process_file(src, MAPPING, out)
    assert outcome.status == "accepted"
    data = pl.read_parquet(out / "rtu.parquet")
    for column in (
        "timestamp",
        "sat",
        "observed",
        "segment",
        "operating_mode",
        "steady",
        "oaf_temp",
    ):
        assert column in data.columns
    report = json.loads((out / "rtu.report.json").read_text())
    assert report["source_sha256"] == outcome.source_sha256
    assert report["output_sha256"] == outcome.output_sha256
    assert report["validation"]["status"] == "accepted"
    assert report["grid"]["step_seconds"] == 60


def test_reprocessing_is_byte_identical(tmp_path: Path) -> None:
    src = write_csv(tmp_path / "rtu.csv", USER_COLUMNS, user_rows(60))
    first = process_file(src, MAPPING, tmp_path / "a")
    second = process_file(src, MAPPING, tmp_path / "b")
    assert first.output_sha256 == second.output_sha256
    assert (tmp_path / "a" / "rtu.report.json").read_text() == (
        tmp_path / "b" / "rtu.report.json"
    ).read_text()


def test_bad_file_is_quarantined_with_a_report_and_no_output(tmp_path: Path) -> None:
    rows = user_rows(5)
    rows[1][0], rows[2][0] = rows[2][0], rows[1][0]
    src = write_csv(tmp_path / "bad.csv", USER_COLUMNS, rows)
    outcome = process_file(src, MAPPING, tmp_path / "out")
    assert outcome.status == "quarantined"
    assert outcome.output is None
    assert not (tmp_path / "out" / "bad.parquet").exists()
    report = json.loads((tmp_path / "out" / "bad.report.json").read_text())
    assert report["validation"]["status"] == "quarantined"


def test_missing_mapped_column_is_quarantined_not_raised(tmp_path: Path) -> None:
    src = write_csv(tmp_path / "short.csv", USER_COLUMNS[:-2], [r[:-2] for r in user_rows(5)])
    outcome = process_file(src, MAPPING, tmp_path / "out")
    assert outcome.status == "quarantined"
    report = json.loads((tmp_path / "out" / "short.report.json").read_text())
    assert report["validation"]["issues"][0]["code"] == "schema"


def test_cli_draft_and_process(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = write_csv(tmp_path / "rtu.csv", USER_COLUMNS, user_rows(20))
    assert main(["draft-mapping", str(src), "--name", "rtu_7"]) == 0
    assert 'name = "rtu_7"' in capsys.readouterr().out
    mapping = tmp_path / "rtu.toml"
    mapping.write_text(USER_MAPPING_TOML)
    assert (
        main(["process", str(src), "--mapping", str(mapping), "--out", str(tmp_path / "out")]) == 0
    )
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["summary"]["accepted"] == 1


def test_cli_reports_mapping_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = write_csv(tmp_path / "rtu.csv", USER_COLUMNS, user_rows(5))
    mapping = tmp_path / "bad.toml"
    mapping.write_text(
        'name = "x"\n[timestamp]\ncolumn = "Timestamp"\n[points]\n'
        '"SAT (F)" = { role = "sat", unit = "TODO" }\n'
    )
    assert (
        main(["process", str(src), "--mapping", str(mapping), "--out", str(tmp_path / "out")]) == 2
    )
    assert "unknown unit" in capsys.readouterr().err


RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "LBNL_FDD_Data_Sets_RTU_all_3"


@pytest.mark.skipif(not RAW.exists(), reason="LBNL dataset not downloaded into data/raw")
def test_real_lbnl_field_files_process(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "Field RTU"
    raw.mkdir(parents=True)
    for name in ("Site1_Staging_Fault.csv", "Site2_Undercharged40.csv"):
        (raw / name).symlink_to(RAW / "Field RTU" / name)
    outcomes = process_lbnl(tmp_path / "raw", tmp_path / "out")
    assert [o.status for o in outcomes] == ["accepted_with_warnings", "accepted_with_warnings"]
    assert (tmp_path / "out" / "manifest.json").exists()
