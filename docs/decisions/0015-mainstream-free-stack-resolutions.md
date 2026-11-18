# 0015. Mainstream, free choices for the remaining open questions

- **Status:** Accepted. Amends [0008](0008-frontend-ui-data-fetching-and-api-client.md) and
  [0012](0012-opentelemetry-observability.md).
- **Date:** 2026-11-05

## Context

Under [0014](0014-pro-bono-open-source-self-hostable.md), every component must be free and self-hostable.
To attract volunteers, the stack should also be as widely known as possible. Several choices were still
open after the review of the stack's downsides.

## Decision

The rule is to pick, for each layer, the most widely used free option that keeps future options open.

| Question | Decision | Why | Rejected |
|---|---|---|---|
| Frontend framework | **React + TypeScript** (unchanged) | The largest contributor pool and a free charting ecosystem | Blazor: smaller pool; good charts often need paid suites |
| UI components | **shadcn/ui + Tailwind** (unchanged) | Free (MIT), very widely used, and flexible because we own the component code | Fluent UI: smaller community outside Microsoft shops |
| Local orchestration | **Docker Compose** is the one supported way to run the stack | Everyone knows it, and it works the same for every language | Aspire: free, but needs the .NET SDK and is less familiar to Python and frontend contributors |
| Authentication | **ASP.NET Core Identity** (built in, local accounts) by default, plus **optional standard OIDC** login | No external service is needed to self-host. Organisations can connect Keycloak, Entra ID, Google or any OIDC provider through configuration | Requiring Entra ID or Keycloak: an extra paid or heavy dependency for small users |
| File storage | An **`IFileStore` / `FileStore` interface** with **local disk** as the default and an optional **S3-compatible** backend | Local disk is all a self-hoster needs. The S3 API is the de facto standard that most cloud and self-hosted object stores support | Tying the project to a single cloud provider's storage |
| Observability export | **OpenTelemetry → OTLP**. The optional `observability` Compose profile runs the free Grafana stack | Users can send telemetry to whatever monitoring they already have | Application Insights as a default: paid ingestion |
| Production inference | **Python** (unchanged from [0007](0007-hybrid-dotnet-api-python-pipeline.md)) | Self-hosters run containers, so there's no ".NET-only operations" constraint | ONNX in .NET: duplicate feature code would need parity tests |
| API | **ASP.NET Core** (unchanged) | Free (MIT), widely used, fast, and the owner's chosen language | |

## Consequences

- Running the whole stack needs only Docker. Building from source needs the .NET SDK, uv and Node.
- Auth is configured, not coded per provider. It's implemented in Phase 6, before any multi-user deployment.
- If a self-hoster's organisation standardises on a particular identity provider, storage or monitoring
  service, they connect it through configuration without code changes.
