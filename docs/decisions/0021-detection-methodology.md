# 0021. Detection methodology and Phase 3 results

- **Status:** Accepted
- **Date:** 2026-11-19
- **Numbers:** [detection report](../detection-report.md), [results.json](../detection/results.json)
  (detection 0.1.0 on pipeline 0.2.0)

## Context

Phase 3 must say whether an RTU behaves abnormally, with performance measured on held-out data,
not visual plausibility. The owner chose hourly windows, time-block and season splits, a
normal-behaviour model as the ML candidate, and scoring on observable windows only.

## Decision

**Unit and labels.** One window per file-hour. A faulty window is scored only when its fault could
physically show for at least 30 minutes: refrigerant faults need the compressor running, a stuck
damper needs the fan on and the building occupied, a wrong economizer setpoint needs outdoor air
between the right and the wrong setpoint. A normal window needs 30 steady minutes. Coverage is
reported per fault.

**Splits, with no leakage.**
- **Simulated:** train on days 0–59, validate on 61–80, test on 82–99. The blocks are shared by every file,
  with one-day gaps between them.
- **ORNL:** leave one season out. The next season tunes the threshold, and the other two train.
- Detectors learn from fault-free training data only.

**Detectors** (each reported with all points and with basic points only, per ADR 0018):

| Family | Dataset | What it does |
|---|---|---|
| Limit rules | Simulated | Each signal's normal 1st–99th percentile range per operating mode. Score = distance outside the range |
| Economizer rules | ORNL | Title 24-style rules from the documented 10 °C economizer setpoint: economizing when it shouldn't, not economizing when it should; plus SAT disagreeing with the VAV discharge (all points) |
| Normal model | Both | Quadratic ridge regression per target, trained on fault-free steady minutes. Score = observed − expected, in units of the typical fault-free error |

**Thresholds.** The only tuned parameter. It is set to the lowest value that keeps false alarms at or
below **5% of normal validation windows**, then frozen before the test windows are scored.

**Weather envelope.** Detectors abstain where outdoor air lies outside the 1st–99th percentile range
seen in fault-free training. Abstained windows count as no alarm (so as misses for faulty windows).

**Headline metrics.** Recall at the false-alarm budget and ROC-AUC, which don't depend on how common
faults are. Precision is reported, with the caveat that the simulated test set is about 96% faulty.

## Results (test windows)

| Dataset | Detector | ROC-AUC | Recall | False alarms |
|---|---|---|---|---|
| Simulated | Limit rules, basic | 0.70 | 51% | 11% |
| Simulated | Normal model, basic | 0.73 | 70% | 44% |
| Simulated | Limit rules, all | 0.78 | 59% | 7% |
| Simulated | Normal model, all | **0.83** | **77%** | 14% |
| ORNL | Economizer rules, basic | 0.64 | 22% | 0% |
| ORNL | Normal model, basic | 0.82 | 44% | 15% |
| ORNL | Economizer rules, all | 0.80 | 37% | 4% |
| ORNL | Normal model, all | **0.89** | **68%** | 15% |

What this means:

1. **With all points, the normal model detects most refrigerant faults** (86–87% recall on condenser
   fouling from 20%, all evaporator fouling, liquid-line restriction from 4 bar, undercharge 20%).
   The rules raise about half as many false alarms. Neither is clearly best: the trade-off between
   recall and nuisance alarms is the design question for Phases 4–5 (for example, rules first,
   or requiring several consecutive abnormal hours).
2. **With basic points, detection is weak.** The limit rules find half the faulty hours at 11% false
   alarms. The basic normal model's 70% recall comes with 44% false alarms, so it isn't usable as is.
   This confirms ADR 0018: what most BAS exports contain limits what FaultIQ can promise.
3. **Some faults are hard with any detector:** overcharge 15% (16% recall at best, matching Phase 1's
   finding that overcharge doesn't scale with severity), and undercharge 10% and liquid-line
   restriction 1 bar without the normal model.
4. **ORNL:**
   - A damper stuck at 50% or 100% is caught 74–97% of the time. Stuck at 5% or 10% is not caught at
     all, because it looks like a damper at its minimum position (as Phase 1 predicted).
   - Supply air sensor bias is caught 58–69% of the time by the VAV cross-check rule (positive bias),
     and up to 100% by the model on the few negative-bias hours.
   - The economizer setpoint offset had only 8 observable test hours, so it is **inconclusive**.
5. **False alarms on test exceed the 5% validation budget** (7–44%). Normal behaviour drifts through
   the season (training July–September, testing late October), so a threshold set on one period
   doesn't fully carry over. Production needs periodic re-baselining, which is now a known requirement.
6. **Abstention:** about 13% of simulated test hours had outdoor air outside the training range, so no
   detector scored them. That caps recall near 87% on even the easiest faults, and is reported rather
   than hidden.

## Methodology changes made during Phase 3 (disclosed)

The test results were looked at while fixing defects. Each fix was made on general grounds, and
none tuned a parameter to test numbers. The method was then frozen at detection 0.1.0.

1. **Threshold by maximum F1 → false-alarm budget.** With 24 faulty files to 1 fault-free file,
   "alarm on everything" scored F1 = 0.98 at a 100% false-alarm rate.
2. **Gradient-boosted trees → quadratic ridge.** On fault-free data, the trees' error grew 3–5 times
   from training to test weeks, because they memorised the training period. The smooth model grows
   1–3 times.
3. **Added the training envelope.** Most of the remaining false alarms were outdoor air colder than
   anything in training.
4. **Envelope restricted to weather only.** Including return air let the most severe fault
   (9-bar suction restriction, which warms the zone) hide behind the guard: 0% recall. With the
   envelope on weather only it is 87%.

## Consequences

- Phase 4 diagnosis starts from detected windows. The basic-points limitation will carry through.
- Phase 5 can use the normal model's expected values as "expected vs observed" evidence.
- The field set is still unused. A sim-to-real check needs detectors that transfer across units,
  which none of these do yet, since they learn unit-specific normal behaviour.
- `MAX_FALSE_ALARM_RATE`, the envelope and the 30-minute window rules are constants recorded in every
  results file.
