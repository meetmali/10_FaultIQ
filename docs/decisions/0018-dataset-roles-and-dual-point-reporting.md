# 0018. Dataset roles and dual reporting (all points and basic points)

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

Phase 1 profiled the 81 LBNL RTU files ([dataset card](../dataset-card.md), [EDA report](../eda-report.md)).
The findings change the plan's assumption that the simulated set alone is enough to start:

- The simulated set has **no economizer**. Its six fault types are all refrigerant-side.
- Several simulated faults (condenser fouling, charge faults) are **invisible with basic BAS points**.
  They show only in refrigerant pressures and temperatures or in power, which typical building systems
  don't record.
- Economizer and sensor-bias faults, the most common real RTU faults, exist only in the experimental
  (ORNL) set, as one day per fault intensity per season.
- The field set is the only real-building data, with two fault cases.

## Decision

1. **Dataset roles**
   - **Simulated:** primary development set for the pipeline, and for detection and diagnosis of
     refrigerant-side faults.
   - **Experimental:** economizer and sensor faults, and the transparent rule baselines (outdoor-air
     fraction, damper and economizer checks), because it has mixed air temperature, damper and
     VAV discharge temperature points.
   - **Field:** held out as a sim-to-real check. Never used for training.
2. **Dual reporting.** Every detection and diagnosis result is reported for two feature sets:
   - **All points:** everything the dataset provides.
   - **Basic points:** only points a typical BAS records (supply, return, outdoor, mixed and zone
     temperature, zone setpoint, damper command, compressor stage, occupancy).
   The basic-points result is the one that predicts usefulness for FaultIQ's real users.
3. **Faults that aren't separable are reported as such.** Where the EDA shows no signature in the
   available points (for example condenser fouling with basic points), the expected outcome is
   "inconclusive", and it is documented rather than forced into a class.

## Consequences

- Phases 3 and 4 run on two datasets with different fault sets, so there are two diagnosis models or
  label spaces, not one. That's more evaluation work, but it reflects reality.
- The economizer story in FaultIQ's docs and Field Guide is tied to the experimental set, and the
  refrigerant story to the simulated set.
- Phase 2 must map the experimental VAV discharge temperatures, which a supply air temperature bias
  check depends on.
