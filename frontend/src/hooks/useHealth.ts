import { useEffect, useState } from "react";

import { getHealth } from "../services/api";
import type { HealthResponse } from "../types/api";

export type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthResponse }
  | { kind: "error"; message: string };

// Temporary hook for Phase 0. TanStack Query replaces it in Phase 7 (ADR 0008).
export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setState({ kind: "ok", health }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "error", message: err instanceof Error ? err.message : "Unknown error" });
      });
    return () => controller.abort();
  }, []);

  return state;
}
