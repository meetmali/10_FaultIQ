// The parts of a rooftop unit a fault can point at (ADR 0026). The fault library's `component`
// field uses these names, so a new fault only needs a library entry to light up the right part.

export type Component =
  | "condenser"
  | "evaporator"
  | "liquid_line"
  | "suction_line"
  | "refrigerant_circuit"
  | "oa_damper"
  | "controller"
  | "sat_sensor";

export type UnitState = "off" | "normal" | "fault" | "unclear" | "analysing";

export const COMPONENT_LABEL: Record<Component, string> = {
  condenser: "Outdoor (condenser) coil",
  evaporator: "Indoor coil and filter",
  liquid_line: "Liquid line",
  suction_line: "Suction line",
  refrigerant_circuit: "Refrigerant circuit",
  oa_damper: "Outdoor-air damper",
  controller: "Economizer controller",
  sat_sensor: "Supply-air sensor",
};

export const isComponent = (c: string | null | undefined): c is Component =>
  c !== null && c !== undefined && c in COMPONENT_LABEL;

/** The illustration state for an equipment status from the API. */
export function unitState(status: string): UnitState {
  switch (status) {
    case "fault":
      return "fault";
    case "abnormal":
      return "unclear";
    case "analysing":
      return "analysing";
    case "normal":
      return "normal";
    default:
      return "off";
  }
}
