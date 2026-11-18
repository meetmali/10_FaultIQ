# 0003. Modular monolith with a separate pipeline library

- **Status:** Superseded by [0007](0007-hybrid-dotnet-api-python-pipeline.md)
- **Date:** 2026-11-05

## Context

The same ingestion, feature and inference code has to run in three places: EDA notebooks,
batch scripts and the API. Microservices would add operational cost with no benefit
at MVP scale.

## Decision

- Use one backend deployable that contains two packages:
  - `faultiq/` is the pure-Python FDD library (ingestion → validation → preprocessing →
    features → detection → diagnosis → evaluation). It **must not import FastAPI or
    `app`**.
  - `app/` is the FastAPI layer: routing, schemas, database access and workers. It calls into `faultiq`.
- Long-running analysis goes to a background `worker` process from the same codebase,
  added once Phase 6 needs it.
- `faultiq.PIPELINE_VERSION` and the model version are recorded with every inference.

## Consequences

Notebooks and scripts import the same tested code that the API runs. The boundary between the two
packages has to be enforced, at first by review and later by an import-lint check.
The modules can be split into separate services later, if load ever justifies it.
