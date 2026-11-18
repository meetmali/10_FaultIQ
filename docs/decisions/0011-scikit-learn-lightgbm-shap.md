# 0011. scikit-learn and LightGBM for models, SHAP for explanations

- **Status:** Accepted. Replaces "XGBoost (optional)" from the project plan. Amended by [0016](0016-corrections-to-chart-zoom-and-shap.md) (attributions from LightGBM `pred_contrib`, not the `shap` package).
- **Date:** 2026-11-05
- **Introduced in:** Phase 3 (detection) and Phase 4 (diagnosis).

## Context

Diagnosis is supervised classification on tabular sensor features, with imbalanced classes and
fault classes that look alike. It needs good per-class performance, calibrated confidence, fast training
for many cross-validation runs, and explanations that can be traced back to specific sensor features.

## Decision

- **scikit-learn** is the framework for baselines and evaluation:
  - Rule and statistical baselines, logistic regression and Random Forest.
  - Isolation Forest, only if it adds measurable value.
  - `GroupKFold` and `GroupShuffleSplit` for leakage-aware splits by file or fault episode.
  - `CalibratedClassifierCV` for calibration.
  - Standard metrics and reliability curves.
- **LightGBM** is the gradient-boosting candidate. Use it through its scikit-learn API so it works with
  the same pipelines, splits and calibration as the baselines.
  - It's chosen over XGBoost for faster training on CPU, native categorical support (operating
    mode, for example) and a smaller footprint.
  - It's adopted only if it beats the simpler baseline on held-out macro-F1 under the documented split.
- **SHAP** (TreeExplainer) provides per-prediction feature attributions. These become *model evidence*
  in the diagnostic result. They're kept clearly separate from measured sensor evidence, and never
  presented as physical root cause.
- Models are saved with `joblib` and a manifest that records the model version, training data
  hashes, split strategy, feature list and `PIPELINE_VERSION`. Model binaries are never committed to Git.

## Consequences

- One ecosystem covers training, evaluation, calibration and explanations, so there's less glue code.
- SHAP adds compute per diagnosis. It's computed once by the worker and stored with the result,
  not on each API request.
