"""Canonical sensor roles and the LBNL column-to-role mappings (see docs/data-dictionary.md).

Every mapping here was verified against the downloaded files on 2026-11-18. Where the files
contradict the LBNL documentation (pressure unit, damper scale), the mapping follows the files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import polars as pl

Dataset = Literal["simulated", "experimental", "field"]
Converter = Callable[[pl.Expr], pl.Expr]


def f_to_c(e: pl.Expr) -> pl.Expr:
    return (e - 32.0) * 5.0 / 9.0


def cfm_to_m3s(e: pl.Expr) -> pl.Expr:
    return e * 0.000471947


def psia_e5_to_kpa(e: pl.Expr) -> pl.Expr:
    # Simulated set: documented as Pa, but values are psia x 1e5 (verified by suction superheat).
    return e / 1e5 * 6.894757


def bar_to_kpa(e: pl.Expr) -> pl.Expr:
    return e * 100.0


def percent_to_fraction(e: pl.Expr) -> pl.Expr:
    return e / 100.0


def same(e: pl.Expr) -> pl.Expr:
    return e


@dataclass(frozen=True)
class RoleRange:
    low: float
    high: float


# Physically plausible ranges in canonical units. Values outside become null and are counted.
_AIR_T = RoleRange(-40.0, 80.0)
_REFG_T = RoleRange(-40.0, 150.0)
_PRES = RoleRange(0.0, 6000.0)
_RH = RoleRange(0.0, 100.0)
_FLOW = RoleRange(0.0, 10.0)
_POWER = RoleRange(0.0, 100_000.0)
_FRACTION = RoleRange(0.0, 1.0)


def plausible_range(role: str) -> RoleRange | None:
    base = role.rstrip("_0123456789") if role[-1].isdigit() else role
    if base.startswith("refg_") and base.endswith("_temp"):
        return _REFG_T
    if base.startswith("refg_") and base.endswith("_pres"):
        return _PRES
    if base in {
        "oat",
        "rat",
        "mat",
        "sat",
        "zone_temp",
        "zone_temp_sp",
        "zone_heat_sp",
        "zone_cool_sp",
        "cond_leaving_air_temp",
    }:
        return _AIR_T
    if base.endswith("_rh"):
        return _RH
    if base.endswith("_flow") and base != "gas_flow":
        return _FLOW
    if base.startswith("power_") or base.startswith("cap_"):
        return _POWER
    if base in {"oa_damper_cmd", "ra_damper_cmd", "comp_stage", "occupied"}:
        return _FRACTION
    return None


# source column -> (canonical role, converter to canonical unit)
SIMULATED: dict[str, tuple[str, Converter]] = {
    "RTU_SA_TEMP": ("sat", f_to_c),
    "RTU_SA_FLOW": ("sa_flow", cfm_to_m3s),
    "RTU_SA_HUM": ("sa_rh", same),
    "RTU_RA_TEMP": ("rat", f_to_c),
    "RTU_RA_FLOW": ("ra_flow", cfm_to_m3s),
    "RTU_RA_HUM": ("ra_rh", same),
    "RTU_OA_TEMP": ("oat", f_to_c),
    "RTU_OA_FLOW": ("oa_flow", cfm_to_m3s),
    "RTU_OA_HUM": ("oa_rh", same),
    "RTU_STG_STA": ("comp_stage", same),
    "RTU_REFG_DISC_TEMP": ("refg_disc_temp", f_to_c),
    "RTU_REFG_COND_TEMP": ("refg_cond_temp", f_to_c),
    "RTU_REFG_SUCT_TEMP": ("refg_suct_temp", f_to_c),
    "RTU_REFG_DISC_PRES": ("refg_disc_pres", psia_e5_to_kpa),
    "RTU_REFG_COND_PRES": ("refg_cond_pres", psia_e5_to_kpa),
    "RTU_REFG_SUCT_PRES": ("refg_suct_pres", psia_e5_to_kpa),
    "RTU_TOT_WATT": ("power_total", same),
    "RTU_COMP_WATT": ("power_comp", same),
    "RTU_SA_FAN_WATT": ("power_fan", same),
    "RTU_SEN_CAPA": ("cap_sensible", same),
    "RTU_TOT_CAPA": ("cap_total", same),
    "ZA_TEMP": ("zone_temp", f_to_c),
    "ZA_HUM": ("zone_rh", same),
    "ZA_TEMP_SPT": ("zone_temp_sp", f_to_c),
}

EXPERIMENTAL: dict[str, tuple[str, Converter]] = {
    "RTU_OA_DMPR_DM": ("oa_damper_cmd", percent_to_fraction),
    "RTU_RA_DMPR_DM": ("ra_damper_cmd", percent_to_fraction),
    "RTU_OA_TEMP": ("oat", f_to_c),
    "RTU_MA_TEMP": ("mat", f_to_c),
    "RTU_SA_TEMP": ("sat", f_to_c),
    "RTU_RA_TEMP": ("rat", f_to_c),
    "RTU_SA_FLOW": ("sa_flow", cfm_to_m3s),
    "RTU_TOT_WATT": ("power_total", same),
    "RTU_GAS_CSUM": ("gas_flow", same),
    "TERM_RM_TEMP_HSPT": ("zone_heat_sp", f_to_c),
    "TERM_RM_TEMP_CSPT": ("zone_cool_sp", f_to_c),
    "OCCU_MOD": ("occupied", same),
    "RTU_COMP_WATT_1": ("power_comp_1", same),
    "RTU_COMP_WATT_2": ("power_comp_2", same),
    "RTU_SA_FAN_WATT": ("power_fan", same),
}

FIELD: dict[str, tuple[str, Converter]] = {
    "RTU_RA_TEMP": ("rat", same),
    "RTU_SA_FAN_WATT": ("power_fan", same),
    "RTU_COMP_WATT": ("power_comp_1", same),
    "RTU_TOT_WATT": ("power_total", same),
    "RTU_SA_FLOW": ("sa_flow", cfm_to_m3s),
    "RTU_MA_HUM": ("ma_rh", same),
    "RTU_OA_HUM": ("oa_rh", same),
    "RTU_RA_HUM": ("ra_rh", same),
    "RTU_SA_HUM": ("sa_rh", same),
    "RTU_SA_TEMP": ("sat", same),
    "RTU_MA_TEMP": ("mat", same),
    "RTU_OA_TEMP": ("oat", same),
    "ZA_TEMP": ("zone_temp", same),
    "RTU_REFG_DISC_PRES_1": ("refg_disc_pres_1", bar_to_kpa),
    "RTU_REFG_DISC_PRES_2": ("refg_disc_pres_2", bar_to_kpa),
    "RTU_REFG_SUCT_PRES_1": ("refg_suct_pres_1", bar_to_kpa),
    "RTU_REFG_SUCT_PRES_2": ("refg_suct_pres_2", bar_to_kpa),
    "RTU_LA_COND_TEMP": ("cond_leaving_air_temp", same),
    "RTU_REFG_COND_TEMP_1": ("refg_cond_temp_1", same),
    "RTU_REFG_COND_TEMP_2": ("refg_cond_temp_2", same),
    "RTU_REFG_SUCT_TEMP_1": ("refg_suct_temp_1", same),
    "RTU_REFG_SUCT_TEMP_2": ("refg_suct_temp_2", same),
    "RTU_REFG_DISC_TEMP_1": ("refg_disc_temp_1", same),
    "RTU_REFG_DISC_TEMP_2": ("refg_disc_temp_2", same),
}

# Columns known to be unusable, with the reason recorded in the load report.
EXCLUDED: dict[Dataset, dict[str, str]] = {
    "simulated": {},
    "experimental": {},
    "field": {"ZA_HUM": "dead sensor: stuck near -15 in every file"},
}

MAPPINGS: dict[Dataset, dict[str, tuple[str, Converter]]] = {
    "simulated": SIMULATED,
    "experimental": EXPERIMENTAL,
    "field": FIELD,
}
