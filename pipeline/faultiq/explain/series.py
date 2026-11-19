"""Downsampled chart series, precomputed by the worker (ADR 0009).

The API never sends raw minute data to a browser. For each analysis the worker stores:
- an overview of the main temperatures for the whole period,
- per fault event, the evidence signals around the event, observed and (where the normal model
  applies) expected, so the UI can draw the expected-versus-observed chart from Phase 5.

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

SERIES_VERSION = 1
OVERVIEW_POINTS = 2000
EVENT_POINTS = 500
EVENT_PADDING = timedelta(hours=2)
MAX_EVENTS = 50  # longest events get detail series; the rest are still listed in the result
OVERVIEW_SIGNALS = ("oat", "rat", "mat", "sat")


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


def _points(times: pl.Series, values: pl.Series, n: int) -> tuple[list[int], list[float]]:
    """Epoch milliseconds and values, nulls dropped, downsampled to at most `n` points."""
    frame = pl.DataFrame({"t": times, "v": values}).drop_nulls()
    if frame.height == 0:
        return [], []
    t = frame["t"].dt.epoch("ms").to_numpy()
    v = frame["v"].cast(pl.Float64).to_numpy()
    idx = lttb(t.astype(float), v, n)
    return t[idx].tolist(), np.round(v[idx], 4).tolist()


def build_series(
    minutes: pl.DataFrame, result: DiagnosticResult, models: dict[str, d.NormalModel]
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
            pl.col("timestamp").is_between(event.start - EVENT_PADDING, event.end + EVENT_PADDING)
        )
        signals: dict[str, Any] = {}
        for ev in event.evidence:
            base = ev.feature.split(":", 1)[1]
            if base not in window.columns:
                continue  # rule shares have no single underlying signal to draw
            t, observed = _points(window["timestamp"], window[base], EVENT_POINTS)
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
                    None if lookup.get(ts) is None else round(lookup[ts], 4) for ts in t
                ]
            signals[ev.id] = entry
        events[event.id] = {
            "start": int(event.start.timestamp() * 1000),
            "end": int(event.end.timestamp() * 1000),
            "signals": signals,
        }
    return {"version": SERIES_VERSION, "overview": overview, "events": events}
