# Plan: persona-based frontend redesign ("Phase 7b")

> Status: **approved and implemented** (19 Nov 2026), see [ADR 0026](../decisions/0026-persona-redesign.md).
> Branch `phase-7b/persona-redesign` (from `phase-7/frontend`). Deviations from this plan: the site filter is
> remembered in the browser rather than the URL, and chart series v2 is about 1.2 MB per 100-day analysis.
> Phase 8 (hardening) is deferred until after this work. Its full backlog is in
> [Deferred: Phase 8](#deferred-phase-8-hardening) and in the Field Guide.

## 1. Goal

Redesign the whole frontend around **two personas**, switchable at any time, without losing what
makes FaultIQ trustworthy. **FaultIQ is a fault detection and diagnostics product**, not a building
management dashboard. Every screen, chart and illustration must help answer one of four questions:

1. **Is anything wrong?** (detection)
2. **What is it, and how sure are we?** (diagnosis and uncertainty)
3. **What should happen next?** (action: a check, a call, a review)
4. **Did it get better?** (follow-up)

Raw sensor data never appears just to fill space. When a reading is shown, it is shown against what
it *should* be, or as evidence for or against a fault.

### Owner decisions (19 Nov 2026)

| Topic | Decision |
|---|---|
| Personas | Building Operator / Facility Manager, and Field Engineer / Technician |
| Default | **Operator.** A header toggle switches persona, and the choice is remembered in the browser. When login arrives (Phase 8), the account's role sets the default |
| Illustrations | **Both styles:** an isometric animated rooftop unit for the Operator, and an animated cutaway schematic for the Technician (it doubles as the live sensor schematic) |
| Sensor history | **Store more signals** (chart series v2), each presented for its diagnostic meaning, not as a raw plot |
| Equipment switcher | Rooftop unit is live. **AHU, VAV box / terminal unit, chiller and cooling tower, and boiler and heat pump** appear as "available in a future release" |
| Themes | Light and dark, following the system setting by default, with a manual override |

## 2. Personas and their jobs

| | Building Operator / Facility Manager | Field Engineer / Technician |
|---|---|---|
| Goal | Keep the building comfortable and running, spend money where it matters | Find the root cause fast and fix it right the first time |
| Main question | "Which units need attention, how serious is it, and who do I call?" | "What does the data say is wrong, how confident is it, and what do I check on site?" |
| Language | Plain words, no jargon: "outdoor coil may be dirty" | Technical terms: discharge pressure, superheat, economizer high limit |
| Wants | Visuals, status at a glance, impact, next step | Evidence, signals against expected values, signatures, operating context, history |
| Avoids | Lists of numbers, model internals | Marketing summaries without evidence |
| Typical action | Open a unit, read the plain summary, share it or dispatch a technician | Inspect evidence, confirm or reject on site, record the outcome |

Both personas see **the same analyses and the same facts**. The persona changes emphasis and
vocabulary, never the truth. Uncertainty is never hidden in the Operator view: it is shown simply
("Likely", "Possible", "Unclear").

## 3. Global shell (both personas)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ FaultIQ   [Rooftop units ▾]   [Site: All ▾]          ( Operator | Technician )  ☀/☾  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Home · Units · Fault Library                                       demo banner if on │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Equipment-type switcher.** Rooftop units (RTU) is active. Air handling units, VAV boxes /
  terminal units, chillers and cooling towers, and boilers and heat pumps are listed with a
  "Coming soon" tag. Choosing one opens a small dialog: "*[Type]* diagnostics will be available in a
  future release. FaultIQ currently supports rooftop units." It never navigates to an empty page.
  The list is data-driven, so adding a type later means adding one entry and its models.
- **Site selector**, shared by every screen and kept in the URL.
- **Persona toggle.** A segmented control, persisted in `localStorage`, defaulting to Operator.
  Switching keeps you on the same unit or event, so the two views are two lenses on one case.
- **Theme toggle:** System, Light or Dark. Charts and illustrations follow it.
- **Navigation:** Home, Units (the equipment list) and Fault Library. The routes are shared; the
  persona chooses which components render.

## 4. Screens

### 4.1 Operator Home: "How are my buildings?"

| Block | Visual | Data |
|---|---|---|
| Portfolio health | A large ring: units by status (needs attention / watch / healthy / no data), with a plain sentence ("2 of 8 rooftop units need attention") | `/equipment/overview` |
| Needs attention now | Up to 4 **unit cards**, each with the **isometric animated RTU** in its current state (the faulty part glowing), the fault in plain words, a likelihood chip (Likely / Possible / Unclear) and "affected for 12 days" | overview + latest result |
| Fleet strip | A row of small RTU illustrations, one per unit, coloured by status. Click to open | overview |
| Issue calendar | A heatmap of the last N days of data: each cell is a day, shaded by how many unit-hours had a named fault. Answers "is it getting worse?" | new `/fault-events/daily` |
| What's going on | Up to 3 plain-language headlines generated from data, for example "Outdoor coil problems on 3 units this month". Template-based and checked, like Phase 5 | summary endpoint |
| Next steps | Counts of "waiting for a technician" (unreviewed named faults) and "confirmed and fixed" | review statuses |

No tables on Operator Home.

### 4.2 Operator Unit view: "What's wrong with this unit?"

- **Hero:** the isometric RTU, large and animated. Airflow and fans move when the unit runs, and the
  diagnosed component pulses with a callout label ("Outdoor coil").
- **Plain summary card:** "Your outdoor coil may be dirty. The unit has worked harder than normal for
  12 days." Plus likelihood and duration, and **"What to do"**: call a technician to inspect and
  clean the coil. Text comes from new cited library fields (see 6.3), never invented.
- **Health timeline:** a horizontal strip over the analysis period. Green is fine, red is a named
  fault, amber is unclear, grey is not running. One glance shows how long and how often.
- **Before / after:** once a technician confirms and a later analysis exists, a simple comparison
  ("Affected hours per day: 18 before, 0 after").
- **Share:** "Copy summary for my technician", which copies a short text with a link to the
  Technician view of the same event.
- **Hidden here:** evidence charts, residuals, model versions and confusion data. One link opens the
  same event in the Technician view.

### 4.3 Technician Home: "What should I work on?"

| Block | Visual | Data |
|---|---|---|
| Work queue | A ranked list of unreviewed named faults (ranked by hours × confidence), each with fault, unit, duration and confidence, and one-click open | `/fault-events?review_status=unreviewed&kind=fault` |
| Fault mix | Fault distribution (bar) and kind split: named, inconclusive, unrecognised, not diagnosable | summary |
| Detection health | Alarmed share of scored hours per unit, and failed analyses with their error codes | overview, analyses |
| Review outcomes | Confirmed / rejected / needs review counts. Confirmed outcomes are future training labels | review statuses |
| Recent analyses | Status, point set, model version and duration, with upload | analyses |

### 4.4 Technician Unit view: the diagnostic workbench

Everything in today's Fault Diagnostics screen stays (findings, alternatives, evidence charts,
context, uncertainty, cited checks, review). New, and each built around a diagnostic question:

