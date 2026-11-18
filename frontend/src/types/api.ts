// Mirrors the .NET API contracts (api/src/FaultIQ.Api). JSON is snake_case (ADR 0007).

export interface HealthResponse {
  status: "ok";
  service: string;
  api_version: string;
  environment: string;
  demo_mode: boolean;
  timestamp: string;
}

/** RFC 9457 Problem Details, as returned for every API error. */
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  code: string;
}
