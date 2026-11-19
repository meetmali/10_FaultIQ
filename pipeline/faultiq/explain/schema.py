"""The diagnostic result: the one record every later layer reads (ADR 0023).

The worker writes it as JSON; the .NET API stores and serves it; the frontend renders it. Its JSON
Schema is committed at docs/contracts/diagnostic-result.schema.json, and a test fails if the two
drift apart, so a change here is always a deliberate contract change.

Every statement points at what it rests on (`refs`): an evidence item, the model output, the
detector, the operating context, the event itself, or a cited source. Nothing else is allowed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"

AnswerKind = Literal["fault", "no_supported_fault", "inconclusive", "not_diagnosable"]
StatementKind = Literal["finding", "measured", "context", "uncertainty", "recommended"]
EvidenceKind = Literal["residual", "physics", "rule"]

# Fixed reference names a statement may cite besides evidence ids and source ids.
FIXED_REFS = ("event", "model", "detector", "context")


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Source(Frozen):
    """A published reference a recommended check rests on."""

    id: str
    citation: str
    url: str | None = None


class Check(Frozen):
    text: str
    source: str = Field(description="Id of the Source this check is taken from")


class Evidence(Frozen):
    """One signal behind the answer, summarised over the event's diagnosable minutes."""

    id: str
    feature: str = Field(description="Model feature, e.g. resid:refg_disc_pres")
    signal: str = Field(description="Plain name, e.g. discharge pressure")
    kind: EvidenceKind
    unit: str
    observed: float = Field(description="Median over the event (share of minutes for rules)")
    expected: float | None = Field(
        None, description="Normal-model expectation for the same conditions; residuals only"
    )
    deviation: float | None = Field(
        None, description="Observed minus expected, in typical fault-free errors; residuals only"
    )
    normal_low: float | None = Field(
        None,
        description="5th percentile on fault-free validation hours: of `deviation` for residuals, "
        "of `observed` otherwise",
    )
    normal_high: float | None = Field(None, description="95th percentile, same basis")
    hours: int = Field(description="Event hours in which this signal was available")
    weight: float = Field(
        description="Diagnosis evidence: summed contribution toward the answer (log-odds). "
        "Detector evidence: median absolute deviation"
    )


class Context(Frozen):
    running: str = Field(description="Equipment the supported faults act on")
    diagnosable_minutes: int = Field(description="Steady minutes with that equipment running")
    dominant_mode: str | None
    outdoor_air_low: float | None
    outdoor_air_high: float | None


class ModelOutput(Frozen):
    answer: str = Field(description="Fault name, or the answer kind when no fault is named")
    top_class: str | None = Field(description="Most likely class before the confidence cut-off")
    confidence: float | None = Field(description="Median hourly probability of top_class")
    cutoff: float | None = Field(description="Confidence needed to name a fault")
    validation_precision: float | None = Field(
        description="Share of validation hours named as this fault that really were it"
    )
    detector_score: float = Field(description="Highest hourly detector score in the event")
    detector_threshold: float
    model_family: str


class Statement(Frozen):
    kind: StatementKind
    text: str
    refs: list[str] = Field(min_length=1)


class FaultEvent(Frozen):
    """Consecutive alarmed hours with the same answer."""

    id: str
    start: datetime
    end: datetime = Field(description="End of the last hour (exclusive)")
    hours: int
    kind: AnswerKind
    fault: str | None
    fault_title: str | None
    model: ModelOutput
    context: Context
    evidence: list[Evidence]
    checks: list[Check]
    statements: list[Statement]


class DiagnosticResult(Frozen):
    schema_version: str = SCHEMA_VERSION
    pipeline_version: str
    diagnosis_version: str
    source: str = Field(description="Input file name")
    dataset: str
    point_set: str
    period_start: datetime | None
    period_end: datetime | None
    hours_total: int
    hours_scored: int = Field(description="Hours with enough steady minutes to score")
    hours_alarmed: int
    supported_faults: list[str]
    library_review_status: str = Field(
        description="Whether an HVAC professional has reviewed the fault library's checks"
    )
    events: list[FaultEvent]
    sources: list[Source] = Field(description="Every source cited by a check in this result")


def json_schema() -> str:
    """The contract file committed at docs/contracts/diagnostic-result.schema.json."""
    import json

    schema = DiagnosticResult.model_json_schema()
    _drop_field_titles(schema)
    schema["$id"] = f"https://github.com/meetmali/FaultIQ/diagnostic-result/{SCHEMA_VERSION}"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def _drop_field_titles(node: object) -> None:
    """Pydantic titles every field ("Hours", "Source"); type generators turn those into clashing
    aliases (Source vs Source2). Model titles stay; field titles go."""
    if isinstance(node, dict):
        for prop in node.get("properties", {}).values():
            if isinstance(prop, dict):
                prop.pop("title", None)
        for value in node.values():
            _drop_field_titles(value)
    elif isinstance(node, list):
        for value in node:
            _drop_field_titles(value)
