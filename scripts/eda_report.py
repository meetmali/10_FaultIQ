"""Phase 1 EDA: quantify what each fault does to the readings (numbers and charts, no raw data).

Usage (from pipeline/):
    uv run --group eda python -I ../scripts/eda_report.py \
        ../data/raw/LBNL_FDD_Data_Sets_RTU_all_3 --out ../docs/eda-report.md --plots ../docs/eda

Simulated files share identical timestamps and weather, so each fault is compared with the baseline
minute by minute, only where the compressor runs in both. That isolates the fault's own effect.
Charts are drawn from the same numbers as the tables, which serve as their table view.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
FAULT_ORDER = [
    "evaporator_fouling",
    "suction_line_restriction",
    "liquid_line_restriction",
    "condenser_fouling",
    "refrigerant_overcharge",
    "refrigerant_undercharge",
]
FAULT_NAMES = {
    "evaporator_fouling": "Evaporator fouling",
    "suction_line_restriction": "Suction-line restriction",
    "liquid_line_restriction": "Liquid-line restriction",
    "condenser_fouling": "Condenser fouling",
    "refrigerant_overcharge": "Overcharge",
    "refrigerant_undercharge": "Undercharge",
}
SENSOR_TOLERANCE_C = 0.5  # typical BAS duct temperature sensor tolerance


@dataclass
class SimResult:
    label: str
    fault: str
    intensity: float | None
    unit: str | None
    runtime: float
    diffs: dict[str, float]
    comp_stage_diff: float


@dataclass
class ExpResult:
    fault: str
    intensity: float | None
    season: str
    damper_cmd: float
    oaf: float
    n: int
    sat: float


def superheat(df: pl.DataFrame) -> pl.Series:
    tsat = np.interp(df["refg_suct_pres"].to_numpy(), _P_KPA, _T_C)
    return pl.Series("superheat", df["refg_suct_temp"].to_numpy() - tsat)


def fmt(x: float, nd: int = 2) -> str:
    return "n/a" if x is None or np.isnan(x) else f"{x:+.{nd}f}"


def analyse_simulated(root: Path) -> list[SimResult]:
    loaded = {
        p.name: load_lbnl_file(p)
        for p in sorted((root / "Simulated RTU").glob("*.csv"))
    }
    base = loaded["RTU_sim_baseline.csv"].data
    base = base.with_columns(superheat(base))
    results = []
    for name, lf in loaded.items():
        d = lf.data.with_columns(superheat(lf.data))
        on = (d["comp_stage"] > 0.1) & (base["comp_stage"] > 0.1)
        diffs = {
            c: float(np.nanmedian((d[c] - base[c]).filter(on).to_numpy()))
            for c in SIM_ALL
        }
        results.append(
            SimResult(
                label=name.removeprefix("RTU_sim_").removesuffix(".csv"),
                fault=lf.label.fault,
                intensity=lf.label.intensity,
                unit=lf.label.intensity_unit,
                runtime=float((d["comp_stage"] > 0.1).mean() or 0),
                diffs=diffs,
                comp_stage_diff=float(
                    (d["comp_stage"] - base["comp_stage"]).mean() or 0
                ),
            )
        )
    return results


def oaf(df: pl.DataFrame) -> pl.Series:
    """Outdoor-air fraction from temperatures, only where |OAT - RAT| >= 5 K (else unreliable)."""
    spread = df["oat"] - df["rat"]
    frac = (df["mat"] - df["rat"]) / spread
    return pl.select(pl.when(spread.abs() >= 5).then(frac).otherwise(None)).to_series()


def analyse_experimental(root: Path) -> list[ExpResult]:
    results = []
    for p in sorted((root / "ORNL_RTU").glob("*.csv")):
        lf = load_lbnl_file(p)
        occ = lf.data.filter((pl.col("occupied") == 1) & ~pl.col("qc_dropout"))
        f = oaf(occ).drop_nulls()
        results.append(
            ExpResult(
                fault=lf.label.fault,
                intensity=lf.label.intensity,
                season=lf.label.season or "",
                damper_cmd=float(occ["oa_damper_cmd"].median() or 0),
                oaf=float(f.median()) if f.len() else float("nan"),
                n=f.len(),
                sat=float(occ["sat"].median() or float("nan")),
            )
        )
    return sorted(
        results,
        key=lambda r: (
            r.fault,
            r.intensity if r.intensity is not None else -99,
            r.season,
        ),
    )


def simulated_tables(results: list[SimResult]) -> list[str]:
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
    for r in results:
        cells = " | ".join(fmt(r.diffs[c], 1) for c in SIM_ALL)
        lines.append(f"| {r.label} | {r.runtime:.0%} | {cells} |")
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
    for r in results:
        lines.append(
            f"| {r.label} | {r.runtime:.0%} | {fmt(r.diffs['sat'])} | "
            f"{fmt(r.diffs['zone_temp'])} | {fmt(r.comp_stage_diff, 3)} |"
        )
    return lines


def experimental_table(results: list[ExpResult]) -> list[str]:
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
    for r in results:
        inten = "" if r.intensity is None else f"{r.intensity:g}"
        oaf_txt = "n/a" if np.isnan(r.oaf) else f"{r.oaf:.2f}"
        lines.append(
            f"| {r.fault} | {inten} | {r.season} | {r.damper_cmd:.2f} | {oaf_txt} | {r.n} | {r.sat:.1f} |"
        )
    return lines


# ---------------------------------------------------------------- charts
# Light chart palette (dataviz reference instance). Blue/red pair validated: CVD dE 21.6.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
RED = "#e34948"
NEUTRAL = "#f0efec"
DEEMPH = "#c3c2b7"


def _style(plt: object) -> None:
    plt.rcParams.update(  # type: ignore[attr-defined]
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.facecolor": SURFACE,
            "figure.facecolor": SURFACE,
            "axes.edgecolor": BASELINE,
            "axes.labelcolor": INK_2,
            "xtick.color": MUTED,
            "ytick.color": INK_2,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": False,
        }
    )


def _titles(fig: object, title: str, subtitle: str) -> None:
    # Position in inches from the top, so short and tall figures get the same spacing.
    height = fig.get_figheight()  # type: ignore[attr-defined]
    fig.text(
        0.02,
        1 - 0.18 / height,
        title,
        ha="left",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=INK,
    )  # type: ignore[attr-defined]
    fig.text(
        0.02,
        1 - 0.46 / height,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.5,
        color=INK_2,
    )  # type: ignore[attr-defined]


def _intensity(r: SimResult) -> str:
    return f"{r.intensity:g} bar" if r.unit == "bar" else f"{r.intensity:g}%"


def chart_sat_by_fault(results: list[SimResult], out: Path) -> None:
    import matplotlib.pyplot as plt

    _style(plt)
    rows = sorted(
        (r for r in results if r.fault != "fault_free"),
        key=lambda r: (FAULT_ORDER.index(r.fault), r.intensity or 0),
    )
    labels = [f"{FAULT_NAMES[r.fault]}  {_intensity(r)}" for r in rows]
    values = [r.diffs["sat"] for r in rows]
    y = np.arange(len(rows))[::-1]

    fig, ax = plt.subplots(figsize=(9, 8.6))
    fig.subplots_adjust(left=0.30, right=0.95, top=0.86, bottom=0.08)
    ax.axvspan(-SENSOR_TOLERANCE_C, SENSOR_TOLERANCE_C, color=NEUTRAL, zorder=0)
    ax.text(
        0,
        len(rows) - 0.2,
        f"±{SENSOR_TOLERANCE_C} °C sensor tolerance",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color=MUTED,
    )
    ax.barh(
        y, values, height=0.5, color=[BLUE if v < 0 else RED for v in values], zorder=2
    )
    ax.axvline(0, color=BASELINE, linewidth=1, zorder=1)
    for xi in range(-8, 9, 2):
        if xi:
            ax.axvline(xi, color=GRID, linewidth=0.8, zorder=0)
    for yi, v in zip(y, values, strict=True):
        if abs(v) >= SENSOR_TOLERANCE_C:  # label only what a BAS could see
            ax.text(
                v + (0.15 if v > 0 else -0.15),
                yi,
                f"{v:+.1f}",
                va="center",
                ha="left" if v > 0 else "right",
                fontsize=8.5,
                color=INK,
            )
    # separate fault families with a little air
    for i in range(1, len(rows)):
        if rows[i].fault != rows[i - 1].fault:
            ax.axhline(y[i] + 0.5, color=GRID, linewidth=0.8)
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(-8.5, 8.5)
    ax.set_ylim(-0.7, len(rows) - 0.2 + 0.8)
    ax.set_xlabel(
        "Supply air temperature change vs baseline (°C): colder to the left, warmer to the right"
    )
    _titles(
        fig,
        "Only some refrigerant faults change supply air temperature",
        "Simulated set · median change vs the fault-free run at the same minute, compressor running",
    )
    fig.savefig(out, dpi=150)
    plt.close(fig)


def chart_condenser_fouling(results: list[SimResult], out: Path) -> None:
    import matplotlib.pyplot as plt

    _style(plt)
    rows = sorted(
        (r for r in results if r.fault == "condenser_fouling"),
        key=lambda r: r.intensity or 0,
    )
    x = [r.intensity or 0 for r in rows]
    fig, (left, right) = plt.subplots(1, 2, figsize=(9, 4.4))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.15, wspace=0.32)
    panels = [
        (
            left,
            [r.diffs["sat"] for r in rows],
            "Supply air temperature change (°C)",
            (-1, 4),
            "°C",
            1,
        ),
        (
            right,
            [r.diffs["refg_disc_pres"] for r in rows],
            "Discharge pressure change (kPa)",
            (0, 400),
            "kPa",
            100,
        ),
    ]
    for ax, vals, ylabel, ylim, unit, step in panels:
        if unit == "°C":
            ax.axhspan(-SENSOR_TOLERANCE_C, SENSOR_TOLERANCE_C, color=NEUTRAL, zorder=0)
            ax.text(
                10,
                SENSOR_TOLERANCE_C + 0.08,
                "sensor tolerance",
                fontsize=8.5,
                color=MUTED,
                va="bottom",
            )
        ticks = np.arange(ylim[0], ylim[1] + step, step)
        for t in ticks:
            ax.axhline(t, color=GRID, linewidth=0.8, zorder=0)
        ax.axhline(0, color=BASELINE, linewidth=1, zorder=1)
        ax.plot(x, vals, color=BLUE, linewidth=2, solid_capstyle="round", zorder=2)
        ax.scatter(
            x, vals, s=50, color=BLUE, edgecolors=SURFACE, linewidths=2, zorder=3
        )
        ax.annotate(
            f"{vals[-1]:+.{1 if unit == '°C' else 0}f} {unit}",
            (x[-1], vals[-1]),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=9,
            color=INK,
        )
        ax.set_ylim(*ylim)
        ax.set_yticks(ticks)
        ax.set_xticks(x, [f"{v:g}%" for v in x])
        ax.set_xlabel("Condenser airflow reduction")
        ax.set_title(ylabel, loc="left", fontsize=10, color=INK_2, pad=8)
        ax.tick_params(length=0)
    _titles(
        fig,
        "Condenser fouling: invisible in supply air, obvious in discharge pressure",
        "Simulated set · median change vs the fault-free run at the same minute · basic BAS points (left), refrigerant point (right)",
    )
    fig.savefig(out, dpi=150)
    plt.close(fig)


def chart_damper_oaf(results: list[ExpResult], out: Path) -> None:
    import matplotlib.pyplot as plt

    _style(plt)
    cases = [
        ("fault_free", None, "Fault-free"),
        ("oa_damper_stuck", 5.0, "Stuck at 5%"),
        ("oa_damper_stuck", 10.0, "Stuck at 10%"),
        ("oa_damper_stuck", 50.0, "Stuck at 50%"),
        ("oa_damper_stuck", 100.0, "Stuck at 100%"),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    fig.subplots_adjust(left=0.17, right=0.97, top=0.78, bottom=0.2)
    free = [
        r.oaf
        for r in results
        if r.fault == "fault_free" and not r.season.startswith("Summer")
    ]
    ax.axvspan(min(free), max(free), color=NEUTRAL, zorder=0)
    ax.text(
        (min(free) + max(free)) / 2,
        len(cases) - 0.45,
        "fault-free range",
        ha="center",
        fontsize=8.5,
        color=MUTED,
    )
    for t in np.arange(-0.2, 1.01, 0.2):
        ax.axvline(t, color=GRID, linewidth=0.8, zorder=0)
    for i, (fault, inten, _name) in enumerate(cases):
        yi = len(cases) - 1 - i
        rs = [
            r
            for r in results
            if r.fault == fault and r.intensity == inten and not np.isnan(r.oaf)
        ]
        for r in rs:
            summer = r.season.startswith("Summer")
            ax.scatter(
                r.oaf,
                yi,
                s=64,
                color=DEEMPH if summer else BLUE,
                edgecolors=SURFACE,
                linewidths=2,
                zorder=3,
            )
        cmd = rs[0].damper_cmd if rs else None
        if cmd is not None:
            ax.plot(
                [cmd, cmd], [yi - 0.25, yi + 0.25], color=INK, linewidth=2, zorder=2
            )
    ax.set_yticks(range(len(cases)), [c[2] for c in cases][::-1])
    ax.set_xlim(-0.25, 1.05)
    ax.set_ylim(-0.6, len(cases) - 0.2)
    ax.tick_params(length=0)
    ax.set_xlabel(
        "Outdoor-air fraction from temperatures, (MAT − RAT) / (OAT − RAT), occupied hours"
    )
    handles = [
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=8,
            color=BLUE,
            markeredgecolor=SURFACE,
            label="Fall, winter, spring day",
        ),
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=8,
            color=DEEMPH,
            markeredgecolor=SURFACE,
            label="Summer day (OAT close to RAT, unreliable)",
        ),
        plt.Line2D([], [], color=INK, linewidth=2, label="Damper command"),
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.45, -0.17),
        ncol=3,
        frameon=False,
        fontsize=8.5,
        labelcolor=INK_2,
    )
    _titles(
        fig,
        "A damper stuck at 50% or 100% stands out; stuck near minimum is hard to tell from normal",
        "Experimental (ORNL) set · median outdoor-air fraction per test day, from minutes where |OAT − RAT| ≥ 5 K",
    )
    fig.savefig(out, dpi=150)
    plt.close(fig)


CHARTS = [
    ("sat-change-by-fault.png", "Supply air temperature change by simulated fault"),
    (
        "condenser-fouling-two-views.png",
        "Condenser fouling seen through supply air and discharge pressure",
    ),
    ("oa-damper-stuck-oaf.png", "Outdoor-air fraction for stuck OA damper cases"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--plots", type=Path, help="folder for PNG charts (needs the eda group)"
    )
    args = parser.parse_args(argv)

    sim = analyse_simulated(args.root)
    exp = analyse_experimental(args.root)
    chart_lines: list[str] = []
    if args.plots:
        args.plots.mkdir(parents=True, exist_ok=True)
        chart_sat_by_fault(sim, args.plots / CHARTS[0][0])
        chart_condenser_fouling(sim, args.plots / CHARTS[1][0])
        chart_damper_oaf(exp, args.plots / CHARTS[2][0])
        rel = Path(args.plots.name)
        chart_lines = [
            "## Charts",
            "",
            "The tables below are the exact numbers behind each chart.",
            "",
        ]
        for file, alt in CHARTS:
            chart_lines += [f"![{alt}]({rel / file})", ""]

    lines = [
        "# EDA report: LBNL RTU data sets",
        "",
        f"> Generated by `scripts/eda_report.py` on {date.today().isoformat()}. Aggregates only, no raw data.",
        "> Interpretation is in the [dataset card](dataset-card.md#eda-findings).",
        "",
        *chart_lines,
        *simulated_tables(sim),
        "",
        *experimental_table(exp),
        "",
    ]
    args.out.write_text("\n".join(lines))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
