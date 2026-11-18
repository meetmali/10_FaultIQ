"""Generic CSV loader: one raw file plus a point mapping -> canonical roles in SI units.

Raw files are only read, never modified. Nothing is dropped or imputed silently: every invalid
value becomes null and is counted in the `LoadReport`, which also records the file's SHA-256 hash
and the pipeline version so results can be traced back to their exact input.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

import faultiq
from faultiq.ingestion.mapping import PointMapping
from faultiq.ingestion.roles import UNITS, plausible_range


class SchemaError(ValueError):
    """The file lacks columns its mapping requires."""


@dataclass
class LoadReport:
    source_file: str
    sha256: str
    pipeline_version: str
    mapping: str
    rows: int = 0
    timestamp_unparsed: int = 0
    duplicate_timestamps: int = 0
    non_increasing_steps: int = 0
    gaps_over_1min: int = 0
    dropout_rows: int = 0
    unmapped_columns: list[str] = field(default_factory=list)
    excluded_columns: dict[str, str] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    source_nulls: dict[str, int] = field(default_factory=dict)
    unparseable_values: dict[str, int] = field(default_factory=dict)
    infinite_values: dict[str, int] = field(default_factory=dict)
    out_of_range: dict[str, int] = field(default_factory=dict)
    final_nulls: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LoadResult:
    data: pl.DataFrame
    report: LoadReport


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path, mapping: PointMapping) -> LoadResult:
    """Load one CSV into canonical roles and SI units, with a full data-quality report."""
    report = LoadReport(
        source_file=path.name,
        sha256=file_sha256(path),
        pipeline_version=faultiq.PIPELINE_VERSION,
        mapping=mapping.name,
    )
    # Read every column as text so mixed int/float columns can't be inferred differently per file.
    raw = pl.read_csv(path, null_values=list(mapping.null_tokens), infer_schema_length=0)
    required = [mapping.timestamp_column, *mapping.points, *mapping.dropout_probes]
    missing = [c for c in dict.fromkeys(required) if c not in raw.columns]
    if missing:
        raise SchemaError(
            f"{path.name}: missing columns required by mapping '{mapping.name}': {missing}"
        )
    report.rows = raw.height
    report.unmapped_columns = sorted(
        c
        for c in raw.columns
        if c != mapping.timestamp_column and c not in mapping.points and c not in mapping.excluded
    )
    report.excluded_columns = {c: why for c, why in mapping.excluded.items() if c in raw.columns}
    report.units = {p.role: p.unit for p in mapping.points.values()}

    # Timestamps: parse and audit regularity; never reorder or deduplicate here.
    text_ts = raw[mapping.timestamp_column]
    if mapping.timestamp_format:
        ts = text_ts.str.strptime(pl.Datetime("us"), mapping.timestamp_format, strict=False)
    else:
        ts = text_ts.str.to_datetime(strict=False).cast(pl.Datetime("us"))
    report.timestamp_unparsed = int(ts.null_count() - text_ts.null_count())
    steps = ts.diff().dt.total_seconds().drop_nulls()
    report.duplicate_timestamps = int(ts.len() - ts.n_unique())
    report.non_increasing_steps = int((steps <= 0).sum())
    report.gaps_over_1min = int((steps > 60).sum())

    numeric_cols = list(dict.fromkeys([*mapping.points, *mapping.dropout_probes]))
    numeric = raw.select([pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols])

    dropout = pl.Series("qc_dropout", [False] * raw.height, dtype=pl.Boolean)
    if mapping.dropout_probes:
        dropout = (
            numeric.select(
                pl.all_horizontal([pl.col(c) == 0.0 for c in mapping.dropout_probes]).fill_null(
                    False
                )
            )
            .to_series()
            .alias("qc_dropout")
        )
    report.dropout_rows = int(dropout.sum() or 0)

    out: dict[str, pl.Series] = {"timestamp": ts}
    for source, point in mapping.points.items():
        role = point.role
        values = numeric[source]
        report.source_nulls[role] = int(raw[source].null_count())
        report.unparseable_values[role] = int(values.null_count() - raw[source].null_count())

        is_inf = values.is_infinite().fill_null(False)
        report.infinite_values[role] = int(is_inf.sum())
        convert = UNITS[point.unit][1]
        values = pl.select(
            convert(pl.when(is_inf | dropout).then(None).otherwise(pl.lit(values))).alias(role)
        ).to_series()

        bounds = plausible_range(role)
        if bounds is not None:
            bad = ((values < bounds.low) | (values > bounds.high)).fill_null(False)
            report.out_of_range[role] = int(bad.sum())
            values = pl.select(pl.when(bad).then(None).otherwise(values).alias(role)).to_series()
        report.final_nulls[role] = int(values.null_count())
        out[role] = values

    out["qc_dropout"] = dropout
    return LoadResult(data=pl.DataFrame(out), report=report)
