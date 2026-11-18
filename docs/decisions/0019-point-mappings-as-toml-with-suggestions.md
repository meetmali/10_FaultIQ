# 0019. Point mappings as TOML files, with suggestions

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

Every building automation system names its points differently (`SAT`, `DA-T`, `Supply Air Temp`,
`RTU_SA_TEMP`) and records them in different units. Phase 1 hard-coded the three LBNL datasets'
columns in Python. Real users will upload their own exports, so the mapping has to be data, not code.
Phase 1 also showed that documented units can be wrong, so a unit must always be stated explicitly
and checked.

## Decision

- **One TOML file per unit of equipment** maps each source column to a **role** (what it measures,
  from the data dictionary) and a **unit** (how it is recorded). TOML is read with Python's built-in
  `tomllib`, so there's no new dependency.
- **The LBNL datasets use the same mechanism.** Their mappings ship in
  `pipeline/faultiq/ingestion/mappings/`, generated from the Phase 1 mappings that were verified against
  the files. All 56 experimental columns are now mapped, including the VAV discharge temperatures.
- **Validation lists every problem at once:** an unknown role, an unknown unit, a unit of the wrong
  kind (for example `sat` in watts), a role mapped twice, or a column both mapped and excluded.
- **Suggestions, never guesses.** `python -m faultiq draft-mapping export.csv` suggests roles from
  common point-name patterns, but writes every unit as `TODO` unless the header states it (such as
  `(°F)`). A mapping that still contains `TODO` is refused, so a person must confirm the units before
  any data is processed.

## Consequences

- Adding a building is a configuration task, not a code change.
- The upload screen in Phase 7 can show the same suggestions and save the same TOML.
- Mappings are small, reviewable text files that can live in version control next to the results.
