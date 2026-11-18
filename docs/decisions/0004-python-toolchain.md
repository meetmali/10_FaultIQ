# 0004. Python 3.13 with uv

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

The project plan requires a pinned Python version and committed lock files. The scientific
stack (pandas, NumPy, scikit-learn, and optionally XGBoost) needs a mature interpreter.

## Decision

- **Python 3.13.** Pinned in `.python-version` and `requires-python = ">=3.13,<3.14"`.
  The container image uses `python:3.13.18-slim`. We chose 3.13 over 3.14 for the most
  conservative wheel availability across the ML stack.
- **uv** handles environments, dependency resolution and the lock file (`pipeline/uv.lock`,
  committed). The container installs with `uv sync --frozen`.
- **ruff** handles linting and formatting, **mypy (strict)** handles types, and **pytest** handles tests.

## Consequences

You need `uv` installed locally (`brew install uv`). Revisit moving to 3.14 when Phase 1
dependencies are added, if every one of them ships 3.14 wheels.
