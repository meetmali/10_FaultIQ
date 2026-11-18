"""Phase 1 EDA: quantify what each fault does to the readings (numbers only, no raw data).

Usage (from pipeline/):
    uv run python -I ../scripts/eda_report.py ../data/raw/LBNL_FDD_Data_Sets_RTU_all_3 \
        --out ../docs/eda-report.md

Simulated files share identical timestamps and weather, so each fault is compared with the baseline
minute by minute, only where the compressor runs in both. That isolates the fault's own effect.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
from faultiq.ingestion.lbnl import load_lbnl_file

# R410A saturation curve (approximate), used to derive suction superheat.
_T_C = np.array([-20, -10, 0, 5, 10, 15, 20, 25, 30, 40, 50], dtype=float)
_P_KPA = np.array(
    [400, 573, 798, 933, 1085, 1253, 1440, 1646, 1875, 2420, 3060], dtype=float
)

SIM_ALL = [
    "sat",
    "zone_temp",
    "refg_suct_pres",
    "refg_disc_pres",
    "superheat",
    "refg_disc_temp",
    "power_comp",
    "cap_total",
]
SIM_BASIC = ["sat", "zone_temp", "comp_stage"]


def superheat(df: pl.DataFrame) -> pl.Series:
    tsat = np.interp(df["refg_suct_pres"].to_numpy(), _P_KPA, _T_C)
    return pl.Series("superheat", df["refg_suct_temp"].to_numpy() - tsat)


def fmt(x: float, nd: int = 2) -> str:
    return "n/a" if x is None or np.isnan(x) else f"{x:+.{nd}f}"


def simulated_section(root: Path) -> list[str]:
    files = sorted((root / "Simulated RTU").glob("*.csv"))
    loaded = {p.name: load_lbnl_file(p) for p in files}
    base = loaded["RTU_sim_baseline.csv"].data
    base = base.with_columns(superheat(base))
    lines = [
        "## Simulated set: fault signatures against the baseline",
        "",
        "Each value is the **median of (fault minus baseline)** at the same minute, using only minutes",
        "where the compressor runs in both files. Units: °C for temperatures and superheat, kPa for",
        "pressures, W for power and capacity. `run time` is the share of minutes with the compressor on.",
        "",
        "| File | Run time | " + " | ".join(SIM_ALL) + " |",
        "|---|---|" + "---|" * len(SIM_ALL),
    ]
    basic_rows = []
    for name, lf in loaded.items():
        d = lf.data.with_columns(superheat(lf.data))
        on = (d["comp_stage"] > 0.1) & (base["comp_stage"] > 0.1)
        runtime = float((d["comp_stage"] > 0.1).mean() or 0)
        diffs = [
            float(np.nanmedian((d[c] - base[c]).filter(on).to_numpy())) for c in SIM_ALL
        ]
        label = name.removeprefix("RTU_sim_").removesuffix(".csv")
        lines.append(
            f"| {label} | {runtime:.0%} | "
            + " | ".join(fmt(v, 1) for v in diffs)
            + " |"
        )
        b = [
            float(np.nanmedian((d[c] - base[c]).filter(on).to_numpy()))
            for c in ("sat", "zone_temp")
        ]
        b.append(float((d["comp_stage"] - base["comp_stage"]).mean() or 0))
        basic_rows.append((label, runtime, b))
    lines += [
        "",
        "### Basic BAS points only",
        "",
        "The same comparison using only points a typical building automation system records.",
        "`comp_stage` is the mean difference over all minutes (positive means the compressor works harder).",
        "",
        "| File | Run time | sat (°C) | zone_temp (°C) | comp_stage |",
        "|---|---|---|---|---|",
    ]
    for label, runtime, b in basic_rows:
        lines.append(
            f"| {label} | {runtime:.0%} | {fmt(b[0])} | {fmt(b[1])} | {fmt(b[2], 3)} |"
        )
    return lines


def oaf(df: pl.DataFrame) -> pl.Series:
    """Outdoor-air fraction from temperatures, only where |OAT - RAT| >= 5 K (else unreliable)."""
    spread = df["oat"] - df["rat"]
    frac = (df["mat"] - df["rat"]) / spread
    return pl.select(pl.when(spread.abs() >= 5).then(frac).otherwise(None)).to_series()


def experimental_section(root: Path) -> list[str]:
    files = sorted((root / "ORNL_RTU").glob("*.csv"))
    rows = []
    for p in files:
        lf = load_lbnl_file(p)
        occ = lf.data.filter((pl.col("occupied") == 1) & ~pl.col("qc_dropout"))
        f = oaf(occ).drop_nulls()
        label = lf.label
        rows.append(
            (
                label.fault,
                label.intensity,
                label.season or "",
                float(occ["oa_damper_cmd"].median() or 0),
                float(f.median()) if f.len() else float("nan"),
                f.len(),
                float(occ["sat"].median() or float("nan")),
            )
        )
    lines = [
        "## Experimental set: economizer evidence during occupied hours",
        "",
        "`OAF` is the outdoor-air fraction implied by temperatures, (MAT − RAT) / (OAT − RAT), computed only",
        "on minutes where |OAT − RAT| ≥ 5 K. Comparing it with the damper command shows whether the damper",
        "does what it is told. `n` is the number of minutes that met the 5 K condition.",
        "",
        "| Fault | Intensity | Season | Damper cmd (median) | OAF (median) | n | SAT °C (median) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(
        rows, key=lambda r: (r[0], r[1] if r[1] is not None else -99, r[2])
    ):
        inten = "" if r[1] is None else f"{r[1]:g}"
        oaf_txt = "n/a" if np.isnan(r[4]) else f"{r[4]:.2f}"
        lines.append(
            f"| {r[0]} | {inten} | {r[2]} | {r[3]:.2f} | {oaf_txt} | {r[5]} | {r[6]:.1f} |"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    lines = [
        "# EDA report: LBNL RTU data sets",
        "",
        f"> Generated by `scripts/eda_report.py` on {date.today().isoformat()}. Numbers only, no raw data.",
        "> Interpretation is in the [dataset card](dataset-card.md) and the summary below each table.",
        "",
        *simulated_section(args.root),
        "",
        *experimental_section(args.root),
        "",
    ]
    args.out.write_text("\n".join(lines))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
