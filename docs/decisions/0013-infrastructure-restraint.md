# 0013. Infrastructure restraint

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

The aim is a system that is fast and professional. It's tempting to add infrastructure that *looks*
enterprise-grade. For a batch FDD MVP, most of it would add operational cost and slow delivery
without making anything faster for users.

## Decision

These are **not** used in the MVP. Each one needs a new ADR with measured evidence before it can be added:

| Not adopting | Why | What we use instead |
|---|---|---|
| Kafka, MQTT or stream processing | Input is batch CSV. Streaming is a future extension (plan, section 19) | PostgreSQL job table |
| Redis or a separate message broker | Job volume is low; another stateful service to run | `FOR UPDATE SKIP LOCKED`, optionally `LISTEN/NOTIFY` |
| Kubernetes | A handful of containers on one host | Docker Compose, then a managed container service |
| More microservices | Each split adds network calls, failure modes and deployments | API, worker, database and frontend only |
| Deep learning, GPUs | Tabular sensor features and limited labelled data; harder to explain and calibrate | scikit-learn and LightGBM ([0011](0011-scikit-learn-lightgbm-shap.md)) |
| A separate time-series database | Not justified until measured | PostgreSQL plus Parquet; TimescaleDB only by ADR |

## Consequences

The system stays small enough to test, observe and run as a solo project. "Professional" here means
measured performance, documented decisions, tests, traceable results and honest limitations, not the number of components.

## Complexity budget (added 2026-11-05)

At the owner's request, every change must also pass this check before it's accepted:

1. **Does it solve a problem we have now**, in the current phase, rather than one we might have later?
2. **Can one maintainer understand and operate it** without needing specialist knowledge?
3. **Does it reuse what's already there?** That means the same database, the same Compose files, the
   same three languages and the same CI.
4. **Could we remove it easily** if it turns out not to be needed?

If the answer to any of these is no, the change needs an ADR that explains why it's worth the extra maintenance.
Things we can't verify yet, such as the Docker stack on a machine without Docker, are listed in the README
as known issues rather than worked around with extra tooling.
