# 0025. Frontend screens, fault library content and human review

- **Status:** Accepted
- **Date:** 2026-11-19
- **Builds on:** ADR 0008 (frontend stack), 0009 (charts), 0023 (explanations), 0024 (API)

## Context

Phase 7 turns the API into the three screens in the project plan (section 11): Dashboard, Fault
Diagnostics and Fault Library. The exit rule is that a user can move from the overview to a
specific diagnosis and then to the fault reference without broken navigation or unexplained
placeholder values.

Three gaps had to be closed first:
- The screens ask for "possible alternatives", but a result recorded only the top class.
- The Fault Library needs symptoms, causes and related faults, and the library had only titles
  and checks.
- The Diagnostics screen asks to "mark a case for human review or record a confirmed outcome".

The owner chose:
- data-backed, cited library content,
- reviews built now,
- Playwright with recorded API responses in CI, plus a local run against the real stack.

## Decision

**Result schema 1.1.0 (additive).** `ModelOutput.alternatives` lists the three most likely classes,
using each class's mean hourly probability over the event. The claim checker is unchanged: the
alternatives are structured data, not statements.

**Fault library: measured where possible, cited where not.**
- `fault_library.toml` adds, per fault:
  - the equipment it belongs to and the unit of its severity,
  - a definition, cited to the LBNL dataset documentation,
  - what FaultIQ measured, cited to the dataset card,
  - likely causes, cited at document level and still marked unreviewed.
- `python -m faultiq export-library` merges that with numbers taken from the Phase 4 held-out
  results, so these are measured, never asserted:
  - **symptoms:** the signals that most often decided the diagnosis,
  - **often confused with:** both directions of the confusion matrix,
  - **performance:** precision and recall overall, and by severity.
- The output is embedded in the API and served at `GET /fault-library` (search across names,
  symptoms and causes; equipment filter) and `GET /fault-library/{id}`. A pipeline test fails if
  the served file differs from what the exporter would produce.

**Human review.**
- Each fault event gets a review status (`unreviewed`, `needs_review`, `confirmed` or `rejected`),
  a note and a review time. The database default covers rows the worker inserts.
- `PATCH /fault-events/{id}/review` sets them, and demo mode blocks it like every write.
- Confirmed outcomes are future labelled data. Who reviewed is recorded once login exists (Phase 8).

**Dashboard endpoints.**
- `GET /equipment/overview` gives each unit's latest analysis and a derived status:
  `no_data`, `analysing`, `analysis_failed`, `fault`, `abnormal` or `normal`.
- `GET /fault-events/summary` gives the fault distribution.
- `GET /equipment/sites` feeds the site selector.

**Screens** (React Router, TanStack Query, ECharts, a small shadcn-style kit, Radix only for the
dialog):

| Screen | What it shows | Interactions |
|---|---|---|
| Dashboard | Totals, an equipment table with status, recent events, a fault-distribution chart with a table | Filter by site, status and event dates (kept in the URL); open a unit or an event; upload and analyse |
| Fault Diagnostics | Analysis history; an air-temperature overview with every event shaded and the selected one outlined, opening on that event ±3 days; an events table; for the selected event: finding, alternatives, each evidence signal with a measured-versus-expected chart, context, uncertainty, cited checks, review form | Pick an analysis or event (in the URL); open the fault in the library; record a review |
| Fault Library | Search and equipment filter; per fault: definition, what was measured, symptoms, causes, checks, often-confused-with, performance by severity, references | Search by name or symptom; follow related faults; return to the diagnosis that linked here |

**What the UX requirements became in code.**
- **Status never by colour alone.** Every badge has an icon and a text label.
- **Observed versus derived versus inferred.** Each statement is labelled "Measured",
  "Model inference", "Operating context", "How far to trust this" or "Suggested check". Library
  sections are labelled "Reference data", "Measured" or "Cited, unreviewed".
- **Suggestions aren't instructions.** Checks sit under a warning while the library is unreviewed.
- **Charts.** Units on the axes, a caption that says when data is downsampled, and a "Data summary"
  table (min, mean, max) so the information doesn't depend on seeing the canvas.
- **States.** Every query shows loading, an error with a retry, an empty state that says what to do,
  and freshness: "Updated 14:37", "Refreshing…", or "Couldn't refresh; showing data from 14:37".
- **Demo mode.** A banner on every screen, numbers marked "sample data", and the upload and review
  controls removed.
- **Keyboard and responsive.**
  - Navigation: a skip link, labelled landmarks, native controls and a focus-trapped dialog.
  - Layout: it collapses to one column at phone width, and wide tables scroll inside their cards.
- **Safe navigation.** The "back to the diagnosis" target comes from the URL, so only internal
  `/equipment/…` paths are honoured.
- **Honest numbers.** A probability never reads 100% ("over 99%") or 0% ("under 1%").

**Times are as recorded.**
- Source files carry no time zone, and point mappings don't declare one yet. Before this phase,
  naive times were shifted by each reader's local zone: the browser, PostgreSQL's session and the
  chart code all disagreed with the explanation text by 5 hours.
- The pipeline now keeps source times exactly as recorded and marks them UTC, so every reader sees
  the same numbers.
- The UI shows data times without a zone ("as recorded in the uploaded data") and system times, such
  as when an analysis ran, in UTC.

**Tests.**
- **Vitest (17 tests):** formatting, badges, the back-link rule, and page states (empty, error,
  demo).
- **Playwright in CI:** the full journey and the other states, against the built app. API answers
  come from committed files: the Phase 5 example result, the generated library and synthetic series,
  so no LBNL sensor values are committed.
- **Playwright locally:** `E2E_REAL=1` runs the same journey against the real stack, seeded with
  `scripts/seed_demo.py`.

## Consequences

- The exit criterion is met. The journey dashboard → diagnosis → library → back passes, with
  recorded responses and against the real stack. The journey test also fails on any `undefined`,
  `NaN` or `[object Object]` on screen.
- The real seeded data shows the system's known weaknesses openly rather than hiding them:
  - The fault-free unit shows undercharge events whose evidence reads "within the fault-free range"
    (Phase 4's drift).
  - A basic-points undercharge unit is named suction restriction. The review form is where a
    technician records that.
- The bundle loads ECharts lazily: the entry is 121 kB gzipped, and the 570 kB chart chunk is
  fetched only on screens with charts.
- Site time zones remain a known gap. Point mappings should declare one before multi-site use.
- Revisit when:
  - login arrives (who reviewed, antiforgery on writes),
  - the library is reviewed,
  - users need to compare units or analyses side by side.
