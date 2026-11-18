"""Reproducible loader for the LBNL RTU FDD data sets.

`load_lbnl_file` turns one raw CSV into a canonical, SI-unit Polars frame plus a `LoadReport` that
records every data-quality action taken. Raw files are only read, never modified. Nothing is dropped
or imputed silently: invalid values become null and are counted.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

import faultiq
from faultiq.ingestion.roles import EXCLUDED, MAPPINGS, Dataset, plausible_range

TS_SOURCE = "Datetime"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
NULL_TOKENS = ["NAN", "NaN", "nan", "NA", ""]
# Experimental-set logging dropouts: these three independent sensors all read exactly 0 deg F.
_DROPOUT_PROBES = ("RTU_OA_TEMP", "RTU_RA_TEMP", "TERM_RM_TEMP_102")


class UnknownFileError(ValueError):
    """The file name matches no documented LBNL naming pattern."""


class SchemaError(ValueError):
    """The file is missing columns that its dataset documents."""


@dataclass(frozen=True)
class FileLabel:
    source_name: str
    dataset: Dataset
    fault: str
    intensity: float | None
    intensity_unit: str | None
    season: str | None = None
    site: str | None = None

    @property
    def is_fault_free(self) -> bool:
        return self.fault == "fault_free"


_SIM_FAULTS = {
    "condfouling": ("condenser_fouling", "%"),
    "evapfouling": ("evaporator_fouling", "%"),
    "overcharge": ("refrigerant_overcharge", "%"),
    "undercharge": ("refrigerant_undercharge", "%"),
    "liquidpipe": ("liquid_line_restriction", "bar"),
    "suctionpipe": ("suction_line_restriction", "bar"),
}
_EXP_FAULTS = {
    "SA_temp_bias": ("sat_sensor_bias", "delta_C"),
    "Inc_Eco_SP": ("economizer_setpoint_offset", "delta_C"),
    "OA_damper_stuck": ("oa_damper_stuck", "%"),
}
_RE_SIM = re.compile(r"^RTU_sim_(?:(?P<base>baseline)|(?P<kind>[a-z]+?)(?P<val>\d+)(?:bar)?)\.csv$")
_RE_EXP = re.compile(
    r"^(?:(?P<free>ERTU)|(?P<kind>SA_temp_bias|Inc_Eco_SP|OA_damper_stuck)_(?P<val>-?\d+))"
    r"_(?P<season>Fall|Spring|Summer|Winter)_(?P<year>\d{4})\.csv$"
)
_RE_FIELD = re.compile(
    r"^Site(?P<site>\d+)_(?:(?P<free>Unfaulted)|(?P<staging>Staging_Fault)|Undercharged(?P<val>\d+))\.csv$"
)


def parse_file_name(name: str) -> FileLabel:
    """Derive dataset, fault and intensity from a documented LBNL file name."""
    if m := _RE_SIM.match(name):
        if m["base"]:
            return FileLabel(name, "simulated", "fault_free", None, None)
        if m["kind"] not in _SIM_FAULTS:
            raise UnknownFileError(f"unknown simulated fault in file name: {name}")
        fault, unit = _SIM_FAULTS[m["kind"]]
        return FileLabel(name, "simulated", fault, float(m["val"]), unit)
    if m := _RE_EXP.match(name):
        season = f"{m['season']}_{m['year']}"
        if m["free"]:
            return FileLabel(name, "experimental", "fault_free", None, None, season=season)
        fault, unit = _EXP_FAULTS[m["kind"]]
        return FileLabel(name, "experimental", fault, float(m["val"]), unit, season=season)
    if m := _RE_FIELD.match(name):
        site = f"site{m['site']}"
        if m["free"]:
            return FileLabel(name, "field", "fault_free", None, None, site=site)
        if m["staging"]:
            return FileLabel(name, "field", "compressor_staging", None, None, site=site)
        return FileLabel(name, "field", "refrigerant_undercharge", float(m["val"]), "%", site=site)
    raise UnknownFileError(f"file name matches no documented LBNL pattern: {name}")


@dataclass
class LoadReport:
    source_file: str
    sha256: str
    pipeline_version: str
    dataset: str
    rows: int = 0
    timestamp_unparsed: int = 0
    duplicate_timestamps: int = 0
    non_increasing_steps: int = 0
    gaps_over_1min: int = 0
    dropout_rows: int = 0
    unmapped_columns: list[str] = field(default_factory=list)
    excluded_columns: dict[str, str] = field(default_factory=dict)
    source_nulls: dict[str, int] = field(default_factory=dict)
    unparseable_values: dict[str, int] = field(default_factory=dict)
    infinite_values: dict[str, int] = field(default_factory=dict)
    out_of_range: dict[str, int] = field(default_factory=dict)
    final_nulls: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LoadedFile:
    label: FileLabel
    data: pl.DataFrame
    report: LoadReport


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_lbnl_file(path: Path) -> LoadedFile:
    """Load one LBNL CSV into canonical roles and SI units, with a full data-quality report."""
    label = parse_file_name(path.name)
    mapping = MAPPINGS[label.dataset]
    excluded = EXCLUDED[label.dataset]
    report = LoadReport(
        source_file=path.name,
        sha256=_sha256(path),
        pipeline_version=faultiq.PIPELINE_VERSION,
        dataset=label.dataset,
    )

    # Read every column as text so mixed int/float columns can't be inferred differently per file.
    raw = pl.read_csv(path, null_values=NULL_TOKENS, infer_schema_length=0)
    missing = [c for c in [TS_SOURCE, *mapping] if c not in raw.columns]
    if missing:
        raise SchemaError(f"{path.name}: missing documented columns {missing}")
    report.rows = raw.height
    report.unmapped_columns = sorted(
        c for c in raw.columns if c != TS_SOURCE and c not in mapping and c not in excluded
    )
    report.excluded_columns = {c: why for c, why in excluded.items() if c in raw.columns}

    # Timestamps: parse and audit regularity; never reorder or deduplicate silently.
    ts = raw[TS_SOURCE].str.strptime(pl.Datetime("us"), TS_FORMAT, strict=False)
    report.timestamp_unparsed = int(ts.null_count() - raw[TS_SOURCE].null_count())
    steps = ts.diff().dt.total_seconds().drop_nulls()
    report.duplicate_timestamps = int(ts.len() - ts.n_unique())
    report.non_increasing_steps = int((steps <= 0).sum())
    report.gaps_over_1min = int((steps > 60).sum())

    numeric = raw.select(
        [pl.col(c).cast(pl.Float64, strict=False).alias(c) for c in mapping]
        + (
            [
                pl.col(c).cast(pl.Float64, strict=False).alias(c)
                for c in _DROPOUT_PROBES
                if c in raw.columns and c not in mapping
            ]
        )
    )

    dropout = pl.Series("qc_dropout", [False] * raw.height)
    if label.dataset == "experimental" and all(c in numeric.columns for c in _DROPOUT_PROBES):
        dropout = (
            numeric.select(
                pl.all_horizontal([pl.col(c) == 0.0 for c in _DROPOUT_PROBES]).fill_null(False)
            )
            .to_series()
            .alias("qc_dropout")
        )
    report.dropout_rows = int(dropout.sum())

    out: dict[str, pl.Series] = {"timestamp": ts}
    for source, (role, convert) in mapping.items():
        text = raw[source]
        values = numeric[source]
        report.source_nulls[role] = int(text.null_count())
        report.unparseable_values[role] = int(values.null_count() - text.null_count())

        is_inf = values.is_infinite().fill_null(False)
        report.infinite_values[role] = int(is_inf.sum())
        values = pl.select(
            pl.when(is_inf | dropout).then(None).otherwise(values).alias(role)
        ).to_series()
        values = pl.select(convert(pl.lit(values)).alias(role)).to_series()

        bounds = plausible_range(role)
        if bounds is not None:
            bad = ((values < bounds.low) | (values > bounds.high)).fill_null(False)
            report.out_of_range[role] = int(bad.sum())
            values = pl.select(pl.when(bad).then(None).otherwise(values).alias(role)).to_series()
        report.final_nulls[role] = int(values.null_count())
        out[role] = values

    out["qc_dropout"] = dropout
    return LoadedFile(label=label, data=pl.DataFrame(out), report=report)
