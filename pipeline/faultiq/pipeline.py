"""End-to-end batch processing: raw CSV -> validated, gridded, feature-rich Parquet.

    load (mapping) -> validate -> regular grid -> operating state -> physics features -> Parquet

Every file gets a JSON report of what each step did, whether it was accepted or quarantined.
A run writes `manifest.json` linking each input's SHA-256 hash to its output's SHA-256 hash and the
pipeline version, so any processed file can be traced to its exact raw input. Re-running on the
same input produces byte-identical outputs (tested).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import polars as pl

import faultiq
from faultiq.features.physics import add_physics_features
from faultiq.ingestion.lbnl import UnknownFileError, lbnl_mapping, parse_file_name
from faultiq.ingestion.loader import SchemaError, file_sha256, load_csv
from faultiq.ingestion.mapping import PointMapping
from faultiq.preprocessing.grid import to_regular_grid
from faultiq.preprocessing.operating_state import THRESHOLDS, add_operating_state
from faultiq.validation.rules import Issue, ValidationResult, validate

log = logging.getLogger("faultiq.pipeline")


@dataclass
class FileOutcome:
    source_file: str
    source_sha256: str
    status: str
    report: str
    output: str | None = None
    output_sha256: str | None = None
    rows: int = 0
    label: dict[str, Any] | None = None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def process_file(
    path: Path, mapping: PointMapping, out_dir: Path, label: dict[str, Any] | None = None
) -> FileOutcome:
    """Process one CSV. Never raises for bad data: problems end up in the report as quarantine."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    report_path = out_dir / f"{stem}.report.json"
    report: dict[str, Any] = {
        "pipeline_version": faultiq.PIPELINE_VERSION,
        "source_file": path.name,
        "source_sha256": file_sha256(path),
        "mapping": mapping.name,
        "label": label,
    }
    outcome = FileOutcome(
        path.name, report["source_sha256"], "quarantined", report_path.name, label=label
    )

    try:
        loaded = load_csv(path, mapping)
    except SchemaError as exc:
        result = ValidationResult("quarantined", [Issue("error", "schema", str(exc))])
        report["validation"] = result.to_dict()
        _write_json(report_path, report)
        log.warning("file_quarantined", extra={"file": path.name, "reason": "schema"})
        return outcome

    report["load"] = loaded.report.to_dict()
    validation = validate(loaded)
    report["validation"] = validation.to_dict()
    if not validation.accepted:
        _write_json(report_path, report)
        log.warning(
            "file_quarantined",
            extra={
                "file": path.name,
                "errors": [i.code for i in validation.issues if i.severity == "error"],
            },
        )
        return outcome

    gridded, grid_report = to_regular_grid(loaded.data)
    processed = add_physics_features(add_operating_state(gridded))
    report["grid"] = grid_report.to_dict()
    report["operating_state"] = {
        "thresholds": THRESHOLDS,
        "mode_share": {
            str(row[0]): round(float(row[1]), 4)
            for row in processed["operating_mode"]
            .value_counts(normalize=True)
            .sort("operating_mode")
            .iter_rows()
        },
        "steady_share": round(float(processed.select(pl.col("steady").mean()).item() or 0), 4),
    }
    report["columns"] = processed.columns

    output_path = out_dir / f"{stem}.parquet"
    processed.write_parquet(output_path, compression="zstd", statistics=False)
    outcome.status = validation.status
    outcome.output = output_path.name
    outcome.output_sha256 = file_sha256(output_path)
    outcome.rows = processed.height
    report["output_file"] = outcome.output
    report["output_sha256"] = outcome.output_sha256
    _write_json(report_path, report)
    log.info(
        "file_processed", extra={"file": path.name, "status": outcome.status, "rows": outcome.rows}
    )
    return outcome


def write_manifest(out_dir: Path, outcomes: list[FileOutcome]) -> Path:
    manifest = {
        "pipeline_version": faultiq.PIPELINE_VERSION,
        "files": [asdict(o) for o in sorted(outcomes, key=lambda o: (o.report, o.source_file))],
        "summary": {
            status: sum(1 for o in outcomes if o.status == status)
            for status in ("accepted", "accepted_with_warnings", "quarantined")
        },
    }
    path = out_dir / "manifest.json"
    _write_json(path, manifest)
    return path


def process_lbnl(raw_root: Path, out_dir: Path) -> list[FileOutcome]:
    """Process every LBNL CSV under `raw_root` into `out_dir/<dataset>/`."""
    outcomes: list[FileOutcome] = []
    for path in sorted(raw_root.rglob("*.csv")):
        try:
            label = parse_file_name(path.name)
        except UnknownFileError:
            log.warning(
                "file_skipped", extra={"file": path.name, "reason": "not an LBNL file name"}
            )
            continue
        outcome = process_file(
            path, lbnl_mapping(label.dataset), out_dir / label.dataset, asdict(label)
        )
        outcome.report = f"{label.dataset}/{outcome.report}"
        if outcome.output:
            outcome.output = f"{label.dataset}/{outcome.output}"
        outcomes.append(outcome)
    write_manifest(out_dir, outcomes)
    return outcomes
