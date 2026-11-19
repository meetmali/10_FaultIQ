"""Plain names, units and number formats shared by the narrator and the claim checker.

Both sides must format a value the same way. A number appearing in a statement is accepted only
if it is the display form of a value the statement cites.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

# feature base name -> (plain name, display unit)
SIGNALS: dict[str, tuple[str, str]] = {
    # normal-model targets (residual evidence shows the physical value)
    "sat": ("supply-air temperature", "degC"),
    "sa_flow": ("supply airflow", "m3/s"),
    "refg_suct_pres": ("suction pressure", "kPa"),
    "refg_disc_pres": ("discharge pressure", "kPa"),
    "refg_disc_temp": ("discharge temperature", "degC"),
    "power_comp": ("compressor power", "W"),
    "oa_damper_cmd": ("outdoor-air damper command", "fraction"),
    "vav_sat_min": ("coldest VAV discharge temperature", "degC"),
    # physics features
    "rat_minus_sat": ("return-air minus supply-air temperature", "K"),
    "mat_minus_sat": ("mixed-air minus supply-air temperature", "K"),
    "zone_temp_error": ("zone temperature above setpoint", "K"),
    "superheat": ("suction superheat", "K"),
    "subcooling": ("liquid subcooling", "K"),
    "condensing_approach": ("condensing approach temperature", "K"),
    "comp_power_per_capacity": ("compressor power per unit of cooling", "ratio"),
    "sensible_heat_ratio": ("sensible heat ratio", "ratio"),
    "oaf_temp": ("outdoor-air fraction", "fraction"),
    "sat_minus_vav_sat_min": ("supply air minus coldest VAV discharge", "K"),
    # economizer rules (share of applicable minutes)
    "economizing_when_should_not": ("damper open while outdoor air was too warm", "share"),
    "not_economizing_when_should": ("mechanical cooling with free cooling available", "share"),
    "sat_disagrees_with_vav": ("supply-air reading disagreeing with the VAV boxes", "share"),
}

FORMATS: dict[str, Callable[[float], str]] = {
    "degC": lambda v: f"{v:.1f} °C",
    "K": lambda v: f"{v:.1f} K",
    "kPa": lambda v: f"{v:,.0f} kPa",
    "W": lambda v: f"{v:,.0f} W",
    "m3/s": lambda v: f"{v:.2f} m³/s",
    "fraction": lambda v: f"{v:.0%}",
    "share": lambda v: f"{v:.0%}",
    "ratio": lambda v: f"{v:.2f}",
    "errors": lambda v: f"{v:+.1f}",
    # A model is never shown as certain: 99.5% and above reads "over 99%".
    "probability": lambda v: "over 99%" if v >= 0.995 else f"{v:.0%}",
    "score": lambda v: f"{v:.2f}",
    "count": lambda v: f"{v:,.0f}",
}

NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def signal(feature: str) -> tuple[str, str]:
    """`resid:refg_disc_pres` -> ("discharge pressure", "kPa")."""
    base = feature.split(":", 1)[-1]
    return SIGNALS.get(base, (base.replace("_", " "), "ratio"))


def fmt(value: float, unit: str) -> str:
    return FORMATS[unit](value)


def fmt_time(t: datetime) -> str:
    return t.strftime("%d %b %Y %H:%M")


def shown(value: float, unit: str) -> float:
    """The value as displayed (rounded the way `fmt` rounds it)."""
    return float(numbers(fmt(value, unit))[0])


def numbers(text: str) -> list[str]:
    """Numbers as written, without thousands separators or a leading plus sign."""
    return [n.replace(",", "").lstrip("+") for n in NUMBER.findall(text)]


def display_numbers(value: float) -> set[str]:
    """Every number token `value` can produce under any display format."""
    out: set[str] = set()
    for f in FORMATS.values():
        out.update(numbers(f(value)))
    return out
