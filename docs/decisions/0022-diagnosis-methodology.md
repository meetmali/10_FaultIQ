# 0022. Diagnosis methodology and Phase 4 results

- **Status:** Accepted
- **Date:** 2026-11-19
- **Numbers:** [diagnosis report](../diagnosis-report.md), [results.json](../diagnosis/results.json),
  [model card](../model-card.md) (diagnosis 0.1.0 on pipeline 0.2.0)

## Context

Phase 3 says *whether* an RTU behaves abnormally. Phase 4 must say *which* supported fault it is,
or admit it can't tell. The owner chose:
- **Two views:** every observable faulty hour, plus the hours Phase 3's detector flagged.
- **Classes:** fault type plus "no supported fault". Severity is reported but not predicted.
- **Honest abstention:** a named fault must be right at least 90% of the time on validation data;
  otherwise the answer is "inconclusive".

## Decision

**Unit and splits.** Same as ADR 0021: one window per file-hour.
- Simulated: train on days 0–59, validate on 61–80, test on 82–99.
- ORNL: leave one season out; the next season validates, the other two train.

Validation picks the model and the confidence cut-off. Test hours are scored once.

**Which hours are diagnosed.** An hour is *diagnosable* when the equipment the supported faults act
on ran steadily for at least 30 minutes: the compressor (simulated refrigerant faults) or the supply
fan (ORNL air-side faults). This rule uses no label, so it works the same on new data.
- **Training and the main view** keep a faulty hour only if its fault could also physically show
  (the Phase 3 observability rule). Otherwise its label would be noise.

**Classes.**
- Simulated: normal plus 6 refrigerant faults.
- ORNL: normal plus 3 air-side faults.
- The field set stays held out, as in ADR 0018.

**Features: behaviour, never conditions.**
- Medians over diagnosable minutes of physics differences and ratios: superheat, subcooling,
  condensing approach, RAT−SAT, MAT−SAT, outdoor-air fraction, SAT−VAV.
- Signed residuals from the Phase 3 normal-behaviour models, as observed minus expected in units of
  typical error. The sign is the diagnosis: low suction pressure and high suction pressure have the
  same detection score but are different faults.
- The share of minutes breaking each economizer rule (ORNL).
- Outdoor air, return air, occupancy and compressor stage are left out on purpose. Faulty hours are
  selected by condition: a setpoint-offset hour only counts when outdoor air sits between the two
  setpoints. A classifier given outdoor air could learn that band instead of the fault.

**Cross-fitting the normal class.** The normal model is fit on fault-free training hours. Used
directly, those hours have near-zero residuals, so the classifier would learn "normal" from data
cleaner than any new hour will be. Instead, each fault-free training hour is scored by a normal
model fit without it:
- simulated: the two halves of the training days score each other,
- ORNL: the two training seasons score each other.

This is the out-of-fold idea used in stacking.

**Candidates** (ADR 0011). A multinomial logistic regression (median imputation, scaling, balanced
class weights) and LightGBM (200 trees, 15 leaves, balanced, deterministic).
- LightGBM is adopted only if it beats the baseline's pooled validation macro-F1 by 0.01.
- Both are reported on test.

**The confidence cut-off.** The answer is the most likely class, shown only when its probability
reaches a cut-off. The cut-off is the lowest one at which named faults are right at least 90% of the
time on at least 10 validation hours. Below it the answer is "inconclusive". If no cut-off reaches
the target, the model never names a fault for that fold.
- No separate probability calibration step. The cut-off is tuned on the outcome that matters, and
  calibration error is reported so users know how far to trust a stated probability.

**Explanations** (ADR 0016). Each answer carries the feature that pushed hardest toward it: LightGBM
`pred_contrib`, or coefficient times scaled value for the logistic model. Phase 5 shows it with the
expected-versus-observed chart.

**Metrics.**
- Macro-F1 on the raw most-likely class, so rare classes count as much as common ones.
- Per-class precision and recall, and the confusion matrix.
- What a user would see once "inconclusive" is allowed:
  - share answered,
  - named-fault precision,
  - for faulty hours: right fault, wrong fault, "no fault" or inconclusive.
- Severity breakdown.
- End to end: what happened to each alarmed hour.

## Results (held-out test hours)

