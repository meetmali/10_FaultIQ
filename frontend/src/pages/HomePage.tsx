import { usePreferences } from "../app/preferences";
import OperatorHome from "./operator/OperatorHome";
import TechnicianHome from "./technician/TechnicianHome";

/** One route, two lenses on the same data (ADR 0026). */
export default function HomePage() {
  return usePreferences().persona === "technician" ? <TechnicianHome /> : <OperatorHome />;
}
