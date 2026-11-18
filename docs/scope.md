# MVP scope and screens

> **Status: Accepted** on 2026-11-18 (see [ADR 0002](decisions/0002-rtu-first-batch-first-mvp-scope.md)).

## Scope summary

- RTUs only. Historical CSV files only. Batch processing. Read-only, with no equipment control.
- Detection (is it abnormal?) is kept separate from diagnosis (which supported fault, or inconclusive).
- Every result shows its evidence, its uncertainty, and the source, model and pipeline versions.
- Free and self-hostable for small and nonprofit building owners (ADR 0014). Users map their own point names to standard sensor roles, and rule-based findings are shown first.
- Every screen shows the decision-support disclaimer.

## Screens

These wireframes are deliberately low-fidelity. Real visual design happens in Phase 7.

### 1. Dashboard

```text
┌ FaultIQ ───────────── [Site ▾] [Status ▾] [Time range ▾] ─────────────┐
│ Equipment  12 total │ ✓ Normal 8 │ ⚠ Abnormal 3 │ ? Insufficient data 1 │
├──────────────────────────────────────┬───────────────────────────────────┤
│ Equipment overview (table)           │ Fault distribution (bar)          │
│ Unit · Status (icon+label) · Last    │ by supported fault class          │
│ run · Open events                    │                                   │
├──────────────────────────────────────┴───────────────────────────────────┤
│ Recent fault events: time · unit · class / "inconclusive" · confidence │
└──────────────────────────────────────────────────────────────────────────┘
  click unit → Fault Diagnostics     click event → Fault Diagnostics (event)
```

### 2. Fault Diagnostics

```text
┌ RTU-03 · mode: economizer + mech. cooling · source file · versions ─────┐
│ Time-series chart (SAT, MAT, RAT, OAT, damper %, fan) with the detected │
│ interval shaded · labelled axes and units · sensor picker               │
├───────────────────────────────┬──────────────────────────────────────────┤
│ Result                        │ Evidence                                 │
│ Detection: Abnormal           │ Measured: MAT ≈ OAT while damper at min  │
│ Diagnosis: <class> | Incon-   │ Derived:  OA-fraction residual           │
│ clusive · calibrated conf.    │ Model:    class probabilities (top 3)    │
│ Alternatives considered       │ Checks:   linked Fault Library entries   │
├───────────────────────────────┴──────────────────────────────────────────┤
│ [Flag for review] [Record confirmed outcome]   History of related events │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3. Fault Library

```text
┌ [Search fault or symptom…] [Equipment ▾] [Severity ▾] ───────────────────┐
│ Supported faults (list)     │ Entry: definition · symptoms · possible     │
│                             │ causes · diagnostic checks · related faults │
│                             │ · references · ← related diagnostic cases   │
└───────────────────────────────────────────────────────────────────────────┘
```

## Cross-cutting UX rules

- Status is always shown with an icon and a text label, never colour alone.
- Measurements, derived features and model outputs are visually distinct.
- "Inconclusive" and "insufficient operating context" are real states, not errors.
- Demo or sample values are labelled as such.