| Dataset | Points | Adopted | Macro-F1 (log. / LGBM) | Answered | Named faults right | Faulty hours: right fault |
|---|---|---|---|---|---|---|
| Simulated | basic | LightGBM | 0.43 / 0.51 | 51% | 84% | 44% |
| Simulated | all | LightGBM | 0.71 / **0.77** | 100% | **90%** | **92%** |
| ORNL | basic | logistic | 0.42 / 0.43 | 14% | 78% | 16% |
| ORNL | all | logistic | **0.55** / 0.42 | 45% | 83% | 45% |

End to end with all points, on hours the detector alarmed on:

| Dataset | Alarm type | Hours | Right fault | Named a fault (wrong for true alarms) | No supported fault | Inconclusive |
|---|---|---|---|---|---|---|
| Simulated | True alarms | 7,758 | **96%** | 3% | 1% | 0% |
| Simulated | False alarms | 61 | n/a | 98% | 2% | 0% |
| ORNL | True alarms | 180 | 54% | 8% | 13% | 24% |
| ORNL | False alarms | 19 | n/a | 26% | **63%** | 11% |

What this means:

1. **With all simulated points, diagnosis works.** On hours the detector flags, the right refrigerant
   fault is named 96% of the time. The deciding features are the physically expected ones:
   - discharge-pressure residual for condenser fouling,
   - suction-pressure residual for suction restriction,
   - RAT−SAT for evaporator fouling,
   - compressor-power residual for liquid-line restriction and undercharge.
2. **The simulated normal class fails** (0.2% recall). By late October, the fault-free unit's
   residuals have drifted to the signature of a mild undercharge, and 414 of 432 normal test hours
   are called undercharge. Cross-fitting cannot fix this: it is drift between seasons, not
   in-sample bias, and there is only one fault-free simulated unit. It is the same drift that pushed
   Phase 3's test false alarms above budget. Two consequences:
   - Diagnosis must run behind detection.
   - The normal model needs re-baselining.
3. **Named-fault precision holds near the 90% target where data is plentiful** (simulated all: 90%)
   **and falls short where it is scarce** (ORNL: 78–83%). ORNL folds have about 200 training hours,
   and each cut-off is tuned on one season of about 100, so it carries over imperfectly.
4. **ORNL, all points:**
   - SAT bias is the most reliable fault (77% recall, 100% precision before the cut-off), decided by
     the SAT-versus-VAV rule.
   - A damper stuck at 50% or 100% is often named, decided by the "economizing when it should not"
     rule. Stuck at 5% or 10% is always inconclusive, matching Phase 3: it looks like minimum
     position.
   - The economizer setpoint offset has 8 test hours, so its results are **inconclusive**, not
     evidence.
5. **Diagnosis can dismiss false alarms when it has the right points.** On ORNL with all points, 63%
   of false alarms were answered "no supported fault". On simulated data it could not, because of
   point 2.
6. **Basic points are not enough for diagnosis.** It answers 14–51% of hours, below the precision
   target. This confirms ADR 0018 for a second phase: the points a site exports bound what FaultIQ
   can promise.
7. **LightGBM won where data is plentiful (simulated) and lost where it is scarce (ORNL).** The
   adoption rule picked correctly both times on validation alone; test agrees for 3 of 4.

**Tried and disclosed.**
- The first run fit the normal model on fault-free training hours and reused it for those same
  hours. Every simulated normal test hour was then named a fault.
- Cross-fitting was adopted because it removes a known bias. Validation favoured it in 3 of 4
  settings:
  - simulated basic 0.55 → 0.58,
  - simulated all 0.83 → 0.84,
  - ORNL all 0.58 → 0.59,
  - ORNL basic fell 0.49 → 0.41.
- Test results of both variants were seen. Nothing else was tuned after that.

## Consequences

- Phase 5 can show a named fault with its deciding feature, and say "inconclusive" when it should.
  The API contract must carry all three answer kinds:
  - fault + confidence + evidence,
  - no supported fault,
  - inconclusive.
- **Required before production:** periodic re-baselining of the normal model on recent fault-free
  data. It now affects both detection (ADR 0021) and diagnosis.
- Models are unit-specific: trained per dataset, not transferable. A new site needs its own
  fault-free baseline. That is why the field set is still unused.
- The 90% target is met on validation by construction, not guaranteed on test. Calibration error
  (0.08–0.19) is shown so users don't read a probability as a promise.
- Revisit when:
  - there are more fault-free units or seasons, which would let us test re-baselining,
  - there are more setpoint-offset hours,
  - Phase 6 or later adds sequence-level evidence (several consecutive hours).
