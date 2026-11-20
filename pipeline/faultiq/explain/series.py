"""Chart series, precomputed by the worker (ADR 0009, ADR 0026).

The API never sends raw minute data to a browser. For each analysis the worker stores:
- an overview of the main temperatures for the whole period (LTTB-downsampled),
- per fault event, the evidence signals around the event, observed and (where the normal model
  applies) expected, for the expected-versus-observed charts from Phase 5,
- (v2) one aligned **hourly** table: each sensor's hourly median, each residual and rule share with
  its fault-free band, and what the workflow decided that hour (mode, diagnosable, alarm, answer).
  Every hourly column answers a diagnostic question; nothing is stored just to be plotted.

Downsampling uses LTTB (largest triangle three buckets), which keeps peaks and troughs that a plain
average would flatten. It is a display transform only: detection and diagnosis use full data.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import polars as pl

from faultiq.detection import detectors as d
from faultiq.explain.schema import DiagnosticResult
from faultiq.explain.text import signal

SERIES_VERSION = 2
OVERVIEW_POINTS = 2000
EVENT_POINTS = 300  # an evidence chart is ~200 px wide
EVENT_PADDING = timedelta(hours=2)
MAX_EVENTS = 50  # longest events get detail series; the rest are still listed in the result
OVERVIEW_SIGNALS = ("oat", "rat", "mat", "sat")
# Sensor and physics signals the technician schematic places on the unit, when the file has them.
HOURLY_SIGNALS = (
    "oat", "rat", "mat", "sat", "oa_damper_cmd", "comp_stage", "sa_flow",
    "refg_suct_pres", "refg_disc_pres", "refg_suct_temp", "refg_disc_temp",
    "superheat", "subcooling", "condensing_approach", "power_fan", "power_comp",
    "vav_sat_min", "zone_temp",
)  # fmt: skip
UNIT_OF = {
    "comp_stage": "fraction",
    "power_fan": "W",
    "refg_suct_temp": "degC",
    "zone_temp": "degC",
}


def lttb(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """Indices of the `n` points LTTB keeps from (x, y). Keeps the first and last point."""
    size = len(x)
    if n >= size or n < 3:
        return np.arange(size)
    bucket = (size - 2) / (n - 2)  # the points between the two ends, split into n - 2 buckets
    keep = [0]
    a = 0  # the point kept from the previous bucket
    for i in range(n - 2):
        lo, hi = int(i * bucket) + 1, int((i + 1) * bucket) + 1  # this bucket
        nhi = min(int((i + 2) * bucket) + 1, size)  # the next bucket is [hi, nhi)
        cx, cy = x[hi:nhi].mean(), y[hi:nhi].mean()
        # Keep the point forming the largest triangle with the previous kept point and the
        # next bucket's average: the one that changes the line's shape the most.
        area = np.abs((x[a] - cx) * (y[lo:hi] - y[a]) - (x[a] - x[lo:hi]) * (cy - y[a]))
        a = lo + int(area.argmax())
        keep.append(a)
    keep.append(size - 1)
    return np.asarray(keep)


def _points(
    times: pl.Series, values: pl.Series, n: int, digits: int = 2
) -> tuple[list[int], list[float]]:
    """Epoch milliseconds and values, nulls dropped, downsampled to at most `n` points."""
    frame = pl.DataFrame({"t": times, "v": values}).drop_nulls()
    if frame.height == 0:
        return [], []
    t = frame["t"].dt.epoch("ms").to_numpy()
    v = frame["v"].cast(pl.Float64).to_numpy()
    idx = lttb(t.astype(float), v, n)
    return t[idx].tolist(), np.round(v[idx], digits).tolist()


def _digits(unit: str) -> int:
    """Display precision: whole kPa and W, two decimals otherwise. Keeps the series small."""
    return 0 if unit in ("kPa", "W") else 2


def _round(values: pl.Series, digits: int = 2) -> list[float | None]:
    return [None if v is None or v != v else round(float(v), digits) for v in values.to_list()]


def hourly_table(
    minutes: pl.DataFrame, hours: pl.DataFrame, ranges: dict[str, tuple[float, float]]
) -> dict[str, Any]:
    """One row per hour, aligned for the time scrubber and the timelines."""
    hours = hours.sort("window_start")
    present = [c for c in HOURLY_SIGNALS if c in minutes.columns]
    medians = minutes.group_by(pl.col("timestamp").dt.truncate("1h").alias("window_start")).agg(
        [pl.col(c).median() for c in present]
    )
    table = hours.join(medians, on="window_start", how="left")
    columns: dict[str, Any] = {}
    for c in present:
        name, unit = signal(c)
        columns[c] = {
            "label": name,
            "unit": UNIT_OF.get(c, unit),
            "kind": "signal",
            "values": _round(table[c]),
        }
    for c in table.columns:
        if c.startswith(("resid:", "med:", "rule:")):
            name, unit = signal(c)
            kind = {"resid": "residual", "med": "physics", "rule": "rule"}[c.split(":", 1)[0]]
            lo, hi = ranges.get(c, (None, None))
            columns[c] = {
                "label": name, "unit": "errors" if kind == "residual" else unit, "kind": kind,
                "values": _round(table[c]), "normal_low": lo, "normal_high": hi,
            }  # fmt: skip
    return {
        "t": table["window_start"].dt.epoch("ms").to_list(),
        "mode": table["mode"].cast(pl.Utf8).to_list(),
        "steady_minutes": table["n_steady"].to_list(),
        "diagnosable": table["diagnosable"].to_list(),
        "alarm": table["alarm"].to_list(),
        "answer": table["answer"].to_list(),
        "confidence": _round(table["confidence"]),
        "columns": columns,
    }


def build_series(
    minutes: pl.DataFrame,
    result: DiagnosticResult,
    models: dict[str, d.NormalModel],
    hours: pl.DataFrame | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    overview = {}
    for col in OVERVIEW_SIGNALS:
        if col in minutes.columns:
            t, v = _points(minutes["timestamp"], minutes[col], OVERVIEW_POINTS)
            if t:
                overview[col] = {"label": signal(col)[0], "unit": signal(col)[1], "t": t, "v": v}

    events: dict[str, Any] = {}
    for event in sorted(result.events, key=lambda e: e.hours, reverse=True)[:MAX_EVENTS]:
        window = minutes.filter(
            # Minute data is naive (as recorded); event times are the same numbers marked UTC.
            pl.col("timestamp").is_between(
                event.start.replace(tzinfo=None) - EVENT_PADDING,
                event.end.replace(tzinfo=None) + EVENT_PADDING,
            )
        )
        signals: dict[str, Any] = {}
        for ev in event.evidence:
            base = ev.feature.split(":", 1)[1]
            if base not in window.columns:
                continue  # rule shares have no single underlying signal to draw
            t, observed = _points(window["timestamp"], window[base], EVENT_POINTS, _digits(ev.unit))
            entry: dict[str, Any] = {
                "label": ev.signal,
                "unit": ev.unit,
                "t": t,
                "observed": observed,
            }
            model = next((m for m in models.values() if base in m.models), None)
            if ev.kind == "residual" and model is not None and t:
                # Expected values only inside the model's weather range, as in the explanation.
                exp = model.expected(window)[f"expected:{base}"]
                inside = window.select(d.within(model.envelope).alias("_in"))["_in"]
                exp = pl.Series([e if ok else None for e, ok in zip(exp, inside, strict=True)])
                lookup = dict(
                    zip(window["timestamp"].dt.epoch("ms").to_list(), exp.to_list(), strict=True)
                )
                entry["expected"] = [
                    None if lookup.get(ts) is None else round(lookup[ts], _digits(ev.unit))
                    for ts in t
                ]
            signals[ev.id] = entry
        events[event.id] = {
            "start": int(event.start.timestamp() * 1000),
            "end": int(event.end.timestamp() * 1000),
            "signals": signals,
        }
    out: dict[str, Any] = {"version": SERIES_VERSION, "overview": overview, "events": events}
    if hours is not None:
        out["hourly"] = hourly_table(minutes, hours, ranges or {})
    return out
