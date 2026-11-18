# 0016. Corrections: chart zoom without DuckDB in the API, and SHAP from LightGBM

- **Status:** Accepted. Amends [0009](0009-echarts-and-precomputed-downsampled-series.md),
  [0010](0010-polars-pyarrow-duckdb-data-processing.md) and [0011](0011-scikit-learn-lightgbm-shap.md).
- **Date:** 2026-11-05

## Context

A review of the stack's downsides found two problems:

1. **ADR 0009** said that zooming deeper into a chart would read bounded Parquet slices "via DuckDB" at
   request time. That would require either a third data-access technology in the .NET API, or a direct
   API-to-worker call, which ADR 0007 forbids.
2. **ADR 0011** adopted the `shap` package. It brings in numba and llvmlite, which slow down installs and
   often conflict with NumPy versions. LightGBM already computes the same TreeSHAP values natively.

## Decision

1. **Chart zoom uses precomputed resolution levels.** For each analysis, the worker writes downsampled series
   at a few fixed levels: an overview of the whole period, a medium level, and full or near-full detail for
   each detected event window. The API only serves these stored series. **DuckDB is used only in
   notebooks, scripts and evaluation reports**, never in the API.
2. **Feature attributions come from LightGBM's** `predict(..., pred_contrib=True)`, which is TreeSHAP and has
   no `shap` dependency.
   - For the non-tree baselines, use scikit-learn's permutation importance at the model level.
   - Per-prediction attributions are shown only for tree models.
   - The `shap` package is added only for notebook visualisations, if ever.

## Consequences

- The API has one data-access technology (EF Core and Npgsql), and the no-direct-calls rule holds.
- The pipeline and worker images are smaller and faster to install.
- Zoom detail outside detected event windows is limited to the medium level. That's acceptable, because the
  investigation workflow centres on detected events.
