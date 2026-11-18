# 0012. OpenTelemetry for observability

- **Status:** Accepted. Amended by [0015](0015-mainstream-free-stack-resolutions.md).
- **Date:** 2026-11-05
- **Introduced in:** Phase 6 (API and worker job flow). Exporting to a backend is set up in Phase 8–9.

## Context

A single request now crosses two runtimes: an upload goes through the .NET API, then a job in
PostgreSQL, then the Python worker, then the results. The project plan (section 13) asks for request count,
latency, error rate, ingestion outcomes, validation rejection reasons, processing duration, job
failures and model version. Without shared telemetry, slow or failed analyses are hard to trace.

## Decision

- Instrument **both services with OpenTelemetry**: traces, metrics and logs linked by trace ID.
  - **.NET:** the OpenTelemetry .NET SDK, with ASP.NET Core, HttpClient and Npgsql instrumentation.
  - **Python:** the OpenTelemetry Python SDK, with manual spans for each pipeline stage (validate,
    preprocess, features, detect, diagnose, explain) and SQLAlchemy instrumentation.
- **Trace context crosses the job table.** The API writes a W3C `traceparent` value onto the job row,
  and the worker continues the same trace. One upload can then be followed end to end.
- Custom metrics:
  - `faultiq.jobs` (count by status)
  - `faultiq.job.duration` (by stage)
  - `faultiq.validation.rejections` (by reason)
  - `faultiq.diagnoses` (by outcome, including inconclusive, and `model_version`)
- **Export:** OTLP to a local collector, using the Grafana LGTM all-in-one container, added as an
  optional Compose profile. Console or no-op in tests.
- Telemetry never includes raw sensor values, uploaded file contents, credentials or connection strings.

## Consequences

- Both services have one standard instrumentation model, with no vendor lock-in.
- The optional observability container is used only when someone runs that Compose profile.
