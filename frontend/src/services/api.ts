import type {
  AnalysisResponse,
  ChartSeries,
  DiagnosticResult,
  EquipmentResponse,
  FaultEventResponse,
  HealthResponse,
  Paged,
  PointSet,
  ProblemDetails,
  UploadFormat,
  UploadResponse,
} from "../types/api";

// Same-origin API: Vite proxies /api in development, and Caddy proxies it in production.
const API_V1 = "/api/v1";

/** A failed API call. `code` is the problem's stable code, for branching (ADR 0007). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly problem?: ProblemDetails;

  constructor(status: number, problem?: ProblemDetails) {
    super(problem?.detail ?? `Request failed (HTTP ${status})`);
    this.name = "ApiError";
    this.status = status;
    this.code = problem?.code ?? `http_${status}`;
    this.problem = problem;
  }
}

type Query = Record<string, string | number | undefined | null>;

function url(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return `${API_V1}${path}${qs ? `?${qs}` : ""}`;
}

async function request<T>(path: string, init?: RequestInit & { query?: Query }): Promise<T> {
  const resp = await fetch(url(path, init?.query), init);
  if (!resp.ok) {
    const isProblem = resp.headers.get("content-type")?.includes("problem+json");
    throw new ApiError(resp.status, isProblem ? ((await resp.json()) as ProblemDetails) : undefined);
  }
  return (await resp.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const getHealth = (signal?: AbortSignal) => request<HealthResponse>("/health", { signal });

export const listEquipment = (query?: { site?: string; page?: number; page_size?: number }) =>
  request<Paged<EquipmentResponse>>("/equipment", { query });

export const createEquipment = (name: string, site?: string) =>
  request<EquipmentResponse>("/equipment", json({ name, site }));

/** Uploads a CSV export. The server stores it under its own ID and returns the SHA-256. */
export function uploadFile(file: File, equipmentId: string, format: UploadFormat) {
  const form = new FormData();
  form.set("file", file);
  form.set("equipment_id", equipmentId);
  form.set("format", format);
  return request<UploadResponse>("/uploads", { method: "POST", body: form });
}

/** Queues an analysis. Poll `getAnalysis` until status is succeeded or failed. */
export const startAnalysis = (uploadId: string, pointSet: PointSet = "all") =>
  request<AnalysisResponse>("/analyses", json({ upload_id: uploadId, point_set: pointSet }));

export const getAnalysis = (id: string, signal?: AbortSignal) =>
  request<AnalysisResponse>(`/analyses/${encodeURIComponent(id)}`, { signal });

export const listAnalyses = (query?: {
  status?: string;
  equipment_id?: string;
  page?: number;
  page_size?: number;
}) => request<Paged<AnalysisResponse>>("/analyses", { query });

export const getAnalysisResult = (id: string, signal?: AbortSignal) =>
  request<DiagnosticResult>(`/analyses/${encodeURIComponent(id)}/result`, { signal });

export const getAnalysisSeries = (id: string, signal?: AbortSignal) =>
  request<ChartSeries>(`/analyses/${encodeURIComponent(id)}/series`, { signal });

export const listFaultEvents = (query?: {
  equipment_id?: string;
  analysis_id?: string;
  kind?: string;
  fault?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}) => request<Paged<FaultEventResponse>>("/fault-events", { query });
