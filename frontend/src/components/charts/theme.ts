import { unitLabel } from "../../lib/format";

// Event shading: the same hue as the event badges, light enough to see the lines through.
export const KIND_SHADE: Record<string, string> = {
  fault: "rgba(220, 38, 38, 0.12)",
  inconclusive: "rgba(217, 119, 6, 0.14)",
  no_supported_fault: "rgba(124, 58, 237, 0.12)",
  not_diagnosable: "rgba(100, 116, 139, 0.14)",
};

export const LINE_COLORS = ["#0369a1", "#b45309", "#047857", "#7c3aed", "#be123c"];

export const axisName = (unit: string) => unitLabel(unit) || undefined;
