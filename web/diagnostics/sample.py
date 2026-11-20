"""Synthetic rooftop-unit trend data and the sample portfolio every account starts with."""

import numpy as np
import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

# Injected faults: (fault code, first day, last day). Ground truth for evaluation.
FAULTS = [("econ-stuck-open", 5, 6), ("low-refrigerant", 9, 10), ("mat-sensor", 13, 14), ("econ-stuck-closed", 17, 18)]

# The sample portfolio: (site, city, unit, tons, seed, injected faults).
PORTFOLIO = [
    ("Campus North", "Champaign, IL", "RTU-1", 10, 11, [("low-refrigerant", 9, 11)]),
    ("Campus North", "Champaign, IL", "RTU-2", 15, 12, [("econ-stuck-open", 5, 7)]),
    ("Campus North", "Champaign, IL", "RTU-3", 7, 13, []),
    ("Downtown Office", "Urbana, IL", "RTU-4", 12, 14, [("mat-sensor", 13, 15), ("econ-stuck-closed", 17, 18)]),
    ("Downtown Office", "Urbana, IL", "RTU-5", 20, 15, []),
    ("Downtown Office", "Urbana, IL", "RTU-6", 10, 0, FAULTS),
]

# A confirmed case with technician notes, so the assistant can show similar past cases.
CONFIRMED_NOTE = (
    "Found low refrigerant charge, about 20% short. Leak at the evaporator coil braze joint, "
    "repaired, recharged and verified superheat. Supply air back at setpoint."
)


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


def load_sample_portfolio(user):
    """Create the sample sites and units with analyses already run. Safe to call more than once."""
    from .models import FaultEvent, Site, Unit
    from .services import run_analysis

    if Site.objects.filter(owner=user, name="Campus North").exists():
        return
    with transaction.atomic():
        for site_name, city, unit_name, tons, seed, faults in PORTFOLIO:
            site, _ = Site.objects.get_or_create(owner=user, name=site_name, defaults={"city": city})
            unit = Unit.objects.create(site=site, name=unit_name, tonnage=tons, notes="Sample unit with synthetic trend data.")
            data = generate(seed=seed, faults=faults).to_csv(index=False).encode()
            run_analysis(unit, SimpleUploadedFile(f"{unit_name.lower()}-june.csv", data, "text/csv"))
        event = FaultEvent.objects.filter(
            analysis__unit__site__owner=user, analysis__unit__name="RTU-1", fault_type__code="low-refrigerant"
        ).first()
        if event:
            event.review_status, event.technician_notes = FaultEvent.Review.CONFIRMED, CONFIRMED_NOTE
            event.save()
