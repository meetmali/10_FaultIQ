"""Fault events and the sensor evidence behind them (ADR 0023).

An event is a run of alarmed hours with the same answer, allowing one quiet hour inside it (a
compressor cycling off for an hour shouldn't split one fault into two). Its evidence is at most
`TOP_EVIDENCE` signals:
- for a named fault or an inconclusive answer, the features that pushed the diagnoser hardest,
  summed over the event's hours (only features that were actually measured in the event),
- otherwise, the targets the detector found furthest from normal.

Every number is taken from the event's own minutes, or from fault-free validation hours for
the "normal range". An expected value is shown only where the normal model applies (inside its
training weather range), i.e. where a defensible baseline exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import polars as pl

from faultiq.detection import detectors as d
from faultiq.explain.schema import Context, Evidence
from faultiq.explain.text import signal

TOP_EVIDENCE = 3
MERGE_GAP = timedelta(hours=2)  # next alarmed hour may start up to 2 h after the previous one
HOUR = timedelta(hours=1)
MIN_REFERENCE_HOURS = 10  # fewer fault-free hours than this: no normal range is shown

NormalRanges = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class EventHours:
    answer: str
    rows: list[int]  # row positions in the scored hours table


def group_events(hours: pl.DataFrame) -> list[EventHours]:
    """Merge alarmed hours (sorted by `window_start`) with the same answer into events."""
    alarmed = hours.with_row_index("_row").filter(pl.col("alarm"))
    events: list[EventHours] = []
    last_start = None
    for row in alarmed.iter_rows(named=True):
        same = events and events[-1].answer == row["answer"]
        if same and last_start is not None and row["window_start"] - last_start <= MERGE_GAP:
            events[-1].rows.append(row["_row"])
        else:
            events.append(EventHours(row["answer"], [row["_row"]]))
        last_start = row["window_start"]
    return events


def normal_ranges(fault_free_hours: pl.DataFrame, columns: list[str]) -> NormalRanges:
    """5th to 95th percentile of each hourly feature on fault-free reference hours."""
    out: NormalRanges = {}
    for c in columns:
        if c in fault_free_hours.columns:
            v = fault_free_hours[c].drop_nulls()
            if v.len() >= MIN_REFERENCE_HOURS:
                out[c] = (float(v.quantile(0.05) or 0.0), float(v.quantile(0.95) or 0.0))
    return out


def _median(s: pl.Series) -> float | None:
    s = s.drop_nulls()
    return float(s.median()) if s.len() else None  # type: ignore[arg-type]


def residual_evidence(
    eid: str,
    feature: str,
    minutes: pl.DataFrame,
    mask: pl.Series,
    model: d.NormalModel,
    ranges: NormalRanges,
    weight: float,
) -> Evidence | None:
    target = feature.split(":", 1)[1]
    if target not in model.models:
        return None
    resid = model.residuals(minutes)[f"resid:{target}"]
    expected = model.expected(minutes)[f"expected:{target}"]
    ok = mask & resid.is_not_null()
    if not ok.any():
        return None
    name, unit = signal(feature)
    observed, exp = _median(minutes[target].filter(ok)), _median(expected.filter(ok))
    if observed is None or exp is None:
        return None
    lo, hi = ranges.get(feature, (None, None))
    return Evidence(
        id=eid, feature=feature, signal=name, kind="residual", unit=unit,
        observed=observed, expected=exp, deviation=_median(resid.filter(ok)),
        normal_low=lo, normal_high=hi,
        hours=int(minutes.filter(ok)["window_start"].n_unique()), weight=weight,
    )  # fmt: skip


def hourly_evidence(
    eid: str, feature: str, event_hours: pl.DataFrame, ranges: NormalRanges, weight: float
) -> Evidence | None:
    """Physics and rule features: the event median of their hourly values."""
    values = event_hours[feature].drop_nulls()
    if values.len() == 0:
        return None
    name, unit = signal(feature)
    lo, hi = ranges.get(feature, (None, None))
    return Evidence(
        id=eid, feature=feature, signal=name,
        kind="rule" if feature.startswith("rule:") else "physics", unit=unit,
        observed=float(values.median()),  # type: ignore[arg-type]
        normal_low=lo, normal_high=hi, hours=values.len(), weight=weight,
    )  # fmt: skip


def diagnosis_evidence(
    event_hours: pl.DataFrame,
    contributions: np.ndarray,
    columns: list[str],
    minutes: pl.DataFrame,
    diagnosable: pl.Series,
    models: dict[str, d.NormalModel],
    residual_model: dict[str, str],
    ranges: NormalRanges,
) -> list[Evidence]:
    """Top features by summed contribution toward the answer, among those measured."""
    measured = np.array([event_hours[c].is_not_null().any() for c in columns])
    weights = np.where(measured, contributions.sum(axis=0), -np.inf)
    out: list[Evidence] = []
    for i in np.argsort(-weights):
        if len(out) == TOP_EVIDENCE or not np.isfinite(weights[i]) or weights[i] <= 0:
            break
        feature, eid, w = columns[i], f"ev{len(out) + 1}", round(float(weights[i]), 4)
        if feature.startswith("resid:"):
            model = models[residual_model[feature.split(":", 1)[1]]]
            ev = residual_evidence(eid, feature, minutes, diagnosable, model, ranges, w)
        else:
            ev = hourly_evidence(eid, feature, event_hours, ranges, w)
        if ev is not None:
            out.append(ev)
    return out


def detector_evidence(
    minutes: pl.DataFrame, steady: pl.Series, model: d.NormalModel, ranges: NormalRanges
) -> list[Evidence]:
    """The targets the detector found furthest from normal, by median absolute deviation."""
    resid = model.residuals(minutes)
    ranked = sorted(
        (
            (float(resid[c].filter(steady).abs().median() or 0.0), c)  # type: ignore[arg-type]
            for c in resid.columns
            if resid[c].filter(steady).drop_nulls().len()
        ),
        reverse=True,
    )
    out: list[Evidence] = []
    for size, col in ranked[:TOP_EVIDENCE]:
        ev = residual_evidence(
            f"ev{len(out) + 1}", col, minutes, steady, model, ranges, round(size, 4)
        )
        if ev is not None:
            out.append(ev)
    return out


def context(minutes: pl.DataFrame, diagnosable: pl.Series, running: str) -> Context:
    steady = minutes.filter(pl.col("steady").fill_null(False))
    mode = steady["operating_mode"].cast(pl.Utf8).mode().sort().first() if steady.height else None
    oat = minutes["oat"].filter(diagnosable).drop_nulls() if "oat" in minutes.columns else None
    has_oat = oat is not None and oat.len() > 0
    return Context(
        running=running,
        diagnosable_minutes=int(diagnosable.sum()),
        dominant_mode=str(mode) if mode is not None else None,
        outdoor_air_low=float(oat.min()) if has_oat else None,  # type: ignore[union-attr,arg-type]
        outdoor_air_high=float(oat.max()) if has_oat else None,  # type: ignore[union-attr,arg-type]
    )
