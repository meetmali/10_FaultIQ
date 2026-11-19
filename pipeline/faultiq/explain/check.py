"""Claim checker: rejects any statement the evidence doesn't support (ADR 0023).

Rules, per statement:
1. It cites at least one reference, and every reference exists in the result.
2. Every number in it is the display form of a value it cites (event times included).
3. It names no fault other than the event's fault or the model's closest match.
4. It uses no words of certainty a model inference can't carry.
5. Recommended checks appear only for a named fault, word for word from the fault library,
   citing the source the library gives.
And per event: a named fault has measured evidence, an uncertainty statement and checks; every
event says how far to trust it.

The workflow runs this on every result and refuses to emit one that fails (fail closed). An LLM
phrasing added later would have to pass the same checks.
"""

from __future__ import annotations

import re
from typing import Any

from faultiq.explain.library import FaultLibrary
from faultiq.explain.schema import FIXED_REFS, DiagnosticResult, FaultEvent, Statement
from faultiq.explain.text import display_numbers, fmt_time, numbers

OVERCONFIDENT = re.compile(
    r"\b(definitely|certainly|undoubtedly|guaranteed?|proves?|proven|is confirmed|"
    r"has been confirmed|the cause is|caused by|without doubt)\b",
    re.IGNORECASE,
)


class ExplanationError(ValueError):
    """An explanation failed the claim checker."""


def _values(obj: Any) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, int | float):
        return [float(obj)]
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in _values(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in _values(x)]
    return []


def _allowed_numbers(event: FaultEvent, refs: list[str]) -> set[str]:
    by_ref: dict[str, Any] = {
        "event": {"hours": event.hours},
        "model": event.model.model_dump(),
        "detector": {
            "score": event.model.detector_score,
            "threshold": event.model.detector_threshold,
        },
        "context": event.context.model_dump(),
        **{e.id: e.model_dump() for e in event.evidence},
    }
    allowed: set[str] = set()
    for r in refs:
        for v in _values(by_ref.get(r, {})):
            allowed |= display_numbers(v)
    return allowed


def check_statement(
    s: Statement, event: FaultEvent, library: FaultLibrary, source_ids: set[str]
) -> list[str]:
    where = f"{event.id} [{s.kind}] {s.text[:60]!r}"
    problems = []
    known = set(FIXED_REFS) | {e.id for e in event.evidence} | source_ids
    for r in s.refs:
        if r not in known:
            problems.append(f"{where}: unknown reference {r!r}")

    text = s.text
    if "event" in s.refs:  # event times are cited as a whole, not as loose numbers
        for t in (event.start, event.end):
            text = text.replace(fmt_time(t), "")
    allowed = _allowed_numbers(event, s.refs)
    for n in numbers(text):
        if n not in allowed:
            problems.append(f"{where}: number {n} is not in the cited evidence")

    may_name = {event.fault, event.model.top_class}
    lowered = s.text.lower()
    for name, info in library.faults.items():
        if name not in may_name and (info.title.lower() in lowered or name in lowered):
            problems.append(f"{where}: names unsupported fault {name!r}")

    if OVERCONFIDENT.search(s.text):
        problems.append(f"{where}: overconfident wording")

    if s.kind == "recommended":
        if event.kind != "fault" or event.fault not in library.faults:
            problems.append(f"{where}: check recommended without a named fault")
        else:
            allowed_checks = {(c.text, c.source) for c in library.faults[event.fault].checks}
            if (s.text, s.refs[0] if s.refs else "") not in allowed_checks:
                problems.append(f"{where}: check is not in the fault library")
    return problems


def check_event(event: FaultEvent, library: FaultLibrary, source_ids: set[str]) -> list[str]:
    problems = [p for s in event.statements for p in check_statement(s, event, library, source_ids)]
    kinds = [s.kind for s in event.statements]
    if "finding" not in kinds or "uncertainty" not in kinds:
        problems.append(f"{event.id}: needs a finding and an uncertainty statement")
    if event.kind == "fault":
        if "measured" not in kinds:
            problems.append(f"{event.id}: a named fault needs measured evidence")
        if "recommended" not in kinds:
            problems.append(f"{event.id}: a named fault needs recommended checks")
    return problems


def check_result(result: DiagnosticResult, library: FaultLibrary) -> list[str]:
    source_ids = {s.id for s in result.sources}
    return [p for e in result.events for p in check_event(e, library, source_ids)]
