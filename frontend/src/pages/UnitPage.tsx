import { usePreferences } from "../app/preferences";
import OperatorUnit from "./operator/OperatorUnit";
import TechnicianWorkbench from "./technician/TechnicianWorkbench";

/** The same unit and event, through either lens (ADR 0026). Switching keeps the URL. */
export default function UnitPage() {
  return usePreferences().persona === "technician" ? <TechnicianWorkbench /> : <OperatorUnit />;
}
