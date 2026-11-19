import { Search } from "lucide-react";
import { useDeferredValue, useId } from "react";
import { Link, useSearchParams } from "react-router";

import { Empty, QueryView } from "../components/QueryState";
import { Badge, Card, Field, inputClass } from "../components/ui";
import { useLibrary } from "../hooks/queries";
import { formatPercent } from "../lib/format";

const EQUIPMENT = ["Refrigerant circuit", "Economizer and controls", "Sensors"];

export default function LibraryPage() {
  const id = useId();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const equipment = params.get("equipment") ?? "";
  const deferred = useDeferredValue(q); // type freely; the search catches up
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
        <p className="text-sm text-slate-600">
          The faults FaultIQ can name, what they look like in the data, and what to check on site.
        </p>
      </div>

      <form role="search" className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-[1fr_16rem]" onSubmit={(e) => e.preventDefault()}>
        <Field label="Search by fault or symptom" htmlFor={`${id}-q`} hint="For example “discharge pressure”, “damper” or “filter”.">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute top-2 left-2.5 size-4 text-slate-400" />
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
              <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                This library hasn't yet been reviewed by an HVAC professional. Measured results come from FaultIQ's
                own held-out tests; causes and checks cite published documents but are suggestions to verify.
              </p>
            )}
            <p className="text-sm text-slate-600" aria-live="polite">
              {lib.items.length} {lib.items.length === 1 ? "fault" : "faults"}
              {q || equipment ? " match" : ""}
            </p>
            {lib.items.length === 0 ? (
              <Empty>No faults match. Try a different word, or clear the equipment filter.</Empty>
            ) : (
              <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {lib.items.map((f) => (
                  <li key={f.id}>
                    <Card className="h-full">
                      <h2 className="text-base font-semibold">
                        <Link to={`/library/${f.id}`} className="text-sky-800 hover:underline">{f.title}</Link>
                      </h2>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <Badge className="border-slate-300 bg-slate-50 text-slate-700">{f.equipment}</Badge>
                        <Badge className="border-slate-300 bg-white text-slate-600">{f.dataset_label}</Badge>
                      </div>
                      {f.measured.symptoms[0] && (
                        <p className="mt-2 text-sm text-slate-700">
                          Main symptom: <strong>{f.measured.symptoms[0].signal}</strong>
                        </p>
                      )}
                      <p className="mt-1 text-sm text-slate-600">
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
