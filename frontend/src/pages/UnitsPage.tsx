import { Link } from "react-router";

import { usePreferences } from "../app/preferences";
import { StatusBadge } from "../components/Badges";
import { IsometricRtu } from "../components/illustrations/IsometricRtu";
import { isComponent, unitState } from "../components/illustrations/components";
import { Empty, Freshness, QueryView } from "../components/QueryState";
import { tableClass } from "../components/ui";
import { useLibraryIndex, useOverview } from "../hooks/queries";
import { formatDateTime, formatNumber, formatPercent } from "../lib/format";
import { faultTitle } from "../lib/labels";

/** Every unit: picture cards for the Operator, a sortable-looking table for the Technician. */
export default function UnitsPage() {
  const { persona, site } = usePreferences();
  const overview = useOverview(site || undefined);
  const library = useLibraryIndex();
  const tech = persona === "technician";
  const name = (f?: string | null) => (f ? (tech ? library.get(f)?.title : library.get(f)?.plain_name) ?? faultTitle(f) : "No fault found");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Rooftop units</h1>
        <p className="text-sm text-muted">{site ? site : "All sites"} · status from each unit's latest analysis.</p>
      </div>
      <QueryView query={overview} loadingLabel="Loading units…">
        {(o) =>
          o.items.length === 0 ? (
            <Empty>No units yet.</Empty>
          ) : tech ? (
            <div className="overflow-x-auto rounded-2xl border border-line bg-surface p-4">
              <table className={tableClass}>
                <caption className="sr-only">Units with their latest analysis</caption>
                <thead>
                  <tr>
                    <th scope="col" className="py-2 font-medium">Unit</th>
                    <th scope="col" className="font-medium">Site</th>
                    <th scope="col" className="font-medium">Status</th>
                    <th scope="col" className="font-medium">Main fault</th>
                    <th scope="col" className="font-medium">Alarmed hours</th>
                    <th scope="col" className="font-medium">Analysed</th>
                  </tr>
                </thead>
                <tbody>
                  {o.items.map((u) => (
                    <tr key={u.id} className="border-t border-line">
                      <th scope="row" className="py-2 font-medium"><Link to={`/equipment/${u.id}`} className="text-accent hover:underline">{u.name}</Link></th>
                      <td>{u.site ?? "–"}</td>
                      <td><StatusBadge status={u.status} /></td>
                      <td>{u.top_fault ? name(u.top_fault) : "–"}</td>
                      <td className="tabular-nums">{u.hours_scored ? `${formatNumber(u.hours_alarmed)} of ${formatNumber(u.hours_scored)} (${formatPercent((u.hours_alarmed ?? 0) / u.hours_scored)})` : "–"}</td>
                      <td className="text-xs text-muted">{u.latest_analysis_at ? formatDateTime(u.latest_analysis_at) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {o.items.map((u) => {
                const comp = u.top_fault ? library.get(u.top_fault)?.component : null;
                return (
                  <li key={u.id}>
                    <Link to={`/equipment/${u.id}`} className="block h-full rounded-2xl border border-line bg-surface p-4 shadow-sm hover:border-accent focus-visible:outline-2 focus-visible:outline-accent">
                      <IsometricRtu variant="card" state={unitState(u.status)} component={isComponent(comp) ? comp : null} title={`${u.name}: ${u.status}`} />
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink">{u.name}</span>
                        <StatusBadge status={u.status} />
                      </div>
                      <p className="mt-1 text-sm text-ink-2">{u.status === "fault" ? name(u.top_fault) : u.status === "abnormal" ? "Unusual, cause unclear" : u.site ?? ""}</p>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )
        }
      </QueryView>
      <Freshness query={overview} />
    </div>
  );
}
