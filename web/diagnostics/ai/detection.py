"""Fault detection for rooftop-unit trend data.

Pipeline: CSV -> validation -> hourly resample -> features -> Isolation Forest anomaly scores
+ physics rules (APAR-style) -> merged fault events with a named fault and a confidence.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

REQUIRED = ["timestamp", "oat", "rat", "mat", "sat", "sat_sp", "damper_pct", "cooling_pct", "fan_on"]
MAX_ROWS = 100_000
MIN_HOURS = 24

# Rule code -> fault library code. Each rule is a physical impossibility or a control error.
RULE_FAULT = {
    "mat_out_of_range": "mat-sensor",
    "low_capacity": "low-refrigerant",
    "not_economizing": "econ-stuck-closed",
    "excess_outdoor_air": "econ-stuck-open",
    "cooling_not_commanded": "cooling-leak",
}


class DetectionError(ValueError):
    """Raised for input the detector cannot analyse. The message is safe to show to users."""


@dataclass
class Event:
    start: pd.Timestamp
    end: pd.Timestamp
    hours: int
    fault_code: str | None
    confidence: float
    anomaly_score: float


@dataclass
class DetectionResult:
    hours_analysed: int
    anomaly_hours: int
    rows_dropped: int
    events: list[Event] = field(default_factory=list)
    series: dict = field(default_factory=dict)


def read_trends(data: bytes) -> tuple[pd.DataFrame, int]:
    """Parse and validate an uploaded CSV. Returns hourly means and the number of unusable rows dropped."""
    try:
        df = pd.read_csv(io.BytesIO(data), nrows=MAX_ROWS + 1)
    except Exception as exc:  # pandas raises several types for malformed files
        raise DetectionError("The file could not be read as CSV.") from exc
    if len(df) > MAX_ROWS:
        raise DetectionError(f"The file has more than {MAX_ROWS:,} rows. Split it into smaller exports.")
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise DetectionError(f"Missing required columns: {', '.join(missing)}.")
    df = df[REQUIRED].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for col in REQUIRED[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    before = len(df)
    df = df.dropna()
    dropped = before - len(df)
    if df.empty:
        raise DetectionError("No usable rows: every row had a missing or non-numeric value.")
    hourly = df.set_index("timestamp").sort_index().resample("1h").mean().dropna()
    if len(hourly) < MIN_HOURS:
        raise DetectionError(f"At least {MIN_HOURS} hours of data are needed; found {len(hourly)}.")
    return hourly, dropped


def rule_flags(h: pd.DataFrame) -> pd.Series:
    """Return the first rule that fires for each hour, or None."""
    lo, hi = np.minimum(h.oat, h.rat), np.maximum(h.oat, h.rat)
    checks = [
        ("mat_out_of_range", (h.mat > hi + 2) | (h.mat < lo - 2)),
        ("low_capacity", (h.cooling_pct >= 90) & (h.sat > h.sat_sp + 2.5)),
        ("not_economizing", (h.oat < h.rat - 2) & (h.oat < 18) & (h.cooling_pct > 10) & (h.damper_pct < 30)),
        ("excess_outdoor_air", (h.oat > h.rat + 2) & (h.damper_pct > 60)),
        ("cooling_not_commanded", (h.cooling_pct <= 5) & (h.sat < h.mat - 3)),
    ]
    out = pd.Series([None] * len(h), index=h.index, dtype=object)
    for name, mask in reversed(checks):  # earlier rules win
        out[mask.to_numpy()] = name
    return out


def features(h: pd.DataFrame) -> np.ndarray:
    spread = (h.oat - h.rat).where((h.oat - h.rat).abs() > 1, np.nan)
    oa_fraction = ((h.mat - h.rat) / spread).clip(-2, 3).fillna(0)
    return np.column_stack([h.sat - h.sat_sp, oa_fraction, h.damper_pct, h.cooling_pct, h.oat - h.rat])


def detect(data: bytes, *, min_event_hours: int = 2, min_unexplained_hours: int = 4) -> DetectionResult:
    """Run detection.

    Events no physics rule explains must last min_unexplained_hours (improvement from evaluation:
    short unexplained anomalies were mostly rare-but-normal hours such as morning economizer start-up).
    min_unexplained_hours=2 reproduces the version before that improvement.
    """
    hourly, dropped = read_trends(data)
    running = hourly[hourly.fan_on >= 0.5]
    if len(running) < MIN_HOURS:
        raise DetectionError("The supply fan ran for fewer than 24 hours, so there is too little data to analyse.")

    x = StandardScaler().fit_transform(features(running))
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=0).fit(x)
    score = -forest.decision_function(x)  # higher = more unusual
    anomalous = score > 0
    rules = rule_flags(running)
    flagged = anomalous | rules.notna().to_numpy()

    events = [
        e for e in _group_events(running.index, flagged, rules, score, min_event_hours)
        if e.fault_code or e.hours >= min_unexplained_hours
    ]
    series = {
        "t": [t.isoformat() for t in running.index],
        "sat": running.sat.round(2).tolist(),
        "sat_sp": running.sat_sp.round(2).tolist(),
        "oat": running.oat.round(2).tolist(),
        "score": np.round(score, 3).tolist(),
    }
    return DetectionResult(len(running), int(anomalous.sum()), dropped, events, series)


def _group_events(index, flagged, rules, score, min_hours) -> list[Event]:
    events, start = [], None
    for i in range(len(index) + 1):
        on = i < len(index) and flagged[i]
        # A new run starts on a flagged hour; a gap in time (fan off overnight) also ends a run.
        if on and start is not None and index[i] - index[i - 1] > pd.Timedelta(hours=1):
            events.append(_make_event(index, rules, score, start, i))
            start = None
        if on and start is None:
            start = i
        elif not on and start is not None:
            events.append(_make_event(index, rules, score, start, i))
            start = None
    return [e for e in events if e.hours >= min_hours]


def _make_event(index, rules, score, start, stop) -> Event:
    window = rules.iloc[start:stop].dropna()
    hours = stop - start
    if window.empty:
        code, confidence = None, 0.3
    else:
        top = window.value_counts()
        code = RULE_FAULT[top.index[0]]
        confidence = round(0.5 + 0.5 * top.iloc[0] / hours, 2)
    return Event(index[start], index[stop - 1], hours, code, confidence, float(np.round(score[start:stop].max(), 3)))
