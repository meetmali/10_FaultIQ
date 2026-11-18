# Deploying FaultIQ: public demo or self-hosting

The public demo and a self-hosted installation use the **same files and steps**. The only difference is
`DEMO_MODE` ([ADR 0017](decisions/0017-deployable-demo-same-artifacts-as-self-hosting.md)).

## What you need

- A Linux machine with **Docker** and the Docker Compose plugin. 2 vCPU, 4 GB RAM and 20 GB of disk is plenty for the demo.
  Options include a small VPS, a free-tier cloud VM (check the provider's current terms), or your organisation's own server.
- For HTTPS: a **domain name** with a DNS `A` (and optionally `AAAA`) record pointing at the machine.
- Ports **80** and **443** open to the internet. Open nothing else except SSH.

## First deployment

```bash
git clone https://github.com/meetmali/FaultIQ.git
cd FaultIQ
cp .env.prod.example .env.prod
```

Edit `.env.prod`:

| Setting | Demo | Self-hosting |
|---|---|---|
| `SITE_ADDRESS` | your domain, e.g. `demo.example.org` | your domain, or `:80` on a private network |
| `DEMO_MODE` | `true` | `false` |
| `POSTGRES_PASSWORD` | output of `openssl rand -hex 32` | the same |

Then start it with the prebuilt images:

```bash
docker compose -f compose.prod.yml --env-file .env.prod pull
docker compose -f compose.prod.yml --env-file .env.prod up -d
```

To build from source instead of pulling (for example to run unreleased changes), use
`up -d --build` and skip `pull`.

Open `https://<your domain>`. Caddy fetches the certificate automatically on the first request, which can take a few seconds.
Check the API with `https://<your domain>/api/v1/health/ready`.

## Routine upkeep

| Task | Command or action | How often |
|---|---|---|
| Update FaultIQ | `docker compose -f compose.prod.yml --env-file .env.prod pull && docker compose -f compose.prod.yml --env-file .env.prod up -d` | each release |
| Back up the database | `docker compose -f compose.prod.yml --env-file .env.prod exec postgres pg_dump -U faultiq faultiq > backup-$(date +%F).sql` | daily (cron), keep copies off the machine |
| Check status and logs | `docker compose -f compose.prod.yml --env-file .env.prod ps` and `... logs --tail 100` | when something looks wrong |
| Patch the OS | your distribution's security updates (for example unattended-upgrades) | automatic |

Restore a backup with
`docker compose -f compose.prod.yml --env-file .env.prod exec -T postgres psql -U faultiq faultiq < backup.sql`.
**Test a restore at least once.** An untested backup can't be relied on.

## Security notes

- Only the `web` container is published. Don't add ports for `api` or `postgres`.
  The API trusts Caddy's forwarded client IP only because it can't be reached directly.
- Never commit `.env.prod`.
- The demo must stay `DEMO_MODE=true`. It rejects all writes, and the UI tells visitors not to enter real data.
- Report vulnerabilities as described in [SECURITY.md](../SECURITY.md).

## Publishing new images (maintainers)

```bash
git tag v0.1.0
git push origin v0.1.0
```

The **Release images** workflow publishes `ghcr.io/<owner>/faultiq-{api,worker,web}:0.1.0` and `:latest`.
After the first release, make each package **public** in GitHub, under Packages and then Package settings, so servers
can pull images without logging in.
