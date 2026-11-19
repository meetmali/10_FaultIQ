"""Template explanations built only from an event's structured fields (ADR 0023).

Four kinds of sentence are kept apart, so a reader always knows what they are looking at:
- finding: what the system concluded (a model inference),
- measured / context: what the sensors showed,
- uncertainty: how far to trust the finding,
- recommended: checks from the cited fault library, only when a fault is named.
"""

from __future__ import annotations

from faultiq.explain.library import FaultLibrary
from faultiq.explain.schema import Context, Evidence, ModelOutput, Statement
from faultiq.explain.text import fmt, fmt_time, shown

WHY_NO_CHECKS = "No checks are recommended because no supported fault was identified."


def _span(start: object, end: object, hours: int) -> str:
    return f"from {fmt_time(start)} to {fmt_time(end)} ({hours} h)"  # type: ignore[arg-type]


def _range(e: Evidence, unit: str) -> str:
    if e.normal_low is None or e.normal_high is None:
        return ""
    return (
        f"; on fault-free hours it ranged {fmt(e.normal_low, unit)} to {fmt(e.normal_high, unit)}"
    )


def _verdict(e: Evidence) -> str:
    """Say plainly whether the value is unusual, so weak evidence reads as weak."""
    value = e.deviation if e.kind == "residual" else e.observed
    if value is None or e.normal_low is None or e.normal_high is None:
        return ""
    unit = "errors" if e.kind == "residual" else "share" if e.kind == "rule" else e.unit
    # Compare the numbers as the reader sees them, so the verdict never contradicts the text.
    lo, hi, v = (shown(x, unit) for x in (e.normal_low, e.normal_high, value))
    if lo <= v <= hi:
        return " This is within the fault-free range."
    return " This is outside the fault-free range."


def measured(e: Evidence) -> Statement:
    name = e.signal[0].upper() + e.signal[1:]
    if e.kind == "residual" and e.expected is not None and e.deviation is not None:
        text = (
            f"{name} was {fmt(e.observed, e.unit)}, against {fmt(e.expected, e.unit)} expected "
            f"for the same conditions ({fmt(e.deviation, 'errors')} typical errors"
            + _range(e, "errors").replace("it ranged", "the gap ranged")
            + ")."
        )
    elif e.kind == "rule":
        text = (
            f"{name} in {fmt(e.observed, 'share')} of applicable minutes" + _range(e, "share") + "."
        )
    else:
        text = f"{name} was {fmt(e.observed, e.unit)}" + _range(e, e.unit) + "."
    return Statement(kind="measured", text=text + _verdict(e), refs=[e.id])


def context_statement(c: Context) -> Statement:
    minutes = fmt(c.diagnosable_minutes, "count")
    text = f"The {c.running} ran steadily for {minutes} minutes in this period"
    if c.dominant_mode:
        text += f", mostly in {c.dominant_mode.replace('_', ' ')} mode"
    if c.outdoor_air_low is not None and c.outdoor_air_high is not None:
        text += (
            f", with outdoor air between {fmt(c.outdoor_air_low, 'degC')} and "
            f"{fmt(c.outdoor_air_high, 'degC')}"
        )
    return Statement(kind="context", text=text + ".", refs=["context"])


def statements(
    kind: str,
    fault: str | None,
    start: object,
    end: object,
    hours: int,
    model: ModelOutput,
    context: Context,
    evidence: list[Evidence],
    library: FaultLibrary,
) -> list[Statement]:
    span = _span(start, end, hours)
    out: list[Statement] = []
    if kind == "fault" and fault is not None:
        title = library.title(fault)
        conf = fmt(model.confidence or 0.0, "probability")
        out.append(Statement(kind="finding", refs=["event", "model"], text=(
            f"Likely {title.lower()} {span}. The diagnosis model gave it {conf} confidence; "
            f"a fault is named only at {fmt(model.cutoff or 0.0, 'probability')} or above."
        )))  # fmt: skip
    elif kind == "inconclusive":
        text = f"Abnormal operation {span}, but no supported fault fits with enough confidence."
        if model.top_class and model.confidence is not None and model.cutoff is not None:
            text += (
                f" Closest match: {library.title(model.top_class).lower()} at "
                f"{fmt(model.confidence, 'probability')}, below the "
                f"{fmt(model.cutoff, 'probability')} needed to name it."
            )
        out.append(Statement(kind="finding", refs=["event", "model"], text=text))
    elif kind == "no_supported_fault":
        out.append(Statement(kind="finding", refs=["event", "detector", "model"], text=(
            f"The detector flagged operation {span} (highest score "
            f"{fmt(model.detector_score, 'score')}, alarm threshold "
            f"{fmt(model.detector_threshold, 'score')}), but the pattern matches none of the "
            "supported faults."
        )))  # fmt: skip
    else:  # not_diagnosable
        out.append(Statement(kind="finding", refs=["event", "detector", "context"], text=(
            f"The detector flagged operation {span}, but the {context.running} was not running "
            "steadily for long enough to diagnose a fault."
        )))  # fmt: skip

    out += [measured(e) for e in evidence]
    out.append(context_statement(context))

    if kind == "fault" and fault is not None:
        text = "This is a model inference from sensor patterns, not a confirmed root cause."
        if model.validation_precision is not None:
            text += (
                f" On validation data, hours named {library.title(fault).lower()} were right "
                f"{fmt(model.validation_precision, 'probability')} of the time."
            )
        out.append(Statement(kind="uncertainty", refs=["model"], text=text))
        out += [
            Statement(kind="recommended", text=c.text, refs=[c.source])
            for c in library.faults[fault].checks
        ]
    elif kind == "no_supported_fault":
        out.append(Statement(kind="uncertainty", refs=["model"], text=(
            "The cause may be a fault FaultIQ does not support, unusual operation, or a false "
            f"alarm. {WHY_NO_CHECKS}"
        )))  # fmt: skip
    elif kind == "inconclusive":
        out.append(Statement(kind="uncertainty", refs=["model"], text=(
            f"{WHY_NO_CHECKS} Review the signals above, or wait for more data."
        )))  # fmt: skip
    else:
        out.append(Statement(kind="uncertainty", refs=["context"], text=(
            f"No diagnosis was attempted for this period. {WHY_NO_CHECKS}"
        )))  # fmt: skip
    return out
