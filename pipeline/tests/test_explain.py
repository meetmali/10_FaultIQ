from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from faultiq.detection import detectors as d
from faultiq.diagnosis.classify import Classifier
from faultiq.diagnosis.features import NORMAL, feature_columns
from faultiq.explain.check import check_event
from faultiq.explain.evidence import group_events
from faultiq.explain.library import LibraryError, fault_library, parse_library
from faultiq.explain.narrate import measured, statements
from faultiq.explain.schema import (
    Context,
    Evidence,
    FaultEvent,
    ModelOutput,
    Statement,
    json_schema,
)
from faultiq.explain.series import build_series
from faultiq.explain.text import fmt, numbers
from faultiq.explain.workflow import Diagnoser, analyse_file, explain
from tests.test_detection import minutes, normal_frame

LIB = fault_library()
T0 = datetime(2018, 10, 11, 7)
ROOT = Path(__file__).parents[2]
CONTRACT = ROOT / "docs" / "contracts" / "diagnostic-result.schema.json"
SERVED_LIBRARY = ROOT / "api" / "src" / "FaultIQ.Api" / "FaultLibrary" / "fault-library.json"

# ------------------------------------------------------------ library and text


def test_every_supported_fault_has_cited_checks() -> None:
    faults = {
        "condenser_fouling", "evaporator_fouling", "liquid_line_restriction",
        "suction_line_restriction", "refrigerant_overcharge", "refrigerant_undercharge",
        "oa_damper_stuck", "economizer_setpoint_offset", "sat_sensor_bias",
    }  # fmt: skip
    assert faults <= set(LIB.faults)
    for f in faults:
        assert LIB.faults[f].checks
        assert all(c.source in LIB.sources for c in LIB.faults[f].checks)


def test_library_rejects_a_check_without_a_known_source() -> None:
    bad = (
        '[sources.a]\ncitation = "A"\n'
        '[faults.x]\ntitle = "X"\nchecks = [{text = "t", source = "b"}]'
    )
    with pytest.raises(LibraryError, match="unknown source"):
        parse_library(bad)


def test_a_model_is_never_shown_as_certain() -> None:
    assert fmt(0.9996, "probability") == "over 99%"
    assert fmt(0.97, "probability") == "97%"
    assert numbers("1,847 kPa, +5.0 and -0.4") == ["1847", "5.0", "-0.4"]


# ------------------------------------------------------------ events


def _hours(alarms: list[bool], answers: list[str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "window_start": [T0 + timedelta(hours=i) for i in range(len(alarms))],
            "alarm": alarms,
            "answer": answers,
        }
    )


def test_events_merge_across_one_quiet_hour_but_not_two() -> None:
    a, b = "condenser_fouling", "inconclusive"
    hours = _hours(
        [True, True, False, True, False, False, True, True],
        [a, a, NORMAL, a, NORMAL, NORMAL, a, b],
    )
    events = group_events(hours)
    assert [(e.answer, e.rows) for e in events] == [(a, [0, 1, 3]), (a, [6]), (b, [7])]


# ------------------------------------------------------------ narration and the claim checker


def _event(kind: str = "fault", fault: str | None = "condenser_fouling") -> FaultEvent:
    ev = Evidence(
        id="ev1", feature="resid:refg_disc_pres", signal="discharge pressure", kind="residual",
        unit="kPa", observed=1847.0, expected=1773.0, deviation=5.04, normal_low=-0.6,
        normal_high=0.7, hours=90, weight=12.3,
    )  # fmt: skip
    model = ModelOutput(
        answer=fault or kind, top_class=fault or "condenser_fouling", confidence=0.9996,
        cutoff=0.41, validation_precision=0.9569, detector_score=9.2, detector_threshold=2.13,
        model_family="lightgbm",
    )  # fmt: skip
    ctx = Context(
        running="compressor", diagnosable_minutes=3422, dominant_mode="cooling",
        outdoor_air_low=10.0, outdoor_air_high=21.1,
    )  # fmt: skip
    start, end = T0, T0 + timedelta(hours=90)
    sts = statements(kind, fault, start, end, 90, model, ctx, [ev], LIB)
    return FaultEvent(
        id="event-1", start=start, end=end, hours=90, kind=kind, fault=fault,  # type: ignore[arg-type]
        fault_title=LIB.title(fault) if fault else None, model=model, context=ctx,
        evidence=[ev], checks=list(LIB.faults[fault].checks) if fault else [], statements=sts,
    )  # fmt: skip


