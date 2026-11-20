import { Search } from "lucide-react";
import { useDeferredValue, useId } from "react";
import { Link, useSearchParams } from "react-router";

import { Empty, QueryView } from "../components/QueryState";
import { Badge, Card, Field, inputClass } from "../components/ui";
import { usePreferences } from "../app/preferences";
import { IsometricRtu } from "../components/illustrations/IsometricRtu";
import { COMPONENT_LABEL, isComponent } from "../components/illustrations/components";
import { Meter } from "../components/visuals";
import { useLibrary } from "../hooks/queries";
import { formatPercent } from "../lib/format";

const EQUIPMENT = ["Refrigerant circuit", "Economizer and controls", "Sensors"];

export default function LibraryPage() {
  const id = useId();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const equipment = params.get("equipment") ?? "";
  const deferred = useDeferredValue(q); // type freely; the search catches up
  const { persona } = usePreferences();
  const library = useLibrary(deferred.trim(), equipment);
  const set = (k: string, v: string) =>
    setParams(
      (p) => {
        if (v) p.set(k, v);
        else p.delete(k);
        return p;
      },
      { replace: true },
    );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Fault Library</h1>
        <p className="text-sm text-muted">
          The faults FaultIQ can name, what they look like in the data, and what to check on site.
        </p>
      </div>

      <form role="search" className="grid gap-3 rounded-lg border border-line bg-surface p-4 sm:grid-cols-[1fr_16rem]" onSubmit={(e) => e.preventDefault()}>
        <Field label="Search by fault or symptom" htmlFor={`${id}-q`} hint="For example “discharge pressure”, “damper” or “filter”.">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute top-2 left-2.5 size-4 text-muted" />
            <input id={`${id}-q`} type="search" className={`${inputClass} w-full pl-8`} value={q} onChange={(e) => set("q", e.target.value)} />
          </div>
        </Field>
        <Field label="Equipment" htmlFor={`${id}-eq`}>
          <select id={`${id}-eq`} className={inputClass} value={equipment} onChange={(e) => set("equipment", e.target.value)}>
            <option value="">All equipment</option>
            {EQUIPMENT.map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </Field>
      </form>

      <QueryView query={library} loadingLabel="Loading the fault library…">
        {(lib) => (
          <>
            {lib.review_status !== "reviewed" && (
              <p className="rounded-md border border-warn-line bg-warn-soft px-3 py-2 text-sm text-warn">
                This library hasn't yet been reviewed by an HVAC professional. Measured results come from FaultIQ's
                own held-out tests; causes and checks cite published documents but are suggestions to verify.
              </p>
            )}
            <p className="text-sm text-muted" aria-live="polite">
              {lib.items.length} {lib.items.length === 1 ? "fault" : "faults"}
              {q || equipment ? " match" : ""}
            </p>
            {lib.items.length === 0 ? (
              <Empty>No faults match. Try a different word, or clear the equipment filter.</Empty>
            ) : (
              <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {lib.items.map((f) => persona === "operator" ? (
                  <li key={f.id}>
                    <Link to={`/library/${f.id}`} className="flex h-full flex-col rounded-2xl border border-line bg-surface p-4 shadow-sm hover:border-accent focus-visible:outline-2 focus-visible:outline-accent">
                      <IsometricRtu variant="card" state="fault" component={isComponent(f.component) ? f.component : null} title={`${f.plain_name}: ${isComponent(f.component) ? COMPONENT_LABEL[f.component] : f.equipment}`} />
                      <h2 className="mt-2 text-base font-semibold text-ink">{f.plain_name}</h2>
                      <p className="mt-1 text-sm text-ink-2">{f.plain_summary?.text}</p>
                      <div className="mt-auto pt-3"><Meter value={f.measured.performance.recall} label="How often FaultIQ spots it" /></div>
                    </Link>
                  </li>
                ) : (
                  <li key={f.id}>
                    <Card className="h-full">
                      <h2 className="text-base font-semibold">
                        <Link to={`/library/${f.id}`} className="text-accent hover:underline">{f.title}</Link>
                      </h2>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <Badge className="border-line bg-raised text-ink-2">{f.equipment}</Badge>
                        <Badge className="border-line bg-surface text-muted">{f.dataset_label}</Badge>
                      </div>
                      {f.measured.symptoms[0] && (
                        <p className="mt-2 text-sm text-ink-2">
                          Main symptom: <strong>{f.measured.symptoms[0].signal}</strong>
                        </p>
                      )}
                      <p className="mt-1 text-sm text-muted">
                        Found in {formatPercent(f.measured.performance.recall)} of held-out faulty hours
                      </p>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </QueryView>
    </div>
  );
}
