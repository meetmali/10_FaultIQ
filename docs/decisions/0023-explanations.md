# 0023. Evidence-grounded explanations and the diagnostic result contract

- **Status:** Accepted
- **Date:** 2026-11-19
- **Numbers:** [explanation report](../explanation-report.md), [results.json](../explanations/results.json),
  [examples](../explanations/examples/), [contract](../contracts/diagnostic-result.schema.json)
  (result schema 1.0.0 on pipeline 0.2.0, diagnosis 0.1.0)

## Context

Phases 3 and 4 decide *whether* a unit is abnormal and *which* supported fault it shows. Phase 5
must say *why*, without inventing anything. The exit rule: every statement traces to a measurement,
a dataset label, a model output or a cited reference, and inconclusive cases are handled
explicitly. The owner chose:
- template sentences, not an LLM,
- recommended checks from a cited fault library,
- the top 3 signals as evidence,
- fault events (runs of hours), not single hours.

## Decision

**A bounded workflow, not an agent.** Six fixed steps:
1. validate input (only Phase 2 output is accepted),
2. operating context,
3. detect (Phase 3 normal model, frozen threshold),
4. diagnose (Phase 4 classifier, frozen cut-off),
5. evidence,
6. explain, then check.

The workflow never receives the label. Labels are joined only afterwards, to score it.

**Fault events.** Consecutive alarmed hours with the same answer form one event. One quiet hour
inside is allowed, so a compressor cycling off doesn't split a fault in two. Each event has one of
four kinds:

| Kind | Meaning | Checks recommended |
|---|---|---|
| `fault` | A supported fault, named above the confidence cut-off | Yes, from the library |
| `inconclusive` | Abnormal, closest match below the cut-off | No, and the explanation says why |
| `no_supported_fault` | Abnormal, but the best match is normal operation | No |
| `not_diagnosable` | Alarmed while the relevant equipment wasn't running steadily | No |

**Evidence: top 3 signals.**
- For `fault` and `inconclusive` events: the features that pushed the diagnoser hardest toward its
  answer, summed over the event. These are LightGBM TreeSHAP values or logistic coefficient times
  value, in log-odds, so they add up across hours. A feature counts only if it was actually measured
  in the event: an imputed value is not evidence.
- For other events: the normal-model targets the detector found furthest from normal.
- Every item states:
  - its observed value,
  - its expected value, but only for residuals inside the normal model's weather range, where a
    baseline is defensible,
  - its normal range on **fault-free validation hours** (5th to 95th percentile, at least 10 hours).
    These hours were scored by the same models used at inference and never seen in training.

  It then says in words whether the value is inside or outside that range, comparing the numbers as
  displayed. A named fault that rests on in-range evidence therefore reads as weak.

**Template statements in five kinds:**
- finding,
- measured,
- context,
- uncertainty,
- recommended.

Each cites what it rests on (`refs`): `event`, `model`, `detector`, `context`, an evidence id, or a
source id. A model is never shown as certain: 99.5% and above reads "over 99%". Each named fault
states its validation precision ("hours named condenser fouling were right 96% of the time").

**The claim checker** runs on every result, and a result that fails is never emitted. It rejects a
statement that:
- cites a reference that doesn't exist,
- contains a number that isn't the displayed form of a value it cites,
- names a fault other than the event's fault or the closest match,
- uses certain wording ("definitely", "caused by", "proves" and similar),
- recommends a check that isn't word for word in the library, or recommends one without a named
  fault.

It also rejects an event that has no finding or uncertainty statement. A named fault must also have
measured evidence and checks.

**The fault library** (`pipeline/faultiq/explain/fault_library.toml`) is data, not code: a title and
2–3 checks per supported fault, each citing a source. The sources are:
- ASHRAE/ACCA Standard 180,
- ASHRAE Guideline 36,
- the Title 24 economizer FDD requirements,
- the LBNL dataset documentation.

Citations are to whole documents, not clauses. The library is marked `review_status = "unreviewed"`,
and every result carries that status so the UI can show it next to a check.

**The contract.** `DiagnosticResult` (Pydantic) is the record the worker writes and the .NET API
stores and serves (Phase 6). Its JSON Schema is committed at
`docs/contracts/diagnostic-result.schema.json`. A test fails if the code and the file disagree, so a
contract change is always deliberate.

## Results (all held-out files)

| Dataset | Points | Results rejected by the checker | Named events: right fault (by count / by hours / events of 3 h or more) | False-alarm events naming a fault |
|---|---|---|---|---|
| Simulated | all | **0 of 25** | 80% / **97%** / 96% | 28 |
| Simulated | basic | 0 of 25 | 61% / 83% / 73% | 0 |
| ORNL | all | **0 of 52** | 70% / 87% / 90% | 3 |
| ORNL | basic | 0 of 52 | 75% / 78% / 75% | 1 |

What this means:

1. **The exit criterion is met.** Across 154 workflow runs (both datasets, both point sets), the
   checker rejected nothing: every statement cites existing evidence, every number traces to it, and
   every check comes from the cited library. The tests show the checker does reject each kind of
   unsupported claim when one is planted.
2. **Short events are the weak spot.** By hours, named events are right 97% of the time (simulated,
   all points); by count, only 80%. One- and two-hour events carry most of the errors, which matches
   Phase 3's idea of requiring several consecutive abnormal hours. It wasn't adopted here, because
   choosing a minimum length after seeing these numbers would be tuning on test data. It is the first
   candidate for a future, pre-registered change.
3. **Evidence is mostly strong, and weak evidence is visible.**
   - On simulated data, 90% of named faults rest on a first signal outside its fault-free range.
     Example: "discharge pressure 1,847 kPa against 1,773 kPa expected, +5.0 typical errors; normal
     −0.6 to +0.7".
   - The drifted normal unit that Phase 4 calls undercharge now shows its evidence as **within** the
     fault-free range. A technician reading it has a concrete reason to doubt it.
4. **ORNL evidence has less context.** Only 80% of evidence items have a normal range, because each
   validation season has one fault-free file and some rules apply only in some weather. Where there
   is no range, the statement says nothing about it rather than guess.
5. **With basic points, more events end inconclusive** (533 of 1,201 simulated events), and no false
   alarm names a fault. The system says "I can't tell" instead of guessing, as designed.

## Consequences

- Phase 6 stores `DiagnosticResult` as the contract between the Python worker and the .NET API,
  probably as a JSON column plus indexed summary fields. The C# types are generated from, or tested
  against, the committed JSON Schema.
- Phase 7 renders statements grouped by kind, with references as links to the evidence chart. The
  library review status is shown next to every recommended check.
- An LLM may later rephrase statements. It would receive only the validated record, and its output
  would have to pass the same claim checker. Until then, templates cost nothing, work offline and
  can't invent.
- **Before a public release,** an HVAC professional must review the fault library against the cited
  documents and change `review_status`.
- Revisit when:
  - a minimum event length is pre-registered and evaluated on fresh data,
  - more fault-free reference hours exist (ORNL normal ranges),
  - the library is reviewed.
