# 0005. React, TypeScript, Vite, Tailwind, npm, Node 26 LTS

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

The project plan specifies React and TypeScript, Plotly for charts, and either Tailwind or one
consistent component library.

## Decision

- **Vite** for development and builds, **React 19** and **TypeScript** in strict mode.
- **Tailwind CSS v4** for styling. Reusable components live in `src/components/`.
- ~~**Plotly** for charts.~~ Superseded by [0009](0009-echarts-and-precomputed-downsampled-series.md), which uses Apache ECharts.
- **npm**, with an exact-pinned `package-lock.json`.
- **Node 26 (Active LTS as of November 2026).** Pinned in `.nvmrc`, and the container
  uses `node:26.13.0-alpine`. `engines` allows `>=24`.
- **Vitest** and **React Testing Library** for unit and component tests. **Playwright** for end-to-end
  tests, added in Phase 7 together with the first real user journey.

## Consequences

Charting is decided in [0009](0009-echarts-and-precomputed-downsampled-series.md). UI kit, data fetching and the API client are decided in [0008](0008-frontend-ui-data-fetching-and-api-client.md).
