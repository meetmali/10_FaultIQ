"""Phase 5: run the explanation workflow on every held-out file and check every statement.

Usage (from pipeline/):
    uv run python -I ../scripts/explain_report.py ../data/processed/v0.2.0 --docs ../docs

Writes docs/explanation-report.md, docs/explanations/results.json, example explanations in
docs/explanations/examples/, and the contract docs/contracts/diagnostic-result.schema.json.
Interpretation lives in docs/decisions/0023-explanations.md.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import faultiq
from faultiq.detection.experiment import _manifest
from faultiq.detection.windows import SEASONS, sim_split
from faultiq.explain.check import ExplanationError
from faultiq.explain.library import fault_library
from faultiq.explain.schema import SCHEMA_VERSION, DiagnosticResult, FaultEvent, json_schema
from faultiq.explain.workflow import Diagnoser, explain, fit_experimental, fit_simulated

NAMES = {"simulated": "Simulated", "experimental": "ORNL experimental"}
KINDS = ("fault", "inconclusive", "no_supported_fault", "not_diagnosable")


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def _held_out(processed: Path, dataset: str, point_set: str):  # type: ignore[no-untyped-def]
    """Yield (diagnoser, label, test minutes) for every held-out file."""
    entries = [e for e in _manifest(processed) if e["label"]["dataset"] == dataset and e["output"]]
    if dataset == "simulated":
        diag = fit_simulated(processed, point_set)
        for e in entries:
            m = pl.read_parquet(processed / e["output"])
            yield (
                diag,
                e["label"],
                m.filter(sim_split(pl.col("timestamp").dt.truncate("1h")) == "test"),
            )
        return
    for season in SEASONS:
        diag = fit_experimental(processed, season, point_set)
        for e in entries:
            if e["label"]["season"] == season:
                yield diag, e["label"], pl.read_parquet(processed / e["output"])


def evaluate(
    processed: Path, dataset: str, point_set: str
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], DiagnosticResult]]]:
    results: list[tuple[dict[str, Any], DiagnosticResult]] = []
    failed: list[str] = []
    for diag, label, minutes in _held_out(processed, dataset, point_set):
        try:
            results.append((label, explain(minutes, diag, label["source_name"])))
        except ExplanationError as exc:
            failed.append(f"{label['source_name']}: {exc}")
    faulty = [(lab, r) for lab, r in results if lab["fault"] != "fault_free"]
    normal = [(lab, r) for lab, r in results if lab["fault"] == "fault_free"]

    def kinds(rs: list[tuple[dict[str, Any], DiagnosticResult]]) -> dict[str, int]:
        c = Counter(e.kind for _, r in rs for e in r.events)
        return {k: c.get(k, 0) for k in KINDS}

    named = [(lab["fault"], e) for lab, r in faulty for e in r.events if e.kind == "fault"]
    false_named = [e for _, r in normal for e in r.events if e.kind == "fault"]
    statements = Counter(s.kind for _, r in results for e in r.events for s in e.statements)
    evidence = [ev for _, r in results for e in r.events for ev in e.evidence]
    fault_events = [e for _, r in results for e in r.events if e.kind == "fault"]
    first_outside = [
        e for e in fault_events
        if e.evidence and any("outside the fault-free range" in s.text for s in e.statements[1:2])
    ]  # fmt: skip
    return {
        "files": len(results) + len(failed),
        "results_failing_the_checker": len(failed),
        "failures": failed[:10],
        "hours_scored": sum(r.hours_scored for _, r in results),
        "hours_alarmed": sum(r.hours_alarmed for _, r in results),
        "events_on_faulty_files": kinds(faulty),
        "events_on_fault_free_files": kinds(normal),
        "named_events_right_fault": round(sum(f == e.fault for f, e in named) / len(named), 4) if named else None,
        "named_event_hours_right_fault": (
            round(sum(e.hours for f, e in named if f == e.fault) / sum(e.hours for _, e in named), 4)
            if named else None
        ),
        "named_events_3h_or_longer_right_fault": (
            round(sum(f == e.fault for f, e in named if e.hours >= 3) / n3, 4)
            if (n3 := sum(e.hours >= 3 for _, e in named)) else None
        ),
        "false_alarm_events_named_a_fault": len(false_named),
        "median_event_hours": float(pl.Series([e.hours for _, r in results for e in r.events]).median() or 0),
        "statements": dict(sorted(statements.items())),
        "evidence_items": len(evidence),
        "evidence_with_normal_range": round(
            sum(ev.normal_low is not None for ev in evidence) / max(1, len(evidence)), 4
        ),
        "residual_evidence_with_expected_value": round(
            sum(ev.expected is not None for ev in evidence if ev.kind == "residual")
            / max(1, sum(ev.kind == "residual" for ev in evidence)), 4
        ),
        "named_faults_whose_first_evidence_is_outside_normal": round(
            len(first_outside) / len(fault_events), 4
        ) if fault_events else None,
    }, results  # fmt: skip


def single_event(result: DiagnosticResult, event: FaultEvent) -> DiagnosticResult:
    cited = {c.source for c in event.checks}
    return result.model_copy(
        update={"events": [event], "sources": [s for s in result.sources if s.id in cited]}
    )


def pick_examples(
    sim: list[tuple[dict[str, Any], DiagnosticResult]],
    exp: list[tuple[dict[str, Any], DiagnosticResult]],
) -> dict[str, DiagnosticResult]:
    """Longest event of a few telling kinds, including a known failure."""

    def longest(rs: list[tuple[dict[str, Any], DiagnosticResult]], ok) -> DiagnosticResult | None:  # type: ignore[no-untyped-def]
        best = None
        for lab, r in rs:
            for e in r.events:
                if ok(lab, e) and (best is None or e.hours > best[1].hours):
                    best = (r, e)
        return single_event(*best) if best else None

    picks = {
        "simulated-condenser-fouling": longest(sim, lambda lab, e: e.fault == "condenser_fouling" == lab["fault"]),
        "simulated-false-alarm-on-normal-unit": longest(sim, lambda lab, e: lab["fault"] == "fault_free" and e.kind == "fault"),
        "ornl-damper-stuck": longest(exp, lambda lab, e: e.fault == "oa_damper_stuck" == lab["fault"]),
        "ornl-sensor-bias": longest(exp, lambda lab, e: e.fault == "sat_sensor_bias" == lab["fault"]),
        "inconclusive": longest(sim + exp, lambda lab, e: e.kind == "inconclusive"),
        "no-supported-fault": longest(sim + exp, lambda lab, e: e.kind == "no_supported_fault"),
    }  # fmt: skip
    return {k: v for k, v in picks.items() if v is not None}


def render(name: str, r: DiagnosticResult) -> list[str]:
    e = r.events[0]
    lines = [
        f"### {name}",
        "",
        f"`{r.source}`, {r.dataset}, {r.point_set} points. Event kind: **{e.kind}**.",
        "",
    ]
    for s in e.statements:
        lines.append(f"- *{s.kind}*: {s.text} <sub>[{', '.join(s.refs)}]</sub>")
    return [*lines, ""]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("processed", type=Path)
    parser.add_argument("--docs", type=Path, required=True)
    args = parser.parse_args(argv)
    docs: Path = args.docs

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": faultiq.PIPELINE_VERSION,
        "generated": datetime.now(UTC).date().isoformat(),
        "library_review_status": fault_library().review_status,
    }
    kept: dict[str, list[tuple[dict[str, Any], DiagnosticResult]]] = {}
    for ds in NAMES:
        out[ds] = {}
        for ps in ("basic", "all"):
            out[ds][ps], results = evaluate(args.processed, ds, ps)
            if ps == "all":
                kept[ds] = results
    examples = pick_examples(kept["simulated"], kept["experimental"])

    (docs / "contracts").mkdir(parents=True, exist_ok=True)
    (docs / "contracts" / "diagnostic-result.schema.json").write_text(json_schema())
    ex_dir = docs / "explanations" / "examples"
    ex_dir.mkdir(parents=True, exist_ok=True)
    for name, r in examples.items():
        (ex_dir / f"{name}.json").write_text(r.model_dump_json(indent=2) + "\n")
    (docs / "explanations" / "results.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n"
    )

    lines = [
        "# Explanation report: Phase 5 evidence-grounded explanations",
        "",
        f"> Generated by `scripts/explain_report.py` on {out['generated']} (result schema {SCHEMA_VERSION}, "
        f"pipeline {out['pipeline_version']}). Numbers only; interpretation is in",
        "> [ADR 0023](decisions/0023-explanations.md). Full numbers: [explanations/results.json](explanations/results.json). "
        "Contract: [contracts/diagnostic-result.schema.json](contracts/diagnostic-result.schema.json).",
        "",
        "**Method.** The bounded workflow (validate, context, detect, diagnose, evidence, explain) ran on every held-out "
        "file: simulated test days 82-99 with the diagnoser trained on days 0-59, and each ORNL season with the fold "
        "that held it out. Labels were never given to the workflow; they were joined afterwards to score events. "
        "Every result went through the claim checker, which rejects a result if any statement cites a missing "
        "reference, contains a number it doesn't cite, names an unsupported fault, sounds certain, or recommends "
        "a check that isn't in the fault library.",
        "",
        f"Fault library review status: **{out['library_review_status']}**.",
        "",
        "## Results",
        "",
        "| Dataset | Points | Files | Rejected by checker | Alarmed hours | Events (faulty files) | Named events: right fault (by hours; events of 3 h or more) | Events on fault-free files |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ds, name in NAMES.items():
        for ps in ("basic", "all"):
            v = out[ds][ps]
            f, n = v["events_on_faulty_files"], v["events_on_fault_free_files"]
            lines.append(
                f"| {name} | {ps} | {v['files']} | {v['results_failing_the_checker']} | {v['hours_alarmed']} "
                f"| {sum(f.values())} ({f['fault']} named, {f['inconclusive']} inconclusive, "
                f"{f['no_supported_fault']} unmatched, {f['not_diagnosable']} not diagnosable) "
                f"| {pct(v['named_events_right_fault'])} ({pct(v['named_event_hours_right_fault'])}; "
                f"{pct(v['named_events_3h_or_longer_right_fault'])}) "
                f"| {sum(n.values())} ({n['fault']} named a fault) |"
            )
    lines += [
        "",
        "| Dataset | Points | Statements by kind | Residual evidence with an expected value "
        "| Evidence with a normal range | Named faults whose first evidence is outside it |",
        "|---|---|---|---|---|---|",
    ]
    for ds, name in NAMES.items():
        for ps in ("basic", "all"):
            v = out[ds][ps]
            st = ", ".join(f"{k} {n}" for k, n in v["statements"].items())
            lines.append(
                f"| {name} | {ps} | {st} | {pct(v['residual_evidence_with_expected_value'])} "
                f"| {pct(v['evidence_with_normal_range'])} "
                f"| {pct(v['named_faults_whose_first_evidence_is_outside_normal'])} |"
            )
    lines += ["", "## Example explanations (all points, longest event of each kind)", ""]
    for name, r in examples.items():
        lines += render(name, r)
    (docs / "explanation-report.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                ds: {
                    ps: {
                        k: out[ds][ps][k]
                        for k in (
                            "files",
                            "results_failing_the_checker",
                            "events_on_faulty_files",
                            "events_on_fault_free_files",
                            "named_events_right_fault",
                            "named_event_hours_right_fault",
                        )
                    }
                    for ps in out[ds]
                }
                for ds in NAMES
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