def _check(e: FaultEvent) -> list[str]:
    return check_event(e, LIB, set(LIB.sources))


def _with(e: FaultEvent, extra: Statement) -> FaultEvent:
    return e.model_copy(update={"statements": [*e.statements, extra]})


def test_generated_explanations_pass_the_checker_for_every_kind() -> None:
    for kind, fault in (
        ("fault", "condenser_fouling"),
        ("inconclusive", None),
        ("no_supported_fault", None),
        ("not_diagnosable", None),
    ):
        e = _event(kind, fault)
        assert _check(e) == [], kind
        kinds = [s.kind for s in e.statements]
        assert ("recommended" in kinds) == (kind == "fault")


def test_checker_rejects_an_invented_number() -> None:
    e = _with(
        _event(), Statement(kind="measured", text="Discharge pressure was 2,100 kPa.", refs=["ev1"])
    )
    assert any("number 2100" in p for p in _check(e))


def test_checker_rejects_a_number_cited_from_the_wrong_place() -> None:
    """1,847 kPa is real evidence, but this statement only cites the context."""
    e = _with(_event(), Statement(kind="context", text="Pressure hit 1,847 kPa.", refs=["context"]))
    assert any("number 1847" in p for p in _check(e))


def test_checker_rejects_unknown_references_and_certainty() -> None:
    e = _with(_event(), Statement(kind="finding", text="This is definitely it.", refs=["ev9"]))
    problems = _check(e)
    assert any("unknown reference 'ev9'" in p for p in problems)
    assert any("overconfident" in p for p in problems)


def test_checker_rejects_naming_another_fault() -> None:
    e = _with(
        _event(), Statement(kind="finding", text="Could be refrigerant overcharge.", refs=["model"])
    )
    assert any("refrigerant_overcharge" in p for p in _check(e))


def test_checker_rejects_checks_not_in_the_library_or_without_a_fault() -> None:
    made_up = Statement(kind="recommended", text="Replace the compressor.", refs=["ashrae-180"])
    assert any("not in the fault library" in p for p in _check(_with(_event(), made_up)))
    real = LIB.faults["condenser_fouling"].checks[0]
    stray = Statement(kind="recommended", text=real.text, refs=[real.source])
    assert any(
        "without a named fault" in p for p in _check(_with(_event("inconclusive", None), stray))
    )


def test_named_fault_without_evidence_or_checks_is_rejected() -> None:
    e = _event()
    bare = e.model_copy(update={"statements": [s for s in e.statements if s.kind == "finding"]})
    problems = _check(bare)
    assert any("measured evidence" in p for p in problems)
    assert any("recommended checks" in p for p in problems)
    assert any("uncertainty" in p for p in problems)


def test_weak_evidence_reads_as_weak() -> None:
    """The verdict compares displayed numbers: -0.5 against a range starting at -0.5 is inside."""
    ev = Evidence(
        id="ev1", feature="resid:power_comp", signal="compressor power", kind="residual",
        unit="W", observed=1901.0, expected=1913.0, deviation=-0.46, normal_low=-0.54,
        normal_high=-0.1, hours=9, weight=1.0,
    )  # fmt: skip
    assert measured(ev).text.endswith("This is within the fault-free range.")


# ------------------------------------------------------------ contract


def test_committed_contract_matches_the_schema() -> None:
    """The .NET API (Phase 6) reads this file; a change must be deliberate and regenerated."""
    assert CONTRACT.read_text() == json_schema()


def test_served_fault_library_matches_its_sources() -> None:
    """The API serves a generated file; regenerate with `python -m faultiq export-library`."""
    import json

    from faultiq.explain.library_export import library_json

    results = json.loads((ROOT / "docs" / "diagnosis" / "results.json").read_text())
    assert SERVED_LIBRARY.read_text() == library_json(LIB, results)


def test_library_measurements_come_from_held_out_results() -> None:
    import json

    from faultiq.explain.library_export import export_library

    results = json.loads((ROOT / "docs" / "diagnosis" / "results.json").read_text())
    lib = {f["id"]: f for f in export_library(LIB, results)["faults"]}
    assert lib["condenser_fouling"]["measured"]["symptoms"][0]["signal"] == "discharge pressure"
    assert lib["sat_sensor_bias"]["dataset"] == "experimental"
    every_cited = [
        c["source"] for f in lib.values() for c in [f["definition"], f["observed"], *f["causes"]]
    ]
    assert set(every_cited) <= set(LIB.sources)


