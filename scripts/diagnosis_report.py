"""Phase 4: run the diagnosis experiment and write the results JSON and markdown report.

Usage (from pipeline/):
    uv run python -I ../scripts/diagnosis_report.py ../data/processed/v0.2.0 \
        --json ../docs/diagnosis/results.json --out ../docs/diagnosis-report.md

Interpretation lives in docs/decisions/0022-diagnosis-methodology.md and docs/model-card.md; this
file only reports numbers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from faultiq.diagnosis.experiment import run

DATASETS = {"simulated": "Simulated", "experimental": "ORNL experimental"}
SHORT = {
    "fault_free": "normal",
    "condenser_fouling": "cond. foul",
    "evaporator_fouling": "evap. foul",
    "liquid_line_restriction": "liquid restr.",
    "suction_line_restriction": "suction restr.",
    "refrigerant_overcharge": "overcharge",
    "refrigerant_undercharge": "undercharge",
    "economizer_setpoint_offset": "econ. setpoint",
    "oa_damper_stuck": "damper stuck",
    "sat_sensor_bias": "SAT bias",
}


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def headline(res: dict[str, Any]) -> list[str]:
    lines = [
        "| Dataset | Points | Adopted | Macro-F1 (logistic / LightGBM) | Answered | Named faults right "
        "| Faulty hours: right fault | Normal hours: said no fault |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ds, name in DATASETS.items():
        for ps in ("basic", "all"):
            r = res[ds][ps]
            a = r["main"]["answers"]
            f1 = r["test_macro_f1"]
            lines.append(
                f"| {name} | {ps} | {r['adopted']} | {f1['logistic']:.2f} / {f1['lightgbm']:.2f} "
                f"| {pct(a['answered_share'])} | {pct(a['named_fault_precision'])} "
                f"| {pct(a['faulty_windows']['correct_fault'])} "
                f"| {pct(a['normal_windows']['said_no_fault'])} |"
            )
    return lines


def confusion_table(conf: dict[str, Any]) -> list[str]:
    labels = [SHORT.get(c, c) for c in conf["labels"]]
    lines = ["| True \\ predicted | " + " | ".join(labels) + " |"]
    lines.append("|---|" + "---|" * len(labels))
    for lab, row in zip(labels, conf["matrix"], strict=True):
        lines.append(f"| {lab} | " + " | ".join(str(v) for v in row) + " |")
    return lines


def section(ds: str, ps: str, r: dict[str, Any]) -> list[str]:
    m = r["main"]
    a = m["answers"]
    lines = [
        f"### {DATASETS[ds]}, {ps} points",
        "",
        f"Adopted **{r['adopted']}** (validation macro-F1: logistic {r['validation_macro_f1']['logistic']}, "
        f"LightGBM {r['validation_macro_f1']['lightgbm']}). Confidence cut-off: {r['confidence_cutoffs']}. "
        f"Calibration error of the top class: {m['calibration_error']}.",
        "",
        "| Class | Test hours | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]
    for c in m["per_class"]:
        lines.append(
            f"| {SHORT.get(c['class'], c['class'])} | {c['windows']} | {pct(c['precision'])} "
            f"| {pct(c['recall'])} | {c['f1']:.2f} |"
        )
    lines += ["", "Most likely class, before the confidence cut-off:", ""]
    lines += confusion_table(m["confusion"])
    fw, nw = a["faulty_windows"], a["normal_windows"]
    lines += [
        "",
        "Answers a user would see (with the cut-off):",
        "",
        "| Hours | Right fault | Wrong fault | No supported fault | Inconclusive |",
        "|---|---|---|---|---|",
        f"| Faulty | {pct(fw['correct_fault'])} | {pct(fw['wrong_fault'])} | {pct(fw['said_no_fault'])} "
        f"| {pct(fw['inconclusive'])} |",
        f"| Normal | n/a | {pct(nw['named_a_fault'])} | {pct(nw['said_no_fault'])} | {pct(nw['inconclusive'])} |",
        "",
        "By severity (faulty test hours):",
        "",
        "| Fault | Severity | Hours | Right fault | No supported fault | Inconclusive |",
        "|---|---|---|---|---|---|",
    ]
    for s in m["by_severity"]:
        lines.append(
            f"| {SHORT.get(s['fault'], s['fault'])} | {format(s['intensity'], 'g')} | {s['windows']} "
            f"| {pct(s['correct'])} | {pct(s['said_no_fault'])} | {pct(s['inconclusive'])} |"
        )
    lines += ["", "Deciding feature for named faults (top 3 per fault):", ""]
    lines += ["| Named fault | Feature | Hours |", "|---|---|---|"]
    for e in m["evidence"]:
        lines.append(
            f"| {SHORT.get(e['answer'], e['answer'])} | `{e['top_feature']}` | {e['len']} |"
        )
    e2e = r["end_to_end"]
    lines += [
        "",
        "End to end, on the hours the Phase 3 normal-model detector alarmed on:",
        "",
        "| Alarms | Hours | Right fault | Named a (wrong) fault | No supported fault | Inconclusive | Not diagnosable |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, name in (("faulty_alarms", "True alarms"), ("false_alarms", "False alarms")):
        v = e2e[key]
        lines.append(
            f"| {name} | {v['windows']} | {pct(v.get('correct_fault', 0.0)) if key == 'faulty_alarms' else 'n/a'} "
            f"| {pct(v.get('named_a_fault', 0.0))} | {pct(v.get('said_no_fault', 0.0))} "
            f"| {pct(v.get('inconclusive', 0.0))} | {pct(v.get('not_diagnosable', 0.0))} |"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("processed", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    res = run(args.processed)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(res, indent=2, sort_keys=True, default=str) + "\n")

    lines = [
        "# Diagnosis report: Phase 4 known-fault classifier",
        "",
        (
            f"> Generated by `scripts/diagnosis_report.py` on {res['generated']} (diagnosis {res['diagnosis_version']}, "
            f"pipeline {res['pipeline_version']}). Numbers only; interpretation and limitations are in"
        ),
        "> [ADR 0022](decisions/0022-diagnosis-methodology.md) and the [model card](model-card.md). "
        "Full results: [diagnosis/results.json](diagnosis/results.json).",
        "",
        "**Method in one paragraph.** Each file-hour is one window. A window is diagnosable when the equipment "
        f"the supported faults act on ran steadily for at least {res['min_minutes']} minutes (compressor for the "
        "simulated set, supply fan for ORNL). Features describe behaviour only: medians of physics differences "
        "and ratios, signed residuals from the Phase 3 normal-behaviour models, and the share of minutes "
        "breaking each economizer rule. A logistic regression and LightGBM are fitted on training hours; "
        f"LightGBM is adopted only if it beats the baseline's validation macro-F1 by {res['adopt_margin']}. "
        "The most likely class is shown only when its probability reaches a cut-off tuned on validation hours "
        f"so that named faults are right at least {pct(res['target_named_fault_precision'])} of the time "
        f"(at least {res['min_named_validation_windows']} named hours); otherwise the answer is inconclusive. "
        "Splits are the same as Phase 3.",
        "",
        "**Two views.** *Main*: every diagnosable test hour whose fault could show, plus every diagnosable "
        "normal hour. *End to end*: only the hours Phase 3's normal-model detector alarmed on.",
        "",
        "## Headline results (held-out test hours, main view)",
        "",
        *headline(res),
        "",
        "## Detail",
        "",
    ]
    for ds in DATASETS:
        for ps in ("basic", "all"):
            lines += [*section(ds, ps, res[ds][ps]), ""]
    args.out.write_text("\n".join(lines))
    print(f"Wrote {args.out} and {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
