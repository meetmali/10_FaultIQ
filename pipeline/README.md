# FaultIQ pipeline (Python)

All data and ML work lives here (see [ADR 0007](../docs/decisions/0007-hybrid-dotnet-api-python-pipeline.md)):

- `faultiq/` is the FDD library: ingestion, validation, preprocessing, features, detection, diagnosis
  and evaluation. It's pure Python with no database or web dependencies. Notebooks, scripts and
  the worker all import it.
- `worker/` is the background process. It claims analysis jobs from PostgreSQL, runs `faultiq`, and writes
  results with `pipeline_version` and `model_version`. In Phase 0 it only checks database
  connectivity and sends a heartbeat. The job queue arrives in Phase 6.

The .NET API in `../api/` never computes features or predictions. It only creates jobs and reads results.

Setup and commands: see the [root README](../README.md#local-setup).
