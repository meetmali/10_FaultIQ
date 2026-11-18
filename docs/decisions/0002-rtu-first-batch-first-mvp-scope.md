# 0002. RTU-first, batch-first MVP scope

- **Status:** Accepted (approved by the project owner on 2026-11-18).
- **Date:** 2026-11-05

## Context

HVAC FDD can expand without limit: more equipment types, live BMS
integration, streaming, failure prediction. The project plan (`FaultIQ_README.md`)
puts a guardrail on this: FaultIQ does **detection and diagnosis of observed faults**, not forecasting.

## Decision

The MVP supports:

- **Equipment:** packaged rooftop units (RTUs) only.
- **Data:** historical CSV files, starting with the LBNL simulated RTU dataset.
- **Processing:** batch ingestion and analysis. No streaming and no live BMS connection.
- **Outputs:** whether an interval is abnormal, which *supported* fault class fits best
  or "inconclusive", the sensor evidence, and the uncertainty.
- **Control:** read-only. The system never sends commands to equipment.
- **Users:** a single demo role. Authentication is added before any hosted deployment.
- **Audience:** small and nonprofit building owners, schools, municipal facilities teams, students
  and researchers. FaultIQ is free, open source (MIT) and self-hostable (see
  [ADR 0014](0014-pro-bono-open-source-self-hostable.md)).
- **Input reality:** CSV trend exports from different control systems, mapped to standard sensor
  roles through a point-mapping step. Rule-based findings are shown first.
- **Screens:** Dashboard, Fault Diagnostics, and Fault Library (see `docs/scope.md`).

Out of scope: failure prediction, remaining-useful-life estimates, maintenance scheduling,
AHUs and chillers, live integrations, multiple tenants, and fine-grained roles.

## Consequences

The workflow stays small enough to validate properly. Anything beyond this list needs a new ADR
that explicitly widens the scope.
