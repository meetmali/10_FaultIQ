# 0017. A deployable demo that uses the same artifacts as self-hosting

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

[ADR 0014](0014-pro-bono-open-source-self-hostable.md) calls for a public demo that uses sample data only. The owner
wants the demo to be deployable. A separate demo codebase or a platform-specific setup would double the
maintenance work. The project has to stay simple enough for one maintainer and volunteers to run.

## Decision

- **One production setup serves both the public demo and self-hosting:** `compose.prod.yml`.
  The only difference is `DEMO_MODE=true` or `false` in `.env.prod`.
- **Four containers:** `postgres`, `api`, `worker` and `web`.
  - `web` is **Caddy**. It serves the built frontend, proxies `/api` to the API on the same origin (so no CORS
    is needed), and gets **HTTPS certificates automatically** for the configured domain. It also adds security headers.
  - Only `web` is exposed to the internet. The API, worker and database stay on the internal Docker network.
- **Demo mode** (`Demo__Enabled=true`):
  - The API rejects every write request under `/api` with a `403` `demo_read_only` problem response.
    This covers future upload and job endpoints automatically.
  - `/api/v1/health` reports `demo_mode`, and the frontend shows a "Public demo: sample data only" banner on every screen.
  - Sample data is loaded by a seed script once results exist (Phase 6–7). The demo never accepts real building data.
- **Abuse protection, always on:** the built-in ASP.NET Core rate limiter, set by default to 300 requests per minute per
  client IP. The client IP comes from Caddy's `X-Forwarded-For` header, which the API trusts only because it isn't
  reachable directly.
- **Images:**
  - A tag push (`v*`) publishes `faultiq-api`, `faultiq-worker` and `faultiq-web` to **GitHub Container Registry**
    (free for public repos), for amd64 and arm64.
  - Servers pull the images. Building from source with `--build` also works.
  - CI builds all three images on every pull request, so contributors don't need Docker locally.
- **Hosting target: any Linux machine with Docker.** That might be a small VPS, a free-tier cloud VM, or an
  organisation's own server. The same steps work everywhere. See [`docs/deployment.md`](../deployment.md).

### Rejected

| Option | Why not |
|---|---|
| Separate demo build or codebase | Two things to maintain, and they'd drift apart |
| Free PaaS tiers (per-platform config) | Services sleep, free databases expire, and each platform needs its own configuration |
| Kubernetes or Helm | Far more to run than four containers need (ADR 0013) |
| A separate CDN or static host for the frontend | A second deployment target and CORS. Caddy already serves it with compression and caching |

## Consequences

- The demo is deployable now. **It's worth actually deploying once there is sample content to show (Phase 7).**
  Deploying the Phase 0 shell earlier adds server upkeep for little benefit.
- Running a public demo means someone has to keep the server patched and the images up to date.
  [`docs/deployment.md`](../deployment.md) lists the minimal routine.
- The Docker images are checked in CI only until Docker is available on the maintainer's machine.
