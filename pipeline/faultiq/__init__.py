"""FaultIQ FDD pipeline library.

This package has no dependency on FastAPI. Notebooks, scripts and the API all
import from it.
"""

__version__ = "0.1.0"

# Bump PIPELINE_VERSION whenever a change to ingestion, validation,
# preprocessing or feature engineering could change outputs for the same input.
# Every inference records this value (see the README, section 6).
PIPELINE_VERSION = "0.2.0"
