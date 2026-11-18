"""LBNL RTU FDD data sets: labels from file names, loading through the bundled point mappings.

The generic loader (`faultiq.ingestion.loader`) does the work; this module only adds what is
specific to LBNL: parsing fault labels from documented file names and picking the right mapping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import polars as pl

from faultiq.ingestion.loader import LoadReport, SchemaError, load_csv
from faultiq.ingestion.mapping import PointMapping, bundled_mapping

Dataset = Literal["simulated", "experimental", "field"]
__all__ = [
    "FileLabel",
    "LoadedFile",
    "SchemaError",
    "UnknownFileError",
    "lbnl_mapping",
    "load_lbnl_file",
    "parse_file_name",
]


class UnknownFileError(ValueError):
    """The file name matches no documented LBNL naming pattern."""


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
class LoadedFile:
    label: FileLabel
    data: pl.DataFrame
    report: LoadReport


def lbnl_mapping(dataset: Dataset) -> PointMapping:
    return bundled_mapping(f"lbnl_{dataset}")


def load_lbnl_file(path: Path) -> LoadedFile:
    """Load one LBNL CSV into canonical roles and SI units, with a full data-quality report."""
    label = parse_file_name(path.name)
    result = load_csv(path, lbnl_mapping(label.dataset))
    return LoadedFile(label=label, data=result.data, report=result.report)
