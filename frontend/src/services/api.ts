import type { HealthResponse } from "../types/api";

// Same-origin API: Vite proxies /api in development, and Caddy proxies it in production.
const API_V1 = "/api/v1";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const resp = await fetch(`${API_V1}/health`, { signal });
  if (!resp.ok) throw new Error(`Health check failed (HTTP ${resp.status})`);
  return (await resp.json()) as HealthResponse;
}
