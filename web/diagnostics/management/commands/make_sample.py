"""Generate synthetic rooftop-unit trend CSVs (no licensed data), with known injected faults."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

# Injected faults: (fault code, first day, last day). Ground truth for evaluation.
FAULTS = [("econ-stuck-open", 5, 6), ("low-refrigerant", 9, 10), ("mat-sensor", 13, 14), ("econ-stuck-closed", 17, 18)]


def generate(days=21, seed=0, faults=()):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-06-01", periods=days * 96, freq="15min")
    hour = t.hour + t.minute / 60
    day = (t - t[0]).days
    oat = 20 + 8 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.6, len(t)) + 3 * np.sin(day / 5)
    rat = 23 + rng.normal(0, 0.3, len(t))
    fan = ((hour >= 6) & (hour < 20)).astype(int)
    sat_sp = np.full(len(t), 13.0)
    damper = np.where((oat < rat - 2) & (oat < 18), 100.0, 20.0)
    active = {code: (day >= a) & (day <= b) & (fan == 1) for code, a, b in faults}
    if "econ-stuck-closed" in active:
        damper = np.where(active["econ-stuck-closed"], 20.0, damper)
    if "econ-stuck-open" in active:
        damper = np.where(active["econ-stuck-open"] & (oat > rat + 2), 90.0, damper)
    frac = damper / 100
    mat = frac * oat + (1 - frac) * rat + rng.normal(0, 0.3, len(t))
    cooling = np.clip((mat - sat_sp) * 8, 0, 100)
    sat = np.where(cooling > 0, sat_sp, mat) + rng.normal(0, 0.4, len(t))
    if "low-refrigerant" in active:
        hit = active["low-refrigerant"] & (cooling > 0)
        cooling = np.where(hit, 100.0, cooling)
        sat = np.where(hit, sat_sp + 5 + rng.normal(0, 0.5, len(t)), sat)
    if "mat-sensor" in active:
        mat = np.where(active["mat-sensor"], mat + 6, mat)
    off = fan == 0
    sat, cooling = np.where(off, rat, sat), np.where(off, 0, cooling)
    return pd.DataFrame({
        "timestamp": t.strftime("%Y-%m-%d %H:%M"), "oat": oat.round(2), "rat": rat.round(2), "mat": mat.round(2),
        "sat": sat.round(2), "sat_sp": sat_sp, "damper_pct": damper.round(1), "cooling_pct": cooling.round(1), "fan_on": fan,
    })


class Command(BaseCommand):
    help = "Write synthetic sample CSVs to web/sample_data/."

    def handle(self, *args, **opts):
        out = Path(settings.BASE_DIR) / "sample_data"
        out.mkdir(exist_ok=True)
        generate(faults=FAULTS).to_csv(out / "rtu_faulty.csv", index=False)
        generate(seed=1).to_csv(out / "rtu_healthy.csv", index=False)
        (out / "rtu_faulty_labels.json").write_text(json.dumps(
            [{"fault": c, "start": f"2026-06-{a + 1:02d}", "end": f"2026-06-{b + 1:02d}"} for c, a, b in FAULTS], indent=2))
        self.stdout.write(self.style.SUCCESS(f"Wrote samples to {out}"))
