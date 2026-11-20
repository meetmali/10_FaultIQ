// Turning results into the Operator's words (ADR 0026). Everything here is computed from stored
// fields; nothing is invented.
import type { FaultEvent } from "../types/api";

export type Likelihood = "Likely" | "Possible" | "Unclear" | "Not diagnosable";

/** Uncertainty in plain words, never hidden: named faults are Likely at 90%+, otherwise Possible. */
export function likelihood(event: Pick<FaultEvent, "kind"> & { model: { confidence?: number | null } }): Likelihood {
  if (event.kind === "not_diagnosable") return "Not diagnosable";
  if (event.kind !== "fault") return "Unclear";
  return (event.model.confidence ?? 0) >= 0.9 ? "Likely" : "Possible";
}

export function duration(hours: number): string {
  if (hours < 48) return `${hours} ${hours === 1 ? "hour" : "hours"}`;
  const days = Math.round(hours / 24);
  return `${days} days`;
}

/** The event that matters most for a unit: the longest named fault, else the longest event. */
export function mainEvent<T extends { kind: string; hours: number }>(events: T[]): T | undefined {
  const named = events.filter((e) => e.kind === "fault");
  const pool = named.length ? named : events;
  return pool.reduce<T | undefined>((best, e) => (!best || e.hours > best.hours ? e : best), undefined);
}

/** Hours of each named fault across a result, largest first. */
export function faultHours(events: { kind: string; fault?: string | null; hours: number }[]): [string, number][] {
  const totals = new Map<string, number>();
  for (const e of events) if (e.kind === "fault" && e.fault) totals.set(e.fault, (totals.get(e.fault) ?? 0) + e.hours);
  return [...totals.entries()].sort((a, b) => b[1] - a[1]);
}
