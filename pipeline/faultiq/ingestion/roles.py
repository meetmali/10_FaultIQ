"""Canonical sensor roles, units, conversions and plausible ranges (see docs/data-dictionary.md).

Every source column is mapped to a *role* (what it measures) and a *unit* (how it is recorded).
The loader converts each unit to its kind's canonical SI unit. A role may carry a numeric suffix
for circuits or rooms, for example `power_comp_1` or `vav_sat_102`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import polars as pl

Converter = Callable[[pl.Expr], pl.Expr]


def _same(e: pl.Expr) -> pl.Expr:
    return e


# unit name -> (kind, converter to the kind's canonical unit)
UNITS: dict[str, tuple[str, Converter]] = {
    "degC": ("temperature", _same),
    "degF": ("temperature", lambda e: (e - 32.0) * 5.0 / 9.0),
    "K": ("temperature", lambda e: e - 273.15),
    "kPa": ("pressure", _same),
    "Pa": ("pressure", lambda e: e / 1000.0),
    "bar": ("pressure", lambda e: e * 100.0),
    "psi": ("pressure", lambda e: e * 6.894757),
    # LBNL simulated set: documented as Pa, recorded as psia x 1e5 (Phase 1 finding).
    "psia_e5": ("pressure", lambda e: e / 1e5 * 6.894757),
    "m3/s": ("flow", _same),
    "cfm": ("flow", lambda e: e * 0.000471947),
    "L/s": ("flow", lambda e: e / 1000.0),
    "%RH": ("humidity", _same),
    "fraction": ("fraction", _same),
    "percent": ("fraction", lambda e: e / 100.0),
    "W": ("power", _same),
    "kW": ("power", lambda e: e * 1000.0),
    "SCFM": ("gas", _same),
    "0/1": ("flag", _same),
}

CANONICAL_UNIT = {
    "temperature": "degC",
    "pressure": "kPa",
    "flow": "m3/s",
    "humidity": "%RH",
    "fraction": "fraction",
    "power": "W",
    "gas": "SCFM",
    "flag": "0/1",
}

_TEMPS = [
    "oat", "rat", "mat", "sat", "zone_temp", "zone_temp_sp", "zone_heat_sp", "zone_cool_sp",
    "cond_leaving_air_temp", "vav_sat", "refg_disc_temp", "refg_suct_temp", "refg_cond_temp",
]  # fmt: skip
ROLE_KIND: dict[str, str] = {
    **{r: "temperature" for r in _TEMPS},
    **{r: "pressure" for r in ("refg_disc_pres", "refg_suct_pres", "refg_cond_pres")},
    **{r: "flow" for r in ("sa_flow", "ra_flow", "oa_flow")},
    **{r: "humidity" for r in ("sa_rh", "ra_rh", "oa_rh", "ma_rh", "zone_rh")},
    **{r: "fraction" for r in ("oa_damper_cmd", "ra_damper_cmd", "comp_stage")},
    "occupied": "flag",
    **{
        r: "power"
        for r in (
            "power_total",
            "power_comp",
            "power_fan",
            "power_hvac",
            "power_vav",
            "cap_sensible",
            "cap_total",
        )
    },
    "gas_flow": "gas",
}

# Roles a typical building automation system records (ADR 0018: "basic points").
BASIC_ROLES = frozenset(
    {"oat", "rat", "mat", "sat", "zone_temp", "zone_temp_sp", "zone_heat_sp", "zone_cool_sp",
     "oa_damper_cmd", "ra_damper_cmd", "comp_stage", "occupied"}
)  # fmt: skip

_ROLE_RE = re.compile(r"^(?P<base>[a-z_]+?)(?:_(?P<index>\d+))?$")


def base_role(role: str) -> str | None:
    """`power_comp_1` -> `power_comp`; returns None for an unknown role."""
    m = _ROLE_RE.match(role)
    if m is None:
        return None
    base = m["base"]
    return base if base in ROLE_KIND else None


def role_kind(role: str) -> str | None:
    base = base_role(role)
    return ROLE_KIND[base] if base else None


@dataclass(frozen=True)
class RoleRange:
    low: float
    high: float


_RANGES = {
    "temperature": RoleRange(-40.0, 80.0),
    "pressure": RoleRange(0.0, 6000.0),
    "flow": RoleRange(0.0, 10.0),
    "humidity": RoleRange(0.0, 100.0),
    "fraction": RoleRange(0.0, 1.0),
    "flag": RoleRange(0.0, 1.0),
    "power": RoleRange(0.0, 100_000.0),
}
_REFRIGERANT_TEMP = RoleRange(-40.0, 150.0)


def plausible_range(role: str) -> RoleRange | None:
    """Physically plausible range in canonical units. Values outside become null and are counted."""
    base = base_role(role)
    if base is None:
        return None
    if base.startswith("refg_") and base.endswith("_temp"):
        return _REFRIGERANT_TEMP
    return _RANGES.get(ROLE_KIND[base])
