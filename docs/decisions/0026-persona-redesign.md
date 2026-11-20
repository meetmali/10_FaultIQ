# 0026. Persona-based redesign: Operator and Technician views

- **Status:** Accepted
- **Date:** 2026-11-19
- **Plan:** [docs/plans/persona-redesign.md](../plans/persona-redesign.md) (approved by the owner before building)
- **Builds on:** ADR 0008, 0009, 0023, 0025

## Context

Phase 7 delivered three working screens for one generic user. The owner asked for a redesign
around two personas, a Building Operator / Facility Manager and a Field Engineer / Technician,
switchable at any time. It also had to include:
- light and dark themes,
- animated equipment illustrations,
- an equipment-type switcher that announces future types.

The governing rule: **FaultIQ is a fault detection and diagnostics product.** Every visual must help
answer one of four questions:
- is anything wrong,
- what is it and how sure are we,
- what next,
- did it get better.

Phase 8 (hardening) was deliberately deferred. Its backlog is recorded in the plan and in the
Field Guide.

## Decision

**One route table, two lenses.** Home, Units, the unit page and the Fault Library are shared routes.
The persona, Operator by default and remembered in the browser, chooses which components render.
Switching persona keeps the URL, so both views show the same unit and event. The persona is a
preference, not a permission: login and roles arrive in Phase 8.

**Shell:**
- an equipment-type menu, served by `GET /equipment-types`: rooftop units available; AHU, VAV box,
  chiller and cooling tower, and boiler and heat pump "coming soon", opening a dialog rather than an
  empty page,
- a site picker,
- the persona toggle and the System/Light/Dark toggle, both real radio groups.

**Design tokens.** CSS variables with light and dark sets, mapped to Tailwind utilities (`bg-surface`,
`text-ink`, `border-line`, status tones). `dark:` is driven by `data-theme`. ECharts gets matching
light and dark themes. Inline links are underlined, so they never rely on colour.

**Illustrations** (original inline SVG, CSS animation only, all motion off under
`prefers-reduced-motion`):
- **Isometric rooftop unit (Operator):**
  - *Details:* outdoor-air hood and damper, access panels, the controller's status light,
    refrigerant lines, a wrap-around condenser coil, a top fan spinning in perspective, ducts and
    the supply-air sensor.
  - *States:* off, normal, fault, unclear, analysing.
  - *Highlighting:* the component named by the fault library's `component` field glows, with a
    callout naming it.
  - *Variants:* hero, card and thumbnail.
- **Cutaway schematic (Technician):**
  - *Drawing:* the air path (damper blades rotate to the command, the fan spins, airflow animates)
    and the refrigerant loop, drawn without crossings.
  - *Readings:* grouped sensor tags at the sensors' physical locations, coloured by **deviation
    from expected** rather than raw value.

**Chart series v2** (worker). One aligned **hourly table** per analysis, holding:
- each sensor's hourly median,
- each residual, physics feature and economizer rule share, with its fault-free band from
  validation,
- the workflow's per-hour decision (mode, diagnosable, alarm, answer, confidence).

It is built from the same hours table the workflow used (`analyse_file`), so timelines show exactly
what was decided. Size is about 1.2 MB per 100-day analysis (about a quarter of that after Caddy's
gzip). Older v1 series degrade gracefully, with a note to re-run.

**Fault library: Operator fields.** `plain_name`, `plain_summary`, `what_to_do` and `component`, cited
and unreviewed like the rest, exported and drift-tested. No cost or energy figures are invented;
impact is stated only where FaultIQ measured it.

**Operator screens:**
- **Home:**
  - a health ring,
  - headlines counted from data,
  - "waiting for a technician" and "confirmed" counts,
  - needs-attention cards with the animated unit and its faulty part,
  - a fleet strip,
  - an issue calendar per site, from `GET /fault-events/daily`, which splits each event's alarmed
    hours across days.
- **Unit:**
  - *Hero:* the animated unit and a plain summary (likelihood in words: Likely, Possible, Unclear).
  - *Next step:* "what to do", plus a "how often FaultIQ is right" meter.
  - *History:* an hour-by-hour health strip, other findings, and before and after.
  - *Hand-off:* "copy summary for my technician" and a one-click switch to the Technician view.
- **Library:** cards and entries in plain words, with reliability meters.

**Technician screens:**
- **Home:**
  - a work queue of unreviewed named faults, ranked by hours × confidence,
  - review outcomes,
  - the fault mix,
  - detection health per unit,
  - latest events.
- **Workbench:** everything from Phase 7, plus:
  - the schematic with an hour scrubber that jumps between events,
  - a fault signature check: each candidate fault's deciding signals, as measured on held-out
    data, checked against this event,
  - an expected-versus-measured explorer showing only the signals that left normal, ranked by
    share of hours,
  - an operating-context timeline (mode, diagnosable, alarm, diagnosis, economizer rules),
  - evidence weights and case history.
- **Library:** the detailed entry plus the schematic, highlighting the faulty part and its deciding
  sensors.

**Tests:**
- **Vitest (25 tests):**
  - persona default and persistence,
  - theme persistence,
  - the coming-soon dialog,
  - page states,
  - illustration text equivalents and stillness,
  - the deviation grading.
- **Playwright (6 journeys on recorded responses):** both personas, both themes, and an axe
  WCAG 2.1 AA scan on every visited screen.
- **Locally:** a real-stack journey.
- **Pipeline:** a series v2 contract test.
- **API:** tests for the equipment types and the daily split.

## Consequences

- Both personas reach a diagnosis and the fault reference without dead ends. An operator can hand a
  case to a technician by copying a summary or switching lenses on the same URL.
- **Bugs caught while building:**
  - **Daily split overcounted.** It walked event clock spans and counted quiet hours; it now uses
    alarmed hours.
  - **Two accessibility violations, found by axe:**
    - definition lists containing `<p>` elements,
    - inline links distinguished only by colour in dark mode.
- **Plan deviation:** the site filter is remembered in the browser rather than kept in the URL. It is
  shared by every screen, which matters more than shareable links at this stage.
- Revisit when:
  - login arrives (role sets the default persona),
  - a second equipment type is added (its illustration, library entries and models),
  - the library is reviewed, removing its "unreviewed" notices.
