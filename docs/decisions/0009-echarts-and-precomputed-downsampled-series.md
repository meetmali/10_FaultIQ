# 0009. Apache ECharts for charts, with precomputed downsampled series

- **Status:** Accepted. Replaces Plotly from the project plan and [0005](0005-frontend-toolchain.md). Amended by [0016](0016-corrections-to-chart-zoom-and-shap.md) (zoom uses precomputed levels, not DuckDB in the API).
- **Date:** 2026-11-05
- **Introduced in:** Phase 6 (the worker writes chart series) and Phase 7 (charts).

## Context

One RTU-year at one-minute resolution is about 525,000 points per sensor. The Fault Diagnostics
screen overlays several sensors (SAT, MAT, RAT, OAT, damper position, fan status). Sending raw
series to the browser, or drawing them with a heavy SVG-based library, makes the most important
screen slow.

## Decision

- **Apache ECharts** is the single charting library. It draws on canvas, so large series stay smooth.
  It also has built-in LTTB point reduction, data zoom, shaded interval markers for the detected fault
  window, and accessibility settings (`aria`) for chart summaries.
  - Charts are lazy-loaded, and only the ECharts modules we use are imported, to keep the bundle small.
  - Evaluation charts (confusion matrices, reliability curves) are also drawn with ECharts, for consistency.
- **The API never sends raw time series to the browser.**
  - When the worker finishes an analysis, it writes **precomputed, downsampled chart series**:
    LTTB down to about 2,000 points per sensor per view.
  - It writes one overview series for the whole period and one detailed series for each detected
    event window.
  - These are stored as Parquet files and referenced from the result.
  - The API serves these small, ready-to-draw series. If a user zooms deeper, the API asks for a
    bounded slice from the processed Parquet file (DuckDB, see [0010](0010-polars-pyarrow-duckdb-data-processing.md)).
- Every chart labels its axes with units and says when the data shown is downsampled. Downsampling
  is a display transform only. Detection and diagnosis always run on full-resolution data.

## Consequences

- Chart responses stay small and fast whatever the size of the source file.
- The worker takes a little longer per job, and uses a little more storage per result.
- The plan's references to Plotly are replaced.
