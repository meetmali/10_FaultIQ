/* Generated from docs/contracts/diagnostic-result.schema.json. Do not edit by hand. Run npm run generate:api. */

export interface DiagnosticResult {
  dataset: string;
  diagnosis_version: string;
  events: FaultEvent[];
  hours_alarmed: number;
  /**
   * Hours with enough steady minutes to score
   */
  hours_scored: number;
  hours_total: number;
  /**
   * Whether an HVAC professional has reviewed the fault library's checks
   */
  library_review_status: string;
  period_end: string | null;
  period_start: string | null;
  pipeline_version: string;
  point_set: string;
  schema_version?: string;
  /**
   * Input file name
   */
  source: string;
  /**
   * Every source cited by a check in this result
   */
  sources: Source[];
  supported_faults: string[];
}
/**
 * Consecutive alarmed hours with the same answer.
 */
export interface FaultEvent {
  checks: Check[];
  context: Context;
  /**
   * End of the last hour (exclusive)
   */
  end: string;
  evidence: Evidence[];
  fault: string | null;
  fault_title: string | null;
  hours: number;
  id: string;
  kind: "fault" | "no_supported_fault" | "inconclusive" | "not_diagnosable";
  model: ModelOutput;
  start: string;
  statements: Statement[];
}
export interface Check {
  /**
   * Id of the Source this check is taken from
   */
  source: string;
  text: string;
}
export interface Context {
  /**
   * Steady minutes with that equipment running
   */
  diagnosable_minutes: number;
  dominant_mode: string | null;
  outdoor_air_high: number | null;
  outdoor_air_low: number | null;
  /**
   * Equipment the supported faults act on
   */
  running: string;
}
/**
 * One signal behind the answer, summarised over the event's diagnosable minutes.
 */
export interface Evidence {
  /**
   * Observed minus expected, in typical fault-free errors; residuals only
   */
  deviation?: number | null;
  /**
   * Normal-model expectation for the same conditions; residuals only
   */
  expected?: number | null;
  /**
   * Model feature, e.g. resid:refg_disc_pres
   */
  feature: string;
  /**
   * Event hours in which this signal was available
   */
  hours: number;
  id: string;
  kind: "residual" | "physics" | "rule";
  /**
   * 95th percentile, same basis
   */
  normal_high?: number | null;
  /**
   * 5th percentile on fault-free validation hours: of `deviation` for residuals, of `observed` otherwise
   */
  normal_low?: number | null;
  /**
   * Median over the event (share of minutes for rules)
   */
  observed: number;
  /**
   * Plain name, e.g. discharge pressure
   */
  signal: string;
  unit: string;
  /**
   * Diagnosis evidence: summed contribution toward the answer (log-odds). Detector evidence: median absolute deviation
   */
  weight: number;
}
export interface ModelOutput {
  /**
   * Fault name, or the answer kind when no fault is named
   */
  answer: string;
  /**
   * Median hourly probability of top_class
   */
  confidence: number | null;
  /**
   * Confidence needed to name a fault
   */
  cutoff: number | null;
  /**
   * Highest hourly detector score in the event
   */
  detector_score: number;
  detector_threshold: number;
  model_family: string;
  /**
   * Most likely class before the confidence cut-off
   */
  top_class: string | null;
  /**
   * Share of validation hours named as this fault that really were it
   */
  validation_precision: number | null;
}
export interface Statement {
  kind: "finding" | "measured" | "context" | "uncertainty" | "recommended";
  /**
   * @minItems 1
   */
  refs: [string, ...string[]];
  text: string;
}
/**
 * A published reference a recommended check rests on.
 */
export interface Source {
  citation: string;
  id: string;
  url?: string | null;
}
