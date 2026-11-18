"""Validation gate: accept, accept with warnings, or quarantine a loaded file.

Errors quarantine the file (it is kept out of analysis and its report says exactly why). Warnings
let it through but count every imperfection, so nothing is hidden. Messages are written for the
person who has to fix the export, not for developers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import polars as pl

from faultiq.ingestion.loader import LoadResult

Status = Literal["accepted", "accepted_with_warnings", "quarantined"]


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    code: str
    message: str


@dataclass
class ValidationResult:
    status: Status
    issues: list[Issue] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.status != "quarantined"

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "issues": [asdict(i) for i in self.issues]}


@dataclass(frozen=True)
class Requirements:
    """Each group is satisfied by any one of its roles."""

    groups: tuple[tuple[str, ...], ...]
    max_missing_share: float = 0.5
    mostly_empty_warning_share: float = 0.5
    missing_warning_share: float = 0.05


# What any RTU analysis needs: supply air, outdoor air, an air temperature to compare against,
# and some signal that tells whether the compressor runs.
RTU_MINIMUM = Requirements(
    groups=(
        ("sat",),
        ("oat",),
        ("rat", "mat", "zone_temp"),
        ("comp_stage", "power_comp", "power_comp_1"),
    )
)


def _share(n: int, total: int) -> str:
    return f"{n:,} of {total:,} rows ({n / total:.1%})" if total else f"{n:,} rows"


def validate(result: LoadResult, requirements: Requirements = RTU_MINIMUM) -> ValidationResult:
    df, rep = result.data, result.report
    issues: list[Issue] = []

    def err(code: str, msg: str) -> None:
        issues.append(Issue("error", code, msg))

    def warn(code: str, msg: str) -> None:
        issues.append(Issue("warning", code, msg))

    total = df.height
    if total == 0:
        err("empty_file", "The file has no data rows.")
        return ValidationResult("quarantined", issues)

    # Timestamps
    if rep.timestamp_unparsed:
        msg = f"{_share(rep.timestamp_unparsed, total)} have a timestamp that could not be read."
        (err if rep.timestamp_unparsed / total > 0.01 else warn)("unreadable_timestamps", msg)
    steps = df["timestamp"].diff().dt.total_seconds()
    backwards = int((steps < 0).sum())
    if backwards:
        err(
            "timestamps_out_of_order",
            f"Timestamps go backwards {backwards:,} times. "
            "Sort the export by time and upload it again.",
        )
    if rep.duplicate_timestamps:
        warn(
            "duplicate_timestamps",
            f"{rep.duplicate_timestamps:,} repeated timestamps. The first reading of each is kept.",
        )
    if rep.gaps_over_1min:
        warn(
            "gaps",
            f"{rep.gaps_over_1min:,} gaps longer than one minute. "
            "Missing minutes are flagged, not filled.",
        )

    # Required sensors
    present = set(df.columns)
    for group in requirements.groups:
        mapped = [r for r in group if r in present]
        names = " or ".join(group)
        if not mapped:
            err(
                "missing_required_role",
                f"No column is mapped to {names}, which every RTU analysis needs.",
            )
            continue
        all_missing = df.select(
            pl.all_horizontal([pl.col(r).is_null() for r in mapped])
        ).to_series()
        missing = int(all_missing.sum())
        if missing / total > requirements.max_missing_share:
            err("required_role_mostly_empty", f"{names} is missing on {_share(missing, total)}.")

    # Value-level problems, one issue per kind with the roles affected
    for code, counts, text in (
        ("unreadable_values", rep.unparseable_values, "values that are not numbers"),
        ("infinite_values", rep.infinite_values, "infinite values"),
        ("out_of_range_values", rep.out_of_range, "physically implausible values"),
    ):
        hit = {role: n for role, n in counts.items() if n}
        if hit:
            detail = ", ".join(f"{role} {n:,}" for role, n in sorted(hit.items()))
            warn(code, f"Set to missing: {text} ({detail}).")
    if rep.dropout_rows:
        warn(
            "dropout_rows",
            f"{rep.dropout_rows:,} logging dropouts "
            "(every probe sensor read exactly 0) set to missing.",
        )
    sparse = {
        role: n
        for role, n in rep.final_nulls.items()
        if n / total > requirements.mostly_empty_warning_share
    }
    if sparse:
        detail = ", ".join(f"{r} {n / total:.0%}" for r, n in sorted(sparse.items()))
        warn("mostly_empty_columns", f"Columns missing on most rows: {detail}.")
    patchy = {
        role: n
        for role, n in rep.final_nulls.items()
        if requirements.missing_warning_share < n / total <= requirements.mostly_empty_warning_share
    }
    if patchy:
        detail = ", ".join(f"{r} {n / total:.0%}" for r, n in sorted(patchy.items()))
        warn("missing_values", f"Columns with notable gaps (flagged, not filled): {detail}.")
    if rep.unmapped_columns:
        warn(
            "unmapped_columns",
            f"Ignored columns not in the mapping: {', '.join(rep.unmapped_columns)}.",
        )

    if any(i.severity == "error" for i in issues):
        return ValidationResult("quarantined", issues)
    return ValidationResult("accepted_with_warnings" if issues else "accepted", issues)
