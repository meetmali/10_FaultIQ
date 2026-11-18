# Development conventions

## Branches and commits

- `main` should always be releasable. Work happens on short-lived branches named
  `phase-N/<topic>`, `feat/<topic>`, `fix/<topic>` or `docs/<topic>`.
- Merge into `main` through a pull request, with CI green.
- Commit messages use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(api): add ingestion endpoint`, `fix(validation): reject duplicate timestamps`.
- Tag each phase's completion: `phase-0`, `phase-1`, and so on. Releases use SemVer tags (`v0.1.0`).

## Issue board

Track work on a GitHub Project with one milestone per phase (Phase 0–9). Each issue
names its phase, its deliverable and its exit criterion. Use the templates in `.github/ISSUE_TEMPLATE/`.

## Code quality

| Area | Tools | Command |
|------|-------|---------|
| API format and analyzers | `dotnet format`, .NET analyzers (warnings are errors) | `make lint`, `make typecheck` |
| API tests | xUnit, WebApplicationFactory | `make test-api` |
| Pipeline lint and format | ruff | `make lint` / `make format` |
| Pipeline types | mypy (strict) | `make typecheck` |
| Pipeline tests | pytest | `make test-pipeline` |
| Frontend lint | ESLint | `npm run lint` (in `frontend/`) |
| Frontend types and build | tsc, Vite | `npm run build` |
| Frontend tests | Vitest, React Testing Library | `make test-frontend` |

CI (`.github/workflows/ci.yml`) runs all of these on every push and pull request.

## Versioning that matters for FDD

- `faultiq.PIPELINE_VERSION`: bump it whenever an ingestion, validation, preprocessing or feature
  change could alter outputs for the same input.
- Model versions are introduced in Phase 3/4, and each one gets a model card in `docs/model-card.md`.
- Every reported metric names its data split strategy.

## Data hygiene

- NuGet packages are versioned centrally in `api/Directory.Packages.props`. Commit the `packages.lock.json` files.
- Never commit raw or processed data, model binaries, or `.env`. `.gitignore` enforces this.
- Notebooks are for exploration only. Reusable logic moves into `pipeline/faultiq/` with tests.
