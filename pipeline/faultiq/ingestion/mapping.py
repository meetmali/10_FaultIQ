"""Point mappings: which source column is which sensor role, in which unit (ADR 0019).

A mapping is a small TOML file, one per unit of equipment. The three LBNL datasets ship as bundled
mappings in `faultiq/ingestion/mappings/`; a user's BAS export gets its own file, which
`draft_mapping_toml` can start from by suggesting roles from common point names.

    name = "rtu_3"
    [timestamp]
    column = "Timestamp"
    format = "%Y-%m-%d %H:%M:%S"   # optional; inferred when omitted
    [points]
    "SAT" = { role = "sat", unit = "degF" }
    [excluded]
    "Spare_AI_4" = "not connected"
    [quality]
    null_tokens = ["NAN", ""]
    dropout_probes = []
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from faultiq.ingestion.roles import UNITS, role_kind

DEFAULT_NULL_TOKENS = ("NAN", "NaN", "nan", "NA", "")


class MappingError(ValueError):
    """The mapping file is malformed or inconsistent. The message says what to fix."""


@dataclass(frozen=True)
class Point:
    role: str
    unit: str


@dataclass(frozen=True)
class PointMapping:
    name: str
    timestamp_column: str
    timestamp_format: str | None
    points: dict[str, Point]
    excluded: dict[str, str] = field(default_factory=dict)
    null_tokens: tuple[str, ...] = DEFAULT_NULL_TOKENS
    dropout_probes: tuple[str, ...] = ()


def parse_mapping(data: dict[str, Any], source: str = "mapping") -> PointMapping:
    """Validate a decoded mapping and return it, or raise MappingError listing every problem."""
    problems: list[str] = []
    name = data.get("name")
    if not isinstance(name, str) or not name:
        problems.append("`name` must be a non-empty string")
    ts = data.get("timestamp", {})
    ts_col = ts.get("column") if isinstance(ts, dict) else None
    if not isinstance(ts_col, str) or not ts_col:
        problems.append("`[timestamp] column` must name the timestamp column")
    ts_fmt = ts.get("format") if isinstance(ts, dict) else None
    if ts_fmt is not None and not isinstance(ts_fmt, str):
        problems.append("`[timestamp] format` must be a strftime string")

    raw_points = data.get("points", {})
    if not isinstance(raw_points, dict) or not raw_points:
        problems.append("`[points]` must map at least one column")
        raw_points = {}
    points: dict[str, Point] = {}
    seen_roles: dict[str, str] = {}
    for column, spec in raw_points.items():
        if not isinstance(spec, dict) or "role" not in spec or "unit" not in spec:
            problems.append(
                f'"{column}": needs both role and unit, e.g. {{ role = "sat", unit = "degF" }}'
            )
            continue
        role, unit = str(spec["role"]), str(spec["unit"])
        kind = role_kind(role)
        if kind is None:
            problems.append(f'"{column}": unknown role "{role}" (see docs/data-dictionary.md)')
            continue
        if unit not in UNITS:
            problems.append(
                f'"{column}": unknown unit "{unit}" (allowed: {", ".join(sorted(UNITS))})'
            )
            continue
        if UNITS[unit][0] != kind:
            problems.append(
                f'"{column}": unit "{unit}" is a {UNITS[unit][0]} unit '
                f'but role "{role}" is a {kind}'
            )
            continue
        if role in seen_roles:
            problems.append(
                f'"{column}": role "{role}" is already mapped from "{seen_roles[role]}"'
            )
            continue
        seen_roles[role] = column
        points[column] = Point(role, unit)

    excluded = data.get("excluded", {})
    if not isinstance(excluded, dict) or not all(isinstance(v, str) for v in excluded.values()):
        problems.append("`[excluded]` must map column names to a reason string")
        excluded = {}
    overlap = set(excluded) & set(points)
    if overlap:
        problems.append(f"columns both mapped and excluded: {sorted(overlap)}")

    quality = data.get("quality", {})
    null_tokens = tuple(quality.get("null_tokens", DEFAULT_NULL_TOKENS))
    dropout_probes = tuple(quality.get("dropout_probes", ()))

    if problems:
        raise MappingError(f"{source}: " + "; ".join(problems))
    if not isinstance(name, str) or not isinstance(ts_col, str):  # pragma: no cover, checked above
        raise MappingError(f"{source}: name and timestamp column are required")
    return PointMapping(
        name=name,
        timestamp_column=ts_col,
        timestamp_format=ts_fmt,
        points=points,
        excluded=dict(excluded),
        null_tokens=null_tokens,
        dropout_probes=dropout_probes,
    )


def load_mapping(path: Path) -> PointMapping:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise MappingError(f"{path.name}: not valid TOML ({exc})") from exc
    return parse_mapping(data, source=path.name)


def bundled_mapping(name: str) -> PointMapping:
    """One of the mappings shipped with FaultIQ, e.g. `lbnl_simulated`."""
    text = resources.files("faultiq.ingestion.mappings").joinpath(f"{name}.toml").read_text("utf-8")
    return parse_mapping(tomllib.loads(text), source=f"{name}.toml")


# ------------------------------------------------------------------ suggestions

# (role, pattern) in priority order: setpoints and dampers before plain temperatures.
_SUGGEST: list[tuple[str, str]] = [
    (
        "zone_temp_sp",
        r"(zone|za|zn|space|room)_?(temp|t)?_?(sp|spt|stpt|setpoint)|clg_?(sp|setpoint)",
    ),
    (
        "oa_damper_cmd",
        r"(oa|outside_?air|outdoor_?air|econ(omizer)?)_?d(mpr|amper|mp)?(_?(cmd|pos|dm|signal|out))?",
    ),
    ("ra_damper_cmd", r"(ra|return_?air)_?d(mpr|amper|mp)(_?(cmd|pos|dm|signal|out))?"),
    ("power_fan", r"(sa_?)?fan_?(watt|watts|power|kw)"),
    ("power_comp", r"comp(ressor)?_?(watt|watts|power|kw)"),
    ("power_total", r"(rtu_?)?tot(al)?_?(watt|watts|power|kw)"),
    (
        "comp_stage",
        r"comp(ressor)?_?(stage|stg|sta|status|cmd)|stg_?sta|(clg|dx|cool(ing)?)_?stage",
    ),
    ("occupied", r"occ(u)?(_?mod(e)?)?|occupied|occupancy"),
    ("sa_flow", r"(sa|supply_?air|da|discharge_?air)_?(flow|cfm)"),
    ("oat", r"oat|osat|(oa|osa|outside_?air|outdoor_?air)_?t(emp(erature)?)?"),
    ("rat", r"rat|(ra|return_?air)_?t(emp(erature)?)?"),
    ("mat", r"mat|(ma|mixed_?air)_?t(emp(erature)?)?"),
    ("sat", r"sat|dat|(sa|da|supply_?air|discharge_?air)_?t(emp(erature)?)?"),
    ("zone_temp", r"zat|znt|(zone|za|zn|space|room)_?t(emp(erature)?)?"),
    ("sa_rh", r"(sa|supply_?air)_?(rh|hum(idity)?)"),
    ("ra_rh", r"(ra|return_?air)_?(rh|hum(idity)?)"),
    ("oa_rh", r"(oa|outside_?air|outdoor_?air)_?(rh|hum(idity)?)"),
    ("zone_rh", r"(zone|za|zn|space|room)_?(rh|hum(idity)?)"),
]
_SUGGEST_RE = [(role, re.compile(rf"(^|_)({pat})($|_)")) for role, pat in _SUGGEST]
_TS_RE = re.compile(r"(^|_)(datetime|timestamp|time_?stamp|date_?time|date|time)($|_)")


def _normalise(name: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", name.lower())).strip("_")


def _unit_hint(name: str) -> str | None:
    low = name.lower()
    if "°f" in low or "degf" in low or re.search(r"[\(\[]\s*f\s*[\)\]]", low):
        return "degF"
    if "°c" in low or "degc" in low or re.search(r"[\(\[]\s*c\s*[\)\]]", low):
        return "degC"
    if "cfm" in low:
        return "cfm"
    if "kw" in low:
        return "kW"
    return None


@dataclass(frozen=True)
class Suggestion:
    role: str
    unit_hint: str | None


# Roles that can repeat per circuit or room: a trailing number in the column name is kept.
_INDEXED = {"power_comp", "zone_temp", "zone_rh"}
_TRAILING_INDEX = re.compile(r"_(\d+)$")


def suggest_roles(columns: list[str]) -> dict[str, Suggestion]:
    """Suggest a role for each recognisable column. The first column to claim a role keeps it."""
    out: dict[str, Suggestion] = {}
    taken: set[str] = set()
    for column in columns:
        norm = _normalise(column)
        for role, rx in _SUGGEST_RE:
            if not rx.search(norm):
                continue
            index = _TRAILING_INDEX.search(norm)
            candidate = f"{role}_{index[1]}" if role in _INDEXED and index else role
            if candidate in taken:
                continue
            out[column] = Suggestion(candidate, _unit_hint(column))
            taken.add(candidate)
            break
    return out


def guess_timestamp_column(columns: list[str]) -> str | None:
    for column in columns:
        if _TS_RE.search(_normalise(column)):
            return column
    return None


def draft_mapping_toml(columns: list[str], name: str = "my_rtu") -> str:
    """A starting mapping for a user's export. Every unit is TODO until a person checks it."""
    ts = guess_timestamp_column(columns)
    suggestions = suggest_roles([c for c in columns if c != ts])
    lines = [
        "# Draft mapping generated by FaultIQ. Check every role and replace every TODO unit",
        "# before use: FaultIQ refuses to load a mapping that still contains TODO.",
        f'name = "{name}"',
        "",
        "[timestamp]",
        f'column = "{ts or "TODO"}"',
        '# format = "%Y-%m-%d %H:%M:%S"   # optional; inferred when omitted',
        "",
        "[points]",
    ]
    for column, s in suggestions.items():
        lines.append(f'"{column}" = {{ role = "{s.role}", unit = "{s.unit_hint or "TODO"}" }}')
    unknown = [c for c in columns if c != ts and c not in suggestions]
    if unknown:
        lines += ["", "# Not recognised. Map them in [points] or list them in [excluded]:"]
        lines += [f'# "{c}" = {{ role = "?", unit = "?" }}' for c in unknown]
    return "\n".join(lines) + "\n"
