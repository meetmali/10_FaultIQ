"""R410A saturation temperature from pressure (approximate table, linear interpolation).

Accurate to well under 1 K across the operating range, which is enough for superheat and
subcooling features. Inputs are absolute pressures in kPa.
"""

from __future__ import annotations

import numpy as np
import polars as pl

_T_C = np.array([-20, -10, 0, 5, 10, 15, 20, 25, 30, 40, 50, 60], dtype=float)
_P_KPA = np.array([400, 573, 798, 933, 1085, 1253, 1440, 1646, 1875, 2420, 3060, 3830], dtype=float)


def saturation_temp_c(pressure_kpa: pl.Expr) -> pl.Expr:
    """Saturation temperature (deg C) for an absolute R410A pressure expression in kPa."""

    def _interp(s: pl.Series) -> pl.Series:
        values = s.to_numpy().astype(float)
        out = np.interp(values, _P_KPA, _T_C)
        out[np.isnan(values)] = np.nan
        return pl.Series(s.name, out).fill_nan(None)

    return pressure_kpa.map_batches(_interp, return_dtype=pl.Float64)
