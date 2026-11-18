import { ApiStatus } from "../components/ApiStatus";
import { DemoBanner } from "../components/DemoBanner";
import { useHealth } from "../hooks/useHealth";

// Phase 0 shell. The three MVP screens (project plan, section 11) arrive in Phase 7.
const PLANNED_SCREENS = [
  { name: "Dashboard", purpose: "Equipment status, fault summaries, recent events" },
  { name: "Fault Diagnostics", purpose: "One-unit investigation with sensor evidence" },
  { name: "Fault Library", purpose: "Searchable fault reference and diagnostic checks" },
];

export function App() {
  const health = useHealth();
  const demoMode = health.kind === "ok" && health.health.demo_mode;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {demoMode && <DemoBanner />}
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">FaultIQ</h1>
        <p className="text-sm text-slate-600">HVAC fault detection &amp; diagnostics · RTU MVP</p>
      </header>
      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        <section aria-labelledby="system-status">
          <h2 id="system-status" className="mb-2 font-medium">
            System status
          </h2>
          <ApiStatus state={health} />
        </section>
        <section aria-labelledby="planned-screens">
          <h2 id="planned-screens" className="mb-2 font-medium">
            Planned screens <span className="text-sm font-normal text-slate-500">(not built yet)</span>
          </h2>
          <ul className="space-y-2">
            {PLANNED_SCREENS.map((s) => (
              <li key={s.name} className="rounded border border-slate-200 bg-white px-4 py-3">
                <span className="font-medium">{s.name}</span>
                <span className="text-slate-600">: {s.purpose}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <footer className="mx-auto max-w-3xl px-6 pb-8 text-sm text-slate-600">
        <p>
          <strong>Decision support only.</strong> FaultIQ doesn't control equipment and is not a
          substitute for a qualified HVAC technician. Model results are not confirmed root causes.
        </p>
        <p className="mt-1">Free and open source under the MIT License.</p>
      </footer>
    </div>
  );
}
