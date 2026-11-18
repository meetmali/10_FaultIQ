# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

FaultIQ is a solo project that will run across ten phases. Choices made early
(about data format, model splits, storage and so on) will be hard to reconstruct later.

## Decision

Keep short ADRs in `docs/decisions/`, one per significant decision, using `template.md`.

## Consequences

Writing each one takes a little time. Later phases, model cards and reviewers can
trace why the system looks the way it does.
