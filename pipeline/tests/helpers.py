"""Shared helpers for synthetic test data. Tests never need the licensed raw dataset."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path


def write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> Path:
    lines = [",".join(columns)] + [",".join("" if v is None else str(v) for v in r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def minutes(n: int, start: str = "2024-06-01 08:00:00", step: int = 1) -> list[str]:
    t0 = datetime.fromisoformat(start)
    return [(t0 + timedelta(minutes=i * step)).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]


USER_MAPPING_TOML = """
name = "test_rtu"

[timestamp]
column = "Timestamp"
format = "%Y-%m-%d %H:%M:%S"

[points]
"SAT (F)" = { role = "sat", unit = "degF" }
"OAT (F)" = { role = "oat", unit = "degF" }
"RAT (F)" = { role = "rat", unit = "degF" }
"MAT (F)" = { role = "mat", unit = "degF" }
"OA Damper %" = { role = "oa_damper_cmd", unit = "percent" }
"Comp Stage" = { role = "comp_stage", unit = "fraction" }
"Fan kW" = { role = "power_fan", unit = "kW" }

[excluded]
"Spare AI" = "not connected"
"""

USER_COLUMNS = [
    "Timestamp",
    "SAT (F)",
    "OAT (F)",
    "RAT (F)",
    "MAT (F)",
    "OA Damper %",
    "Comp Stage",
    "Fan kW",
    "Spare AI",
]


def user_rows(
    n: int, comp: float = 1.0, damper: float = 10.0, start: str = "2024-06-01 08:00:00"
) -> list[list[object]]:
    return [[ts, 55.0, 85.0, 75.0, 76.0, damper, comp, 1.2, 0] for ts in minutes(n, start)]
