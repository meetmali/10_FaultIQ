# FaultIQ

**Agentic fault detection and diagnostics (FDD) for HVAC rooftop units.** FaultIQ detects abnormal
operating behaviour, diagnoses which supported fault type it matches (or says the result is inconclusive), and
shows the evidence behind each result.

FaultIQ is **pro bono and open source (MIT)**. It's free to use and to self-host, so building owners
without a budget for commercial FDD software can still find and understand faults. FaultIQ supports
decisions. It never controls equipment, doesn't predict future failures, and is not a substitute for a
qualified HVAC technician.

- **Project plan and roadmap:** [`FaultIQ_README.md`](FaultIQ_README.md)
- **Architecture:** [`docs/architecture.md`](docs/architecture.md) · **Decisions:** [`docs/decisions/`](docs/decisions/README.md)
- **Scope and screens:** [`docs/scope.md`](docs/scope.md) · **Conventions:** [`docs/development.md`](docs/development.md)

**Current phase:** Phase 0, repository setup.

## Stack at a glance

| Part | Technology | Arrives |
|------|------------|---------|
| API (`api/`) | ASP.NET Core, .NET 10 LTS, C#, EF Core | Phase 0 / 6 |
| Data and worker (`pipeline/`) | Python 3.13, Polars, PyArrow, uv (DuckDB in notebooks and reports only) | Phase 0 / 1–2 |
| ML | scikit-learn, LightGBM (if it beats the baseline), TreeSHAP attributions from LightGBM | Phase 3–4 |
| Frontend (`frontend/`) | React, TypeScript, Vite, Tailwind + shadcn/ui, TanStack Query, React Router | Phase 0 / 7 |
| Charts | Apache ECharts, drawn from precomputed downsampled series | Phase 6–7 |
| Storage | PostgreSQL 17 for records, Parquet for processed data | Phase 0 / 2 |
| Observability | OpenTelemetry across the API and worker | Phase 6 / 8 |
| Auth | ASP.NET Core Identity (local accounts) + optional OIDC provider | Phase 6 |
| File storage | Local disk by default, optional S3-compatible | Phase 6 |

Deliberately left out: Kafka, Redis, Kubernetes, extra microservices and deep learning
([ADR 0013](docs/decisions/0013-infrastructure-restraint.md)).

The API handles HTTP, uploads, jobs and persistence. All feature engineering, detection, diagnosis and
evaluation happen in Python. The two communicate only through PostgreSQL
([ADR 0007](docs/decisions/0007-hybrid-dotnet-api-python-pipeline.md)).

## Repository layout

```text
api/        ASP.NET Core API (src/FaultIQ.Api) + xUnit tests
pipeline/   Python FDD library (faultiq/) + background worker (worker/) + pytest
frontend/   React + TypeScript + Vite + Tailwind
docs/       architecture, ADRs, scope, (later) data dictionary, dataset and model cards
data/       raw/ interim/ processed/ are git-ignored; sample/ is for synthetic data only
notebooks/  EDA (Phase 1+)
scripts/    dataset inspection and batch analysis (Phase 1+)
```

## Local setup

### Prerequisites

| Tool | Version | Install (macOS) |
|------|---------|-----------------|
| Git | any recent | |
| Docker + Docker Compose | Docker Desktop or OrbStack | `brew install --cask docker` or `brew install orbstack` |
| .NET SDK | 10.0.403 (`api/global.json`) | `brew install dotnet` |
| Python | 3.13 (`.python-version`) | `brew install python@3.13` |
| uv | 0.13+ | `brew install uv` |
| Node.js | 26 LTS (`.nvmrc`; ≥24 works) | `brew install node@26` or nvm |

The .NET SDK, Python, uv and Node are only needed to run things outside Docker or to run tests.

### Option A: everything in Docker

```bash
git clone https://github.com/meetmali/FaultIQ.git
cd FaultIQ
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/api/v1/health |
| API readiness (checks the DB) | http://localhost:8000/api/v1/health/ready |
| OpenAPI document | http://localhost:8000/api/v1/openapi.json |
| PostgreSQL | `localhost:5432` (credentials from `.env`) |

All ports bind to `127.0.0.1` only. Check the worker with `docker compose logs worker`. Stop everything with
`docker compose down`. Add `-v` to also delete the database volume.

### Option B: run each part natively

```bash
make setup      # dotnet restore + uv sync + npm ci
make api        # http://localhost:8000 (dotnet watch)
make frontend   # http://localhost:5173 (second terminal)
make worker     # optional; needs PostgreSQL on localhost:5432
```

Without PostgreSQL running, `/health` still returns `200`, while `/health/ready` returns `503`
with `database: unavailable`. That's the expected behaviour.

### Tests and checks

```bash
make check      # dotnet format/build/test, ruff, mypy, pytest, eslint, tsc, vitest
```

Run `make help` to list all targets.

## Deploying (public demo or self-hosting)

One production setup serves both purposes. Set `DEMO_MODE=true` for a read-only, sample-data demo, or `false`
to analyse your own data:

```bash
cp .env.prod.example .env.prod      # set SITE_ADDRESS (your domain) and POSTGRES_PASSWORD
docker compose -f compose.prod.yml --env-file .env.prod pull
docker compose -f compose.prod.yml --env-file .env.prod up -d
```

Caddy handles HTTPS automatically. The full guide, including backups and updates, is in
[docs/deployment.md](docs/deployment.md).

## Contributing

HVAC and BAS experts, developers and testers are all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md),
the [Code of Conduct](CODE_OF_CONDUCT.md) and the [security policy](SECURITY.md).

## Dataset

The MVP uses the [LBNL Rooftop Unit Fault Detection Dataset](https://faultdetection.lbl.gov/dataset/rtu/).
Download it separately into `data/raw/`. **Never commit it.** Attribution and usage terms
will be recorded in `docs/dataset-card.md` during Phase 1.

## Known issues (Phase 0)

- Neither Compose stack (development or production) has been run yet, because Docker isn't installed on the
  development machine. The API, worker, frontend and Caddy configuration have been verified natively, and CI
  builds all three images on every pull request.
- No release images have been published yet. The first `v*` tag publishes them. Until then, use `up -d --build`.
- The API container has no `HEALTHCHECK`, because the chiseled .NET image has no shell or curl. Use `/api/v1/health/ready` instead.
- `npm audit` reports moderate advisories in ESLint's own dependency chain. These are dev tooling only and don't ship to the browser.
- Playwright (end-to-end tests) is deferred to Phase 7, when the first real user journey exists.

## License

[MIT](LICENSE). FaultIQ is provided "as is", without warranty. Results are decision support only.
