"""Profile the raw LBNL RTU CSV files (Phase 1 dataset discovery).

Usage (from pipeline/):
    uv run python -I ../scripts/inspect_dataset.py ../data/raw/LBNL_FDD_Data_Sets_RTU_all_3 \
        --out ../data/interim/raw_profile.json

Reads every CSV read-only and writes one JSON profile: schema, timestamp regularity, missing values,
value ranges and compressor run time per file. Raw files are never modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

NULL_TOKENS = ["NAN", "NaN", "nan", "NA", ""]
TS_COL = "Datetime"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def dataset_of(path: Path) -> str:
    parent = path.parent.name.lower()
    if "simulated" in parent:
        return "simulated"
    if "ornl" in parent:
        return "experimental"
    if "field" in parent:
        return "field"
    return "unknown"


def compressor_on(df: pl.DataFrame, dataset: str) -> pl.Series | None:
    """Best-effort compressor-running flag, used only to estimate fault observability."""
    if dataset == "simulated" and "RTU_STG_STA" in df.columns:
        return df["RTU_STG_STA"] > 0.1
    watt_cols = [c for c in df.columns if c.startswith("RTU_COMP_WATT")]
    if watt_cols:
        total = df.select(
            pl.sum_horizontal([pl.col(c).fill_null(0) for c in watt_cols])
        ).to_series()
        return total > 200.0
    return None


def profile_file(path: Path) -> dict[str, Any]:
    dataset = dataset_of(path)
    df = pl.read_csv(path, null_values=NULL_TOKENS, infer_schema_length=20000)
    info: dict[str, Any] = {
        "file": path.name,
        "dataset": dataset,
        "bytes": path.stat().st_size,
        "rows": df.height,
        "columns": df.columns,
    }

    if TS_COL not in df.columns:
        info["timestamp_error"] = f"no '{TS_COL}' column"
        return info

    ts = df[TS_COL].cast(pl.Utf8).str.strptime(pl.Datetime, TS_FORMAT, strict=False)
    diffs = ts.diff().dt.total_seconds().drop_nulls()
    info["timestamp"] = {
        "unparsed": int(ts.null_count()),
        "start": str(ts.min()),
        "end": str(ts.max()),
        "span_days": round((ts.max() - ts.min()).total_seconds() / 86400, 2),  # type: ignore[operator]
        "duplicates": int(df.height - ts.n_unique()),
        "non_increasing": int((diffs <= 0).sum()),
        "gaps_over_60s": int((diffs > 60).sum()),
        "max_gap_minutes": round(float(diffs.max() or 0) / 60, 1),
        "step_counts": {
            str(int(k)): int(v)
            for k, v in diffs.value_counts()
            .sort("count", descending=True)
            .head(3)
            .iter_rows()
        },
    }

    cols: dict[str, Any] = {}
    for name in df.columns:
        if name == TS_COL:
            continue
        s = df[name]
        entry: dict[str, Any] = {"dtype": str(s.dtype), "nulls": int(s.null_count())}
        if s.dtype.is_numeric():
            entry.update(
                min=None if s.min() is None else round(float(s.min()), 4),  # type: ignore[arg-type]
                max=None if s.max() is None else round(float(s.max()), 4),  # type: ignore[arg-type]
                mean=None if s.mean() is None else round(float(s.mean()), 4),  # type: ignore[arg-type]
                distinct=int(s.n_unique()),
            )
        else:
            entry["non_numeric_examples"] = s.drop_nulls().unique().head(5).to_list()
        cols[name] = entry
    info["column_stats"] = cols

    on = compressor_on(df, dataset)
    if on is not None:
        info["compressor_on_fraction"] = round(float(on.mean() or 0), 4)
    if "OCCU_MOD" in df.columns:
        info["occupied_fraction"] = round(float(df["OCCU_MOD"].mean() or 0), 4)
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", type=Path, help="folder containing the unzipped dataset"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="where to write the JSON profile"
    )
    args = parser.parse_args(argv)

    files = sorted(args.root.rglob("*.csv"))
    if not files:
        print(f"No CSV files under {args.root}", file=sys.stderr)
        return 1

    profiles = []
    for i, path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {path.parent.name}/{path.name}", file=sys.stderr)
        profiles.append(profile_file(path))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"root": str(args.root), "files": profiles}, indent=2, default=str)
    )
    print(f"Wrote {len(profiles)} profiles to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