# ------------------------------------------------------------ workflow end to end


def _diagnoser() -> Diagnoser:
    model = d.NormalModel(["oat", "rat", "comp_stage"], ["sat"]).fit(normal_frame())
    cols = feature_columns(
        "simulated", "basic"
    )  # med:rat_minus_sat, med:zone_temp_error, resid:sat
    rng = np.random.default_rng(0)
    y = np.array([NORMAL, "condenser_fouling"] * 100)
    x = np.column_stack(
        [rng.normal(11, 0.3, 200), rng.normal(0, 0.2, 200),
         np.where(y == NORMAL, 0.0, 20.0) + rng.normal(0, 1, 200)]
    )  # fmt: skip
    clf = Classifier("logistic", cols).fit(x, y)
    return Diagnoser(
        "simulated", "basic", {"basic": model, "all": model}, None, clf, cutoff=0.6,
        detector_threshold=3.0, ranges={"resid:sat": (-1.0, 1.0)},
        precision={"condenser_fouling": 0.95},
    )  # fmt: skip


def test_workflow_finds_explains_and_checks_a_fault_without_seeing_a_label() -> None:
    n = 300  # five hours: two normal, three with supply air 5 K too warm
    oat = 20.0
    sat = [12 + 0.1 * oat] * 120 + [12 + 0.1 * oat + 5] * 180
    df = minutes(
        n, oat=oat, rat=23.0, comp_stage=1.0, sat=sat,
        rat_minus_sat=[23 - s for s in sat], zone_temp_error=0.0,
    )  # fmt: skip
    result = explain(df, _diagnoser(), "unit.csv")
    assert result.hours_alarmed == 3
    [event] = result.events
    assert event.kind == "fault" and event.fault == "condenser_fouling"
    assert event.hours == 3
    assert event.evidence[0].feature == "resid:sat"
    alternatives = event.model.alternatives
    assert alternatives[0].fault == "condenser_fouling"  # highest first, the answer itself
    assert {a.fault for a in alternatives} == {"condenser_fouling", NORMAL}
    assert sum(a.probability for a in alternatives) == pytest.approx(1.0, abs=1e-3)
    assert event.evidence[0].expected == pytest.approx(14.0, abs=0.3)
    assert [s.id for s in result.sources] == ["ashrae-180"]
    assert result.library_review_status == "unreviewed"
    # Times are as recorded, explicitly marked, so no reader shifts them by its own zone.
    assert event.start.utcoffset() is not None and event.start.hour == 2


def test_series_v2_hourly_table_is_aligned_and_diagnostic() -> None:
    """Every hourly column has one value per hour, and residuals carry their fault-free band."""
    oat = 20.0
    sat = [12 + 0.1 * oat] * 120 + [12 + 0.1 * oat + 5] * 180
    df = minutes(
        300, oat=oat, rat=23.0, comp_stage=1.0, sat=sat,
        rat_minus_sat=[23 - x for x in sat], zone_temp_error=0.0,
    )  # fmt: skip
    diag = _diagnoser()
    result, hours = analyse_file(df, diag, "unit.csv")
    series = build_series(df, result, diag.models, hours, diag.ranges)
    assert series["version"] == 2
    hourly = series["hourly"]
    n = len(hourly["t"])
    assert n == 5
    assert all(len(hourly[k]) == n for k in ("mode", "diagnosable", "alarm", "answer"))
    assert all(len(c["values"]) == n for c in hourly["columns"].values())
    resid = hourly["columns"]["resid:sat"]
    assert resid["kind"] == "residual" and (resid["normal_low"], resid["normal_high"]) == (
        -1.0,
        1.0,
    )
    assert hourly["alarm"] == [False, False, True, True, True]
    assert hourly["columns"]["sat"]["kind"] == "signal"


def test_workflow_refuses_unprocessed_input() -> None:
    with pytest.raises(ValueError, match="not a processed file"):
        explain(pl.DataFrame({"timestamp": [T0]}), _diagnoser(), "raw.csv")
