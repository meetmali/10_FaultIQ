# 0006. PostgreSQL for records, files for samples

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

A year-long RTU simulation at minute resolution comes to roughly 500k rows per file, with many
columns, and there are many fault scenarios. Storing every sample as a relational row
(long format, `sensor_name`/`value`) would make the database very large and slow, and the ML
pipeline works on wide tables anyway.

## Decision

- **PostgreSQL 17** holds *application records*: sites, equipment, data sources,
  ingestion jobs, diagnostic runs, fault events, evidence items, the fault library and model versions.
- **Raw files** stay immutable on file storage (`data/raw/`, and the uploads volume), each with
  a server-generated ID and a content hash.
- **Validated and processed data** are stored as **wide-format Parquet** files, partitioned by
  source, and reproducible from the raw files and `PIPELINE_VERSION`.
- Evidence items store only the bounded slices of time series needed for display.
- TimescaleDB is deferred. We adopt it only if measured query needs justify it, via a new ADR.

## Consequences

Lineage has to be tracked explicitly: from raw file and hash, to the processed artifact, to the diagnostic run.
The long-format representation in section 7.2 of the project plan is treated as a conceptual
model, not a storage format. The final schema is set in Phase 6, after Phase 1 EDA.