1. **Live cutaway schematic with a time scrubber.** "What was every sensor doing at this moment?"
   - The schematic shows readings where the sensors physically are: OAT, RAT, MAT, SAT, damper
     command, compressor stage, suction and discharge pressure, superheat, subcooling, and fan and
     compressor power.
   - Each tag is coloured by **deviation from expected**, not by raw value: grey when there is no
     model, neutral inside the fault-free range, amber or red outside it.
   - The operating mode shows as a label and an animation (fans spin, compressor runs, damper open
     to the commanded angle).
   - Scrubbing jumps between events.
2. **Fault signature check.** "Does the data look like this fault?" For the diagnosed fault and its
   alternatives, it lists the signals that decide each fault (from the library's measured symptoms)
   and shows this event's measured deviation for each: ✓ consistent, ✗ against, or ? no data. It
   makes the classifier's reasoning visible and helps reject wrong diagnoses.
3. **Expected-versus-measured explorer.** "Which signals left normal, and when?" A stack of small
   residual strips (in typical errors), one per model target, with the fault-free band shaded and
   events marked. It replaces "plot everything" with "show only what deviated".
4. **Operating-context timeline.** "Why was this hour (not) diagnosable?" Mode bands (off, fan only,
   economizer, cooling, economizer + cooling, heating) and steady or diagnosable hours, aligned with
   events. It explains gaps and "not diagnosable" results.
5. **Economizer rule timeline** (units with an economizer). "When did the economizer misbehave?"
   Hours violating each rule, against outdoor air and the 10 °C enable setpoint.
6. **Evidence weights.** "What pushed the model?" A bar chart of the top feature contributions
   (already stored as `weight`), with plain names.
7. **Case history.** Other events of the same fault on this unit and their review outcomes.

### 4.5 Fault Library (both personas)

- **Operator:** cards with the small isometric RTU and the affected part highlighted, plus a
  plain-language summary, "what to do" and how reliably FaultIQ detects it (as a simple meter).
- **Technician:** today's detailed entry plus the cutaway schematic with the affected component and
  its symptom sensors highlighted.

## 5. Illustrations

### 5.1 Isometric rooftop unit (Operator)

- Original artwork, drawn as inline SVG: a packaged RTU on a roof curb, showing the outdoor-air hood
  and damper, the condenser section with its top fan, the compressor access panel, the supply and
  return ducts into the roof, and a VAV-style duct hint below.
- **States:**
  - *off / no data:* static and muted;
  - *running and normal:* fans spin slowly, with soft airflow particles at the intake and supply;
  - *fault:* the affected component glows red with a pulsing outline and a callout label;
  - *analysing:* a subtle scanning shimmer;
  - *unclear:* amber glow.
- **Thumbnail variant** for fleet strips and cards: the same drawing, fewer details, static.

### 5.2 Cutaway schematic (Technician)

A clean side-section in standard HVAC diagram style: outdoor-air damper → mixing box (return-air
damper) → filter → evaporator coil → supply fan → supply duct. Below it, the refrigerant loop:
compressor → condenser coil (with fan) → liquid line → expansion valve → evaporator → suction line.
Sensor tags sit at their physical locations, and airflow and refrigerant flow animate by mode.

### 5.3 Which part each fault highlights

| Fault | Highlighted component |
|---|---|
| Condenser fouling | Condenser coil and fan |
| Evaporator fouling | Evaporator coil and filter |
| Liquid-line restriction | Liquid line and filter drier |
| Suction-line restriction | Suction line |
| Refrigerant overcharge / undercharge | Refrigerant circuit (compressor and lines) |
| Outdoor-air damper stuck | Outdoor-air damper |
| Economizer setpoint offset | Economizer controller |
| Supply-air temperature sensor bias | Supply-air sensor |

### 5.4 Motion and accessibility

- All animation stops under `prefers-reduced-motion`.
- Each illustration has a text equivalent: "Rooftop unit RTU-1, running. Problem area: outdoor
  coil."
- The glow is paired with a text callout, so colour never carries the meaning alone.
- Animation is CSS only, with no animation library.

## 6. Data and backend changes

### 6.1 Chart series v2 (worker)

Stored per analysis, downsampled with LTTB, versioned (`version: 2`). The API passes it through as
before.

| Series | Content | Used by |
|---|---|---|
| `signals` | Up to about 14 sensor and physics signals that exist in the file: OAT, RAT, MAT, SAT, damper command, compressor stage, suction and discharge pressure and temperature, superheat, subcooling, condensing approach, fan and compressor power | Schematic scrubber |
| `residuals` | Per normal-model target: deviation in typical errors, plus its fault-free band from validation | Expected-vs-measured explorer, schematic tag colours |
| `hours` | One row per hour: operating mode (dominant), steady and diagnosable flags, alarm, answer, and economizer rule shares | Health timeline, context timeline, rule timeline |
| `events` | Unchanged from v1 | Evidence charts |

Size: about 1 MB per analysis in total, which is fine for JSONB. Existing analyses keep v1 series,
and the UI degrades gracefully (no schematic scrubber, with a note) until they are re-run.

### 6.2 New API endpoints

- `GET /fault-events/daily?site=&equipment_id=&from=&to=`: hours per day by kind and unit, for the
  Operator issue calendar.
- `GET /equipment-types`: the switcher list (`rtu` available; the others `coming_soon`), so the
  catalogue lives in one place.

### 6.3 Fault library: operator fields

New TOML fields per fault, cited and marked unreviewed like the rest:
- `plain_name`, for example "Dirty outdoor coil",
- `plain_summary`, for example "The unit has to work harder to get rid of heat",
- `what_to_do`, for example "Ask a technician to inspect and clean the outdoor coil",
- `component`, the illustration part to highlight.

Exported and drift-tested as today. No cost or energy numbers are invented: impact is stated only
where FaultIQ measured it (for example "compressor power was 75 to 693 W higher in tests").

### 6.4 Grounding stays

Any generated sentence (Operator headlines, plain summaries filled from an event) uses templates
filled only from stored fields, and a frontend unit test checks that every number in them comes from
the data. The Phase 5 claim checker remains the gate for the explanation itself.

## 7. Visual design

- **Design tokens** as CSS variables, with light and dark sets:
  - surface, raised surface, border, text and muted text,
  - an accent (blue),
  - status colours: fault (red), unclear (amber), unrecognised (violet), healthy (green), and
    no data / off (slate).
- Every status pairs its colour with an icon and words, as today.
- Dark mode uses the Tailwind v4 `dark:` variant driven by a `data-theme` attribute. It defaults to
  the system setting, with the override saved in `localStorage`.
- ECharts gets a light and a dark theme built from the same tokens.
- **Typography:** the system font stack and tabular numbers for readings. The Operator view uses
  larger type and more whitespace; the Technician view is denser.
- **Layout:** cards and visuals for the Operator, panels and a split layout (schematic beside the
  charts) for the Technician. Both work at phone width; the Technician workbench stacks.

## 8. Accessibility and quality bar

- WCAG 2.1 AA contrast in both themes, checked with axe in Playwright.
- Keyboard: every control is reachable, the toggles are real radio groups, and the time scrubber is
  a slider with arrow keys.
- Every chart and illustration has a text equivalent. Reduced motion is respected.
- No placeholder values: Playwright fails on "undefined", "NaN" or "[object Object]", as today.

## 9. Tests

- **Vitest:**
  - persona and theme persistence,
  - the equipment switcher's coming-soon dialog,
  - illustration state and component highlighting per fault,
  - the signature check logic,
  - Operator headline templates (every number traceable).
- **Playwright** (mocked API, both themes, both personas):
  - Operator: home → needs-attention card → unit → summary → open in Technician view.
  - Technician: work queue → workbench → schematic scrub → review → library → back.
  - Both: choosing a coming-soon equipment type shows the dialog.
  - axe accessibility checks on each screen in both themes.
- **Pipeline:** series v2 shape and size tests; the library export's new fields; drift tests.
- **API:** the daily endpoint and the equipment types list.

## 10. Delivery steps

1. Pipeline: series v2, plus the new library fields and their export. Re-run the sample analyses.
2. API: the daily and equipment-types endpoints, contract regeneration and tests.
3. Design system: tokens, light and dark, ECharts themes, persona and theme context, the new shell
   (equipment switcher, persona toggle, theme toggle).
4. Illustrations: isometric RTU (with thumbnail) and cutaway schematic, with fault highlighting and
   motion states.
5. Operator screens: Home, Unit and the Library view.
6. Technician screens: Home (work queue) and the workbench (scrubber schematic, signature check,
   residual explorer, context and rule timelines, evidence weights, history).
7. Tests (Vitest, Playwright with axe), ADR 0026, README, Field Guide.
8. Show you both personas in both themes before committing.

## 11. Out of scope for this redesign

- Real cost or energy estimates (no metered tariff or energy data yet).
- Equipment other than rooftop units. The switcher shows them as coming soon only.
- Login and roles. The persona is a preference, not a permission (Phase 8).
- Live or streaming data. Analyses stay batch uploads.

## Deferred: Phase 8 (hardening)

Kept for later at the owner's request; nothing here is dropped. Each item is also in the Field Guide.

| Area | Item | Origin |
|---|---|---|
| Identity | ASP.NET Core Identity (local accounts) plus optional OIDC; roles (operator, technician, admin) set the default persona | ADR 0015, 0024, 0025 |
| Identity | Record who reviewed each event; audit trail of review changes | ADR 0025 |
| Security | Antiforgery on form posts (uploads) once cookie auth exists; per-user rate limits | ADR 0024 |
| Security | Security review: uploads, path handling, pickle trust boundary, Problem Details leakage, CORS, headers | Plan §8 |
| Security | Dependency and licence checks in CI (NuGet, PyPI, npm) | Plan §8 |
| Reliability | Failure cases: database down mid-job, disk full, worker killed, corrupt CSVs, very large files | Plan §8 |
| Reliability | `LISTEN/NOTIFY` for faster job pickup; delete and retry analyses | ADR 0024 |
| Data | Site time zones declared in point mappings, with conversion | ADR 0025 |
| Data | Data lineage checks from raw file to result | Plan §8 |
| ML | Periodic re-baselining of the normal model; a pre-registered minimum event length evaluated on fresh data | ADR 0021–0023 |
| ML | Per-site baselines for non-LBNL units (detection-only first) | ADR 0024 |
| Content | HVAC professional review of the fault library; flip `review_status` | ADR 0023 |
| Ops | Run both Docker Compose stacks for real; tested backup and restore; OpenTelemetry collector profile | ADR 0012, 0017 |
| Ops | Merge the stacked phase branches into `main`; confirm CI (Playwright, database tests) on GitHub | Phases 0–7 |
| UX | Accessibility audit with assistive technology; browser matrix (Chrome, Firefox, Safari, Edge) | Plan §8 |
| UX | DuckDB-backed deep zoom beyond the stored series | ADR 0009, 0024 |
