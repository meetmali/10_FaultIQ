"""The fault library as served by the API (ADR 0025).

Hand-written, cited text comes from fault_library.toml. Everything measured comes from FaultIQ's
held-out diagnosis results (docs/diagnosis/results.json, all points), so it is never asserted:
- symptoms: the signals that most often decided the diagnosis for that fault,
- often confused with: both directions of the confusion matrix,
- performance: precision and recall, and how often each severity was named correctly.

The output is committed in the API project and a test regenerates it, so the two can't drift.
"""

from __future__ import annotations

import json
from typing import Any

from faultiq.explain.library import FaultLibrary
from faultiq.explain.text import signal

LIBRARY_VERSION = 1
DATASET_OF = {
    "simulated": ("simulated", "Simulated rooftop unit (LBNL)"),
    "experimental": ("experimental", "ORNL test rooftop unit (LBNL)"),
}
MIN_CONFUSED_HOURS = 5  # ignore a handful of stray hours
DIAGNOSIS_SOURCE = "faultiq-diagnosis"


def _cited(item: Any) -> dict[str, str] | None:
    return None if item is None else {"text": item.text, "source": item.source}


def _dataset_for(fault: str, results: dict[str, Any]) -> str:
    for ds in DATASET_OF:
        if any(c["class"] == fault for c in results[ds]["all"]["main"]["per_class"]):
            return ds
    raise ValueError(f"{fault} has no held-out results")


def _measured(fault: str, main: dict[str, Any]) -> dict[str, Any]:
    labels = main["confusion"]["labels"]
    matrix = main["confusion"]["matrix"]
    i = labels.index(fault)
    confused = []
    for j, other in enumerate(labels):
        if j == i:
            continue
        as_other, from_other = matrix[i][j], matrix[j][i]
        if as_other + from_other >= MIN_CONFUSED_HOURS:
            confused.append({
                "fault": other, "named_as_other_hours": as_other,
                "other_named_as_this_hours": from_other,
            })  # fmt: skip
    confused.sort(key=lambda c: -(c["named_as_other_hours"] + c["other_named_as_this_hours"]))
    symptoms = []
    for e in main["evidence"]:
        if e["answer"] == fault:
            name, unit = signal(e["top_feature"])
            kind = e["top_feature"].split(":", 1)[0]
            symptoms.append({
                "feature": e["top_feature"], "signal": name, "unit": unit,
                "kind": {"resid": "residual", "med": "physics", "rule": "rule"}.get(kind, kind),
                "deciding_hours": e["len"],
            })  # fmt: skip
    per_class = next(c for c in main["per_class"] if c["class"] == fault)
    severity = [
        {
            "intensity": s["intensity"],
            "hours": s["windows"],
            "right_fault": round(s["correct"], 4),
            "said_no_fault": round(s["said_no_fault"], 4),
            "inconclusive": round(s["inconclusive"], 4),
        }
        for s in main["by_severity"]
        if s["fault"] == fault
    ]
    return {
        "symptoms": symptoms,
        "confused_with": confused,
        "performance": {
            "test_hours": per_class["windows"],
            "precision": per_class["precision"],
            "recall": per_class["recall"],
            "by_severity": severity,
        },
    }


def export_library(library: FaultLibrary, results: dict[str, Any]) -> dict[str, Any]:
    faults = []
    used = {DIAGNOSIS_SOURCE}
    for name, info in sorted(library.faults.items()):
        ds = _dataset_for(name, results)
        entry = {
            "id": name,
            "title": info.title,
            "equipment": info.equipment,
            "dataset": DATASET_OF[ds][0],
            "dataset_label": DATASET_OF[ds][1],
            "intensity_unit": info.intensity_unit,
            "definition": _cited(info.definition),
            "observed": _cited(info.observed),
            "causes": [_cited(c) for c in info.causes],
            "checks": [_cited(c) for c in info.checks],
            "measured": {"source": DIAGNOSIS_SOURCE, **_measured(name, results[ds]["all"]["main"])},
        }
        used |= {
            c.source for c in (info.definition, info.observed, *info.causes, *info.checks) if c
        }
        faults.append(entry)
    return {
        "version": LIBRARY_VERSION,
        "review_status": library.review_status,
        "diagnosis_version": results["diagnosis_version"],
        "sources": [
            {"id": s.id, "citation": s.citation, "url": s.url}
            for s in sorted(library.sources.values(), key=lambda s: s.id)
            if s.id in used
        ],
        "faults": faults,
    }


def library_json(library: FaultLibrary, results: dict[str, Any]) -> str:
    return json.dumps(export_library(library, results), indent=2, ensure_ascii=False) + "\n"
