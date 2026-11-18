# 0014. Pro bono, open source and self-hostable

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

FaultIQ is a pro bono project. It's built and given away free for public benefit, not sold. The people
most likely to benefit are those without a budget for commercial FDD software: small and
nonprofit building owners, schools, municipal facilities teams, students and researchers.
The project has close to no budget, and contributors are likely to be volunteers.

## Decision

- **Licence: MIT.** It's the most widely used and most permissive open-source licence, and it's the same
  licence as .NET and React. All adopted dependencies use MIT, Apache-2.0, BSD or the PostgreSQL licence,
  which are compatible. **No paid or restrictively licensed components** (for example commercial UI suites
  or "community edition" licences with revenue caps).
- **Delivery model:**
  1. **Self-hosted first.** `docker compose up` on the user's own machine or server. It costs the project nothing
     to run, and building data never leaves the user's premises.
  2. **A public demo with sample data only.** No real building uploads are accepted there.
  3. A free hosted service is a future option only (project plan, section 19). It would need its own ADR covering
     cost, data custody, security and abuse protection.
- **Every external service must be optional and free to self-host.** Nothing in the core workflow may
  require a paid account (cloud identity, paid monitoring, paid storage).
- **Open-source governance from Phase 0:** `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
  (Contributor Covenant) and `SECURITY.md` (private vulnerability reporting).
- **Liability and trust:** the app itself, not just the docs, states that FaultIQ provides decision support
  only and is not a substitute for a qualified HVAC technician. The MIT licence's "as is" warranty disclaimer applies.
- **Real-world input matters.** Users will upload CSV trend exports from many different control systems, so:
  - Phase 2 includes a **point-mapping step**. Users map their column names (for example "SAT", "DA-T" or
    "SupplyAirTemp") to standard sensor roles, informed by the Brick and Project Haystack naming conventions.
  - **Rule-based findings are shown first.** Rules such as ASHRAE Guideline 36 and APAR carry over between
    buildings. Machine-learning diagnoses are labelled as trained on simulated LBNL data until they've been
    validated on real data.

## Consequences

- Hosting costs fall to the people who self-host. The project itself pays only for the demo.
- Licensing has to be checked whenever a dependency is added. A CI licence check is planned for Phase 8.
- Point mapping adds work in Phase 2, but without it FaultIQ can't be used on real buildings.
