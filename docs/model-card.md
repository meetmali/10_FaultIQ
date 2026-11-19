# Model card: FaultIQ known-fault diagnoser

> Diagnosis 0.1.0 on pipeline 0.2.0. Method and decisions: [ADR 0022](decisions/0022-diagnosis-methodology.md).
> Numbers: [diagnosis report](diagnosis-report.md). Detection, which runs first: [ADR 0021](decisions/0021-detection-methodology.md).

## What it does

Given one hour of data from a packaged rooftop unit (RTU), it answers one of three things:
- the supported fault it shows, with a confidence and the feature that decided it,
- **no supported fault**,
- **inconclusive**, when it isn't confident enough to meet its precision target.

It runs on hours where the relevant equipment ran steadily for 30 minutes or more. Other hours are
"not diagnosable".

| Item | Value |
|---|---|
| Model type | Multinomial logistic regression (baseline) or LightGBM, chosen per dataset on validation macro-F1 |
| Input | 3–13 hourly behaviour features (physics medians, signed normal-model residuals, economizer rule shares) |
| Output | Class probabilities, an answer (fault / no supported fault / inconclusive), the deciding feature |
| Confidence rule | Answer shown only above a cut-off at which named faults were right at least 90% of the time on validation |
| Code | `pipeline/faultiq/diagnosis/` |
| Licence | MIT (code). Data: LBNL dataset terms, attribution required, not redistributed |

## Intended use

- **For:** screening and triage by a building operator or HVAC technician, after Phase 3 detection
  raises an alarm. It suggests where to look first and shows the evidence.
- **Not for:**
  - automatic control actions,
  - warranty or billing decisions,
  - any decision without a technician confirming on site,
  - faults outside the supported list, which it will never name (an unknown fault may show up as a
    wrong fault or "inconclusive"),
  - units other than the one it was trained on.

## Supported faults

| Dataset | Faults |
|---|---|
| Simulated RTU (LBNL) | Condenser fouling, evaporator fouling, liquid-line restriction, suction-line restriction, refrigerant overcharge, refrigerant undercharge |
| ORNL experimental RTU (LBNL) | Outdoor-air damper stuck, economizer setpoint offset, supply-air temperature sensor bias |

## Training and evaluation data

The [LBNL RTU FDD dataset](https://faultdetection.lbl.gov/dataset/rtu/) is described in the
[dataset card](dataset-card.md).

- **Simulated:** 25 files over 100 days.
  - Training: 34,471 hours from days 0–59.
  - Validation: 11,645 hours from days 61–80.
  - Test: 10,465 hours from days 82–99 (main view).
  - The test set is about 96% faulty hours.
- **ORNL:** 52 files over 4 seasons.
  - Each season is tested once (392 main-view test hours in total).
  - It is validated on the next season and trained on the other two.
- **Field set:** 4 files, held out and unused. The models are unit-specific (see limitations).

No test hour is ever in training. The normal class is cross-fitted, so the classifier never learns
"normal" from hours the normal model was fit on.

## Results (held-out test hours)

| Dataset | Points | Macro-F1 | Answered | Named faults right | Faulty hours: right fault | Calibration error |
|---|---|---|---|---|---|---|
| Simulated | all | 0.77 | 100% | 90% | 92% | 0.08 |
| Simulated | basic | 0.51 | 51% | 84% | 44% | 0.19 |
| ORNL | all | 0.55 | 45% | 83% | 45% | 0.12 |
| ORNL | basic | 0.42 | 14% | 78% | 16% | 0.13 |

End to end with all simulated points, the right fault is named for **96% of true alarms**.

**Per class (simulated, all points, recall of the most likely class):**
- Evaporator fouling: 100%.
- Undercharge: 97%.
- Suction restriction: 95%.
- Condenser fouling: 94%.
- Liquid-line restriction: 80%.
- Overcharge: 83%.
- Normal: 0.2% (see limitations).

## Limitations and known failure modes

1. **Drift makes normal look faulty.** Simulated normal hours from late October are called a mild
   undercharge, because the normal model was trained on July–September. Always run diagnosis
   behind detection, and re-baseline the normal model on recent fault-free data.
2. **Below-target precision on small data.** On ORNL, named faults are right 78–83% of the time,
   below the 90% validation target. The cut-off is tuned on one season of about 100 hours.
3. **Invisible faults stay invisible.** A damper stuck at 5–10% looks like minimum position. Overcharge
   15% often looks normal. Low-severity faults are diagnosed less often (see the severity tables in
   the report).
4. **Economizer setpoint offset is unvalidated.** Only 8 test hours.
5. **Basic points are not enough.** With only the points a typical BAS exports, it answers 14–51% of
   hours.
6. **Unit-specific.** Each model needs a fault-free baseline from the same unit. It doesn't transfer
   between units, so the field set can't be evaluated yet.
7. **Single faults only.** Training data has one fault at a time. Simultaneous faults are untested.
8. **Simulated and lab data.** The best numbers come from simulation. Real buildings are noisier.

## Ethical and practical considerations

- A confident wrong diagnosis costs a technician a trip and erodes trust. That is why "inconclusive"
  exists, and why the precision target was fixed before looking at test data.
- FaultIQ is pro bono. It shouldn't be marketed with the simulated numbers alone. Report the ORNL
  and basic-point numbers next to them.
- No personal data is used. Building telemetry can reveal occupancy patterns, so self-hosters should
  treat uploads as private (ADR 0014).

## Reproduce

```bash
cd pipeline && uv run python -I ../scripts/diagnosis_report.py ../data/processed/v0.2.0 \
    --json ../docs/diagnosis/results.json --out ../docs/diagnosis-report.md
```

Deterministic: two runs give byte-identical `results.json`, apart from the generated date.
