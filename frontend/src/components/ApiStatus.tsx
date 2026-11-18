import type { HealthState } from "../hooks/useHealth";

// Status is shown with text and an icon as well as colour (project plan, section 11).
export function ApiStatus({ state }: { state: HealthState }) {
  if (state.kind === "loading") {
    return (
      <p role="status" className="text-slate-600">
        <span aria-hidden="true">…</span> Checking API…
      </p>
    );
  }

  if (state.kind === "error") {
    return (
      <p role="status" className="text-red-700">
        <span aria-hidden="true">✕</span> API unreachable: {state.message}
      </p>
    );
  }

  const { api_version, environment } = state.health;
  return (
    <p role="status" className="text-green-700">
      <span aria-hidden="true">✓</span> API online · version {api_version} · {environment}
    </p>
  );
}
