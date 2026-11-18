# 0007. Hybrid backend: .NET API with a Python data and ML pipeline

- **Status:** Accepted. Supersedes [0003](0003-modular-monolith-with-separate-pipeline-library.md).
- **Date:** 2026-11-05

## Context

The project owner wants C#/.NET for the backend. It's common in BAS and enterprise
environments and fits future integration work such as BMS and vendor APIs. But the heart of FaultIQ
is data exploration, leakage-aware evaluation, calibrated classification, and evidence extraction.
Python's ecosystem (pandas, scikit-learn, Jupyter) is clearly stronger there than ML.NET.

We considered three options:

1. All Python. This was the original plan.
2. All .NET, with ML.NET. Rejected: weak tooling for data exploration, splits by group,
   calibration and explanations.
3. **Hybrid. Chosen:** .NET for the application tier, Python for everything that touches data or models.

## Decision

### Responsibilities

| `api/`: ASP.NET Core (.NET 10 LTS, C#) | `pipeline/`: Python 3.13 |
|---|---|
| REST API under `/api/v1` | `faultiq` library: ingestion, validation, preprocessing, features, detection, diagnosis, evaluation |
| Upload handling: safe IDs, size and type checks, content hash | `worker`: claims analysis jobs and runs the pipeline |
| Database schema and migrations (EF Core, from Phase 6) | Model training, evaluation and calibration (scripts and notebooks) |
| Job creation and status, pagination, filtering | Evidence extraction and explanation generation, including any LLM phrasing |
| Authentication and authorization (when added) | Records `pipeline_version` and `model_version` on every result |
| Future BMS and vendor integrations | |

### Integration contract

- **There are no direct calls between the API and the worker.** PostgreSQL is the integration point.
  - The API inserts a job row with status `queued`.
  - The worker claims it with `SELECT … FOR UPDATE SKIP LOCKED`, sets it to `running`, and writes
    results, evidence and versions, then sets it to `succeeded` or `failed` with a safe error message.
  - `LISTEN/NOTIFY` can be added later to reduce pickup delay. The worker still keeps polling as a fallback.
- **Files:** the API and worker share a volume for uploads and processed data. They refer to files by
  server-generated IDs, never by filenames supplied by users.
- **Schema ownership:** EF Core migrations in `api/` are the only source of truth for the schema.
  The worker uses SQLAlchemy Core with explicit table definitions. In Phase 6, a contract test checks
  the worker's definitions against the migrated schema.
- **Feature engineering and inference run only in Python.** We won't export models to ONNX for use in
  .NET during the MVP: that would mean rewriting feature engineering (operating mode,
  steady-state filtering) in C#. The two versions would drift, and diagnoses would go wrong without any error showing.

### API conventions

- JSON uses `snake_case`, the same as the Python side and the frontend.
- Timestamps are ISO 8601 and timezone-aware (UTC).
- Errors use RFC 9457 Problem Details (`application/problem+json`), with a stable `code` extension
  for clients to branch on. Stack traces and internal details are never returned.
- OpenAPI is served at `/api/v1/openapi.json`.

### Toolchain

- **.NET 10 LTS:** the SDK is pinned in `api/global.json`. The runtime image is
  `mcr.microsoft.com/dotnet/aspnet:10.0.14-noble-chiseled`, which runs as non-root and has no shell.
- Package versions are managed centrally (`Directory.Packages.props`), with `packages.lock.json`
  files committed. Warnings are treated as errors, and nullable reference types are enabled.
- Tests use xUnit and `WebApplicationFactory`.
- The Python side keeps [ADR 0004](0004-python-toolchain.md) (Python 3.13 and uv), now scoped to `pipeline/`.

## Consequences

- There are two languages and toolchains, and one more container (`worker`). CI runs three jobs.
- The job table and result tables are a contract between the two languages, so they need versioning and tests.
- Ownership is clear: .NET never computes features or predictions, and Python never serves HTTP to the frontend.
- Revisit this decision if inference ever needs very low latency inside the API. Even then, prefer a
  Python inference service over porting features to C#.
