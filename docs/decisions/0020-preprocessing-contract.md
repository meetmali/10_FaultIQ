# 0020. Preprocessing contract: no filling, steady state by delay, physics features only

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

Phase 2 turns validated files into model-ready data. Three choices shape every later phase: what to
do with missing data, how to ignore transients, and how much feature engineering to do before the
detection phase shows what is needed. The owner chose the simplest option for each.

## Decision

1. **Validation gate.** A file is **quarantined** (kept out of analysis, with a report saying why) when
   it has no rows, timestamps run backwards, a core sensor is unmapped (supply air, outdoor air, a
   return/mixed/zone temperature, a compressor signal) or a core sensor is missing on more than half
   of the rows. Every other imperfection is **accepted with a warning** that counts it.
2. **Regular grid, never filled.** Each file goes onto a regular grid at its own sampling interval (1
   minute for LBNL, 15 minutes for a typical BAS export). Missing steps become explicit rows with
   `observed = false` and null values. A gap longer than 60 minutes starts a new `segment` instead of
   inserting empty rows, so windowed features never reach across an outage. Duplicates keep the first
   reading.
3. **Operating mode and steady state.** Each minute gets equipment flags (fan, compressor, heating,
   economizer) and one mode: off, fan only, economizer, cooling, economizer + cooling, heating or
   unknown. A minute is **steady once its mode hasn't changed for 10 minutes**, like ASHRAE Guideline 36
   FDD delays. Off and unknown are never steady. Thresholds are constants recorded in every report.
4. **Physics features only.** Per-minute engineering quantities: outdoor-air fraction (from temperatures
   and from flows), coil temperature drops, zone temperature error, superheat, subcooling, condensing
   approach, compressor power per capacity, sensible heat ratio, and the VAV cross-check
   (supply air minus the coldest VAV discharge). Rolling windows and statistics wait for Phase 3.
5. **Traceable, deterministic output.** One Parquet file and one JSON report per input, plus a run
   manifest linking each input's SHA-256 to its output's SHA-256 and the pipeline version. Reprocessing
   the same input gives byte-identical output (tested, and verified on all 81 LBNL files).

## Consequences

- No value in the processed data was invented. Models and rules must handle nulls, which keeps
  their behaviour honest.
- Mode-based steady state ignores compressor stage changes within cooling. If Phase 3 shows staging
  transients matter, a stability check can be added as a new ADR.
- Winter data with cycling gas heat has few steady minutes (about 10% on some ORNL days), so
  winter economizer evidence will be thin.
- The field set's refrigerant pressures don't get superheat or subcooling features: whether they are
  gauge or absolute pressures is undocumented.
