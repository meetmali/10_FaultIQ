# 0010. Polars, PyArrow and DuckDB for data processing

- **Status:** Accepted. Replaces pandas as the main pipeline data library from the project plan. Amended by [0016](0016-corrections-to-chart-zoom-and-shap.md) (DuckDB only in notebooks, scripts and reports).
- **Date:** 2026-11-05
- **Introduced in:** Phase 1 (loader and EDA) and Phase 2 (pipeline).

## Context

The pipeline reads many large CSV files (one fault scenario per file, about 500,000 rows each),
validates them, aligns timestamps, derives operating mode and steady-state flags, and builds rolling
features. pandas runs on a single core, copies data often, and needs a lot of memory for this workload.
The pipeline must also be reproducible: the same input must always give the same output.

## Decision

- **Polars** is the DataFrame library for everything in `pipeline/faultiq/`.
  - Use the lazy API (`scan_csv`, `scan_parquet`) for ingestion and feature pipelines. This gives
    multi-core execution and query optimisation.
  - Declare explicit schemas and dtypes on read. Never rely on type inference for production loads.
- **PyArrow and Parquet** are the storage format for validated and processed data
  (see [0006](0006-storage-postgres-records-files-for-samples.md)).
- **DuckDB** handles ad-hoc and bounded-slice queries directly over Parquet: EDA, evaluation reports,
  and chart zoom requests (see [0009](0009-echarts-and-precomputed-downsampled-series.md)).
  It is never used as a second system of record.
- **pandas** is allowed in notebooks and at library boundaries that require it, such as
  some plotting or SHAP helpers. Convert with `.to_pandas()` at the edge. Pipeline modules
  never depend on it.
- **NumPy** for numerical work. scikit-learn and LightGBM take Polars or NumPy input directly.

## Consequences

- The pipeline is expected to run several times faster with lower memory use. Phase 2 will measure
  this and report it in the validation report, rather than assume it.
- Polars has a different API from pandas, so there's a short learning curve. Notebook examples will
  show the common patterns.
- Rolling-window and time-alignment logic must be unit-tested carefully, including at window edges and gaps.
