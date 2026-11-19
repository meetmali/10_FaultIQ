# 0024. API, persistence and the analysis job loop

- **Status:** Accepted
- **Date:** 2026-11-19
- **Contracts:** [openapi.json](../contracts/openapi.json), [diagnostic-result.schema.json](../contracts/diagnostic-result.schema.json),
  [schema.sql](../../api/migrations/schema.sql)

## Context

Phases 1–5 run as scripts over the LBNL files. Phase 6 must let a client submit data, start an
analysis and read persisted results through documented contracts. ADR 0007 already fixes the shape:
- the .NET API owns HTTP and the schema,
- the Python worker owns analysis,
- PostgreSQL is the only thing between them.

The owner chose:
- local PostgreSQL 17 through Homebrew for development (Docker isn't installed),
- bundled LBNL models only,
- results as JSONB plus summary tables,
- no login until Phase 8.

## Decision

**Schema (EF Core, snake_case, the only source of truth).** Four tables:

| Table | Holds | Notes |
|---|---|---|
| `equipment` | A unit (name, site) | Index on site |
| `uploads` | A stored CSV: server-generated name, format, size, SHA-256 | Original name kept for display only; check constraint on format |
| `analyses` | One analysis **and** its job row: status, attempts, worker, `traceparent`, safe error, versions, summary counts, the `result` and `chart_series` as JSONB | Check constraints on status and point set; index `(status, created_at)` serves the claim query |
| `fault_events` | One row per event, copied from the result | Filterable across analyses for the dashboard; cascade-deleted with its analysis |

The result stays one JSONB document: the Phase 5 contract, unchanged. Events are copied out only so
lists can be filtered and paginated with indexes. Migrations also ship as an idempotent SQL script
(`api/migrations/schema.sql`) for review and for the worker's contract test, and CI fails if the two
drift apart.

**API (`/api/v1`).**
- `POST /equipment` and `GET /equipment[/{id}]`.
- `POST /uploads`: multipart file, `equipment_id`, `format`.
- `POST /analyses` returns `202` with a `Location`.
- `GET /analyses`, `GET /analyses/{id}`, `/{id}/result` and `/{id}/series`.
- `GET /fault-events`.

Lists page with `page` and `page_size` (at most 100) and return a total. Errors are RFC 9457
problems with a stable `code`:
- `validation_error`, `not_found`, `unsupported_file_type`, `not_text`, `upload_too_large`,
- `result_not_ready`, `analysis_failed`.

The result and series endpoints pass the stored JSON through untouched; the API never re-models it.

**Uploads are untrusted.** The checks run in order, cheap ones first and the database last:
1. the format must be on an allow-list,
2. the extension must be `.csv`,
3. the size must be within `Uploads:MaxSizeMb` (Kestrel and form limits set to match),
4. the first 8 KB must be text (no NUL bytes, valid UTF-8),
5. the equipment must exist.

The file is streamed to disk under `{guid}.csv` while its SHA-256 is computed, then renamed into
place. The user's file name is never part of a path. Storage sits behind `IFileStore` (ADR 0015):
local disk now, S3-compatible later.

**The job loop (ADR 0007, made concrete).**
- The API inserts a `queued` row and records the request's W3C `traceparent`.
- The worker claims the oldest queued row with `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED
  LIMIT 1) RETURNING …`.
- It then runs validate and preprocess (Phase 2), then detect, diagnose, explain and check
  (Phases 3–5), then the chart series.
- It writes the result, the event rows and `succeeded` in **one transaction**. That update only
  applies while the row is still `running`, so a slow worker whose job was requeued can't overwrite
  a newer attempt.
- Failures store a stable code and a message safe to show users (never a stack trace or a server
  path). Details go to the logs, tagged with the trace ID.
- A row left `running` past `job_timeout_minutes` is requeued, and fails as `worker_timeout` after
  3 attempts.
- The worker polls when idle. `LISTEN/NOTIFY` stays optional.

**Models.** `python -m faultiq train-models` (`make train-models`) fits one frozen Diagnoser per
format and point set:
- **Simulated:** the Phase 4 splits.
- **ORNL:** a production split, with three seasons training and Winter 2022 validating.

It writes them with joblib and a manifest recording each file's SHA-256 and a `model_version`
(`lbnl_simulated-all@diagnosis-0.1.0+<sha>`). Model files are pickles, so they run code when loaded.
The worker therefore loads them only from its configured directory, and only after the hash
matches. Uploads are never unpickled. Models are git-ignored, mounted read-only into the worker, and
not published: they are built from the LBNL data, which each installer downloads under its own terms.

**Chart series (ADR 0009, simplified).** The worker stores the downsampled series as JSONB on the
analysis, not as Parquet files:
- an overview of outdoor, return, mixed and supply air at up to 2,000 points each, using LTTB,
- for each of the 50 longest events, its evidence signals ±2 h around the event (observed and,
  where the normal model applies, expected) at up to 500 points.

One real analysis is about 400 kB. This drops the Parquet reader the API would otherwise need.
Zooming deeper than the stored series (DuckDB slices in ADR 0009) is deferred until a user needs it.

**Tracing (ADR 0012).**
- **API:** OpenTelemetry for ASP.NET Core and Npgsql.
- **Worker:** the OpenTelemetry SDK with one span per stage, continuing the trace from the job row's
  `traceparent`, so one upload is a single trace from HTTP request to finished analysis.
- Spans are exported over OTLP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Even without an
  exporter, worker logs carry the same trace ID the API returns in problem responses.

**Contracts are committed and enforced.**
- `docs/contracts/openapi.json` is regenerated with `UPDATE_CONTRACTS=1 dotnet test`; a test fails if
  the API differs.
- The frontend types are generated from it with `openapi-typescript`, and from the result schema with
  `json-schema-to-typescript`. CI fails if regenerating changes them.
- Field-level titles are dropped from the exported result schema so the generated names don't clash.
- JSON numbers are strict (no `"42"`), so integers stay integers in TypeScript.

**Testing without surprises.** API tests run in a `Testing` environment, so a developer's database
settings never apply. Database tests use `FAULTIQ_TEST_DB` / `FAULTIQ_TEST_DATABASE_URL` and are
skipped, with a reason, when those aren't set. CI provides a PostgreSQL service for both jobs. The
worker's tests prove:
- its tables match the migrated schema,
- 20 jobs claimed by 4 concurrent workers are each taken exactly once,
- completion is atomic,
- a requeued job can't be completed by its old worker,
- stale jobs retry, then fail.

**Not in this phase.**
- Login and antiforgery (Phase 8). Uploads disable antiforgery explicitly because no cookie
  authentication exists yet; Phase 8 must turn it back on.
- Deleting or retrying analyses.
- `LISTEN/NOTIFY`.
- Per-site baselines for non-LBNL units.

## Consequences

- The Phase 6 exit criterion is met on a real database: through the frontend's proxy, a client
  creates equipment, uploads an LBNL CSV, starts an analysis and reads the checked result, its events
  and its chart series.
  - A 100-day simulated file takes about 5.5 s in the worker.
  - A broken file fails with `validation_failed` and a readable reason.
- One process boundary now carries a lot of contract: SQL schema, JSONB document, OpenAPI and
  generated TypeScript. Each is a committed file with a drift test, which is the price of keeping
  feature code in one language (ADR 0007).
- Analysing an LBNL file overlaps the data the bundled models were trained on, so those results are
  a demonstration. The held-out evaluation stays in the Phase 3–5 reports.
- **Until Phase 8, a writable instance must not be exposed to the internet.** The deployment guide
  says so.
- Revisit when:
  - a second worker process is needed (claiming already supports it),
  - users zoom past the stored series,
  - a non-LBNL site needs analysis, which needs per-site baselines and a new ADR.
