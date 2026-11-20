// How far a reading sits from normal (ADR 0026), shared by the schematic and the signature check.
import type { HourlyColumn } from "../types/api";
import type { Tone } from "./tone";

// Which hourly column says whether a sensor is behaving normally.
export const SIGNAL_BAND: Record<string, string> = {
  sat: "resid:sat",
  sa_flow: "resid:sa_flow",
  refg_suct_pres: "resid:refg_suct_pres",
  refg_disc_pres: "resid:refg_disc_pres",
  refg_disc_temp: "resid:refg_disc_temp",
  power_comp: "resid:power_comp",
  oa_damper_cmd: "resid:oa_damper_cmd",
  vav_sat_min: "resid:vav_sat_min",
  superheat: "med:superheat",
  subcooling: "med:subcooling",
  condensing_approach: "med:condensing_approach",
};

/** The sensor a model feature describes: resid:refg_disc_pres -> refg_disc_pres. */
export const featureSignal = (feature: string) => feature.split(":", 2)[1] ?? feature;

/** Inside the fault-free band is ok; outside by less than one band-width is warn; more is fault. */
export function deviationTone(value: number | null | undefined, col?: HourlyColumn): Tone {
  if (value === null || value === undefined || !col || col.normal_low == null || col.normal_high == null) return "idle";
  const lo = col.normal_low;
  const hi = col.normal_high;
  if (value >= lo && value <= hi) return "ok";
  const width = Math.max(hi - lo, 1e-6);
  const beyond = (value < lo ? lo - value : value - hi) / width;
  return beyond > 1 ? "fault" : "warn";
}

