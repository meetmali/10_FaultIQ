"""Energy cost estimate for a fault event, and the work-order priority it suggests.

A deliberately simple, transparent model so a facility manager can check the arithmetic:

    wasted kWh = fault hours x unit tons x kW per ton x waste factor for that fault

The waste factor is the share of the unit's electrical input the fault wastes while it is active.
The values are engineering estimates, not measurements, and every page that shows a cost says so.
"""

from django.conf import settings

KW_PER_TON = 1.2  # typical full-load electrical input of a packaged rooftop unit
DEFAULT_TONS = 10  # used when a unit's tonnage is not recorded
HOURS_PER_MONTH = 14 * 30  # occupied running hours in a month (14 h a day)

WASTE_FACTOR = {
    "econ-stuck-closed": 0.35,  # compressor does work that free outdoor air could have done
    "low-refrigerant": 0.30,  # compressor at full power while delivering less cooling
    "econ-stuck-open": 0.25,  # hot outdoor air loads the coil
    "cooling-leak": 0.20,  # cooling valve passes while commanded off
    "mat-sensor": 0.15,  # controller acts on a wrong reading
    "fan-off-occupied": 0.0,  # no energy wasted, but the space gets no fresh air
}
UNCLASSIFIED_FACTOR = 0.10
COMFORT_FAULTS = {"fan-off-occupied"}


def price():
    return settings.ENERGY_PRICE_PER_KWH


def _code(event):
    return event.fault_type.code if event.fault_type_id else None


def _kw(event):
    tons = event.analysis.unit.tonnage or DEFAULT_TONS
    return tons * KW_PER_TON * WASTE_FACTOR.get(_code(event), UNCLASSIFIED_FACTOR)


def estimate(event):
    """kWh and cost so far, and the monthly cost if the fault is left unfixed."""
    kw = _kw(event)
    kwh = event.hours * kw
    monthly = kw * HOURS_PER_MONTH * price()
    return {"kwh": round(kwh), "cost": round(kwh * price(), 2), "monthly_cost": round(monthly), "comfort": _code(event) in COMFORT_FAULTS}


def suggest_priority(event):
    """Priority for a new work order: comfort faults are urgent, the rest follow the monthly cost."""
    if _code(event) in COMFORT_FAULTS:
        return "urgent"
    monthly = estimate(event)["monthly_cost"]
    level = "high" if monthly >= 300 else "medium" if monthly >= 100 else "low"
    if event.confidence < 0.5 and level != "low":  # weak evidence: one step lower until a technician confirms
        level = {"high": "medium", "medium": "low"}[level]
    return level


DUE_DAYS = {"urgent": 1, "high": 3, "medium": 7, "low": 14}
