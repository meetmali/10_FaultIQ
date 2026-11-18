# Contributing to FaultIQ

Thank you for helping. FaultIQ is a free, open-source (MIT) project. It brings HVAC fault detection
and diagnostics to building owners who can't afford commercial tools.

## Ways to help

- **HVAC and BAS expertise.** Review fault definitions, rules and diagnostic checks. Your domain
  knowledge is as valuable as code.
- **Code.** Contribute to the .NET API (`api/`), the Python pipeline (`pipeline/`) or the React
  frontend (`frontend/`).
- **Data.** Share point-naming examples from different control systems. **Never share real
  building data in issues or pull requests.** Use synthetic or sanitized examples only.
- **Docs and testing.** Improve the setup guide, report bugs, or try FaultIQ on your own exports.

## Getting started

1. Read the [README](README.md#local-setup) and run `make setup` and then `make check`.
2. Skim the [architecture](docs/architecture.md) and the [decision records](docs/decisions/README.md).
   They explain *why* the project looks the way it does.
3. Pick an issue labelled `good first issue`, or open one to discuss your idea before starting
   large changes.

## Pull requests

- Branch from `main` (`feat/<topic>`, `fix/<topic>`, `docs/<topic>`).
  Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.
- `make check` must pass. Add tests for new behaviour.
- Keep the project's boundaries:
  - The .NET API never computes features or predictions. That belongs in `pipeline/` (ADR 0007).
  - Model output is never presented as a confirmed root cause.
  - Every result stays traceable to its source file, `pipeline_version` and `model_version`.
- New dependencies must be free and permissively licensed (MIT, Apache-2.0, BSD or similar).
  See [ADR 0014](docs/decisions/0014-pro-bono-open-source-self-hostable.md).
- A significant design change needs a new ADR (see [`docs/decisions/template.md`](docs/decisions/template.md)).

## Conduct and security

- Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security vulnerabilities **privately**, as described in [SECURITY.md](SECURITY.md). Don't open public issues for them.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
