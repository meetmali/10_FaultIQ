// API types, generated from the committed contracts (ADR 0008). Never edit the generated files:
// run `npm run generate:api` after the contracts change. JSON is snake_case (ADR 0007).
import type { components } from "./generated/api";

type Schemas = components["schemas"];

export type HealthResponse = Schemas["HealthResponse"];
export type EquipmentResponse = Schemas["EquipmentResponse"];
export type CreateEquipmentRequest = Schemas["CreateEquipmentRequest"];
export type UploadResponse = Schemas["UploadResponse"];
export type AnalysisResponse = Schemas["AnalysisResponse"];
export type CreateAnalysisRequest = Schemas["CreateAnalysisRequest"];
export type FaultEventResponse = Schemas["FaultEventResponse"];
export type EquipmentOverview = Schemas["EquipmentOverview"];
export type SiteResponse = Schemas["SiteResponse"];
export type FaultEventSummaryResponse = Schemas["FaultEventSummaryResponse"];
export type FaultLibraryResponse = Schemas["FaultLibraryResponse"];
export type LibraryFaultResponse = Schemas["LibraryFaultResponse"];
export type LibraryFault = Schemas["LibraryFault"];
export type LibrarySource = Schemas["LibrarySource"];
export type CitedText = Schemas["CitedText"];

/** Derived equipment status (ADR 0025). */
export type EquipmentStatus = "no_data" | "analysing" | "analysis_failed" | "fault" | "abnormal" | "normal";
export type ReviewStatus = "unreviewed" | "needs_review" | "confirmed" | "rejected";

export interface Paged<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

/** Upload formats with bundled models (ADR 0024). */
export type UploadFormat = "lbnl_simulated" | "lbnl_experimental";
export type PointSet = "all" | "basic";

/** RFC 9457 Problem Details, as returned for every API error, with a stable `code`. */
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code: string;
  errors?: Record<string, string[]>;
  trace_id?: string;
}

export type {
  Alternative,
  Check,
  Context,
  DiagnosticResult,
  Evidence,
  FaultEvent,
  ModelOutput,
  Source,
  Statement,
} from "./generated/diagnostic-result";

/** Downsampled chart series stored with each analysis (ADR 0009). Times are epoch milliseconds. */
export interface ChartSeries {
  version: number;
  overview: Record<string, { label: string; unit: string; t: number[]; v: number[] }>;
  events: Record<
    string,
    {
      start: number;
      end: number;
      signals: Record<
        string,
        { label: string; unit: string; t: number[]; observed: number[]; expected?: (number | null)[] }
      >;
    }
  >;
}
