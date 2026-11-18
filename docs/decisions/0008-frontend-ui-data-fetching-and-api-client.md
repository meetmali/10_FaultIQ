# 0008. Frontend UI kit, data fetching and generated API client

- **Status:** Accepted. Extends [0005](0005-frontend-toolchain.md). Amended by [0015](0015-mainstream-free-stack-resolutions.md).
- **Date:** 2026-11-05
- **Introduced in:** Phase 7. The API client generator is introduced in Phase 6, with the first real endpoints.

## Context

The frontend has to feel fast and look professional. It also has to stay consistent with an API
written in another language (C#), and handle loading, empty, error and stale states on every
screen (project plan, section 11).

## Decision

- **UI components: shadcn/ui** on top of Tailwind CSS v4. Components are copied into
  `src/components/ui/` and built on Radix primitives. This gives accessible dialogs, menus, tables
  and tabs with keyboard support, and the code is ours to adjust.
- **Server state: TanStack Query.** All API reads go through query hooks in `src/hooks/`.
  - Shared cache keys mean revisiting a screen loads instantly from cache, then refreshes in the background.
  - Retry, cancellation and `isStale` cover the plan's loading, error and stale-data states consistently.
  - Long-running diagnostic jobs are polled with `refetchInterval` until they reach a terminal state.
- **Routing: React Router**, with each screen loaded lazily so the first page load stays small.
- **API types and client are generated** from the .NET OpenAPI document
  (`/api/v1/openapi.json`) with `openapi-typescript`, plus a thin typed `fetch` wrapper.
  - Generated files live in `src/types/generated/` and are never edited by hand.
  - CI fails if regenerating changes them, so the TypeScript side can't drift from the C# contracts.

## Consequences

- There are a few more dependencies, but each one replaces code we would otherwise write and test ourselves.
- The hand-written `src/types/api.ts` from Phase 0 is replaced once generation is in place.
- The .NET API must keep its OpenAPI document accurate, so endpoints declare their response types.
