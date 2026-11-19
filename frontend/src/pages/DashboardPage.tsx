import { useId, useMemo } from "react";
import { Link, useSearchParams } from "react-router";

import { KindBadge, ReviewBadge, StatusBadge } from "../components/Badges";
import { ChartFigure, type ChartOption } from "../components/charts";
import { Empty, Freshness, QueryView } from "../components/QueryState";
import { Card, CardTitle, Field, inputClass, Stat } from "../components/ui";
import { UploadDialog } from "../components/UploadDialog";
import { useEventSummary, useFaultEvents, useFaultTitles, useHealth, useOverview, useSites } from "../hooks/queries";
import { formatConfidence, formatDataTime, formatDateTime, formatNumber, formatPercent } from "../lib/format";
import { faultTitle, KIND_LABEL, STATUS_LABEL } from "../lib/labels";
import type { EquipmentOverview } from "../types/api";

const STATUS_ORDER = ["fault", "abnormal", "analysing", "analysis_failed", "normal", "no_data"];

/** Filters live in the URL, so a filtered view can be bookmarked or shared. */
function useFilters() {
  const [params, setParams] = useSearchParams();
  const get = (k: string) => params.get(k) ?? "";
  const set = (k: string, v: string) =>
    setParams((p) => {
      if (v) p.set(k, v);
      else p.delete(k);
      return p;
    });
  return { site: get("site"), status: get("status"), from: get("from"), to: get("to"), set };
}

const toIso = (date: string, endOfDay = false) => (date ? `${date}T${endOfDay ? "23:59:59" : "00:00:00"}Z` : undefined);

export default function DashboardPage() {
  const id = useId();
  const f = useFilters();
  const titles = useFaultTitles();
  const demo = useHealth().data?.demo_mode ?? false;
  const sites = useSites();
  const overview = useOverview(f.site || undefined);
  const range = { site: f.site || undefined, from: toIso(f.from), to: toIso(f.to, true) };
  const events = useFaultEvents({ ...range, page_size: 10 });
  const summary = useEventSummary(range);
  const title = (fault?: string | null) => (fault ? (titles[fault] ?? faultTitle(fault)) : "No fault named");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-slate-600">Equipment status and recent fault events.</p>
        </div>
        {!demo && <UploadDialog equipment={overview.data?.items ?? []} />}
      </div>

      <form aria-label="Filters" className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-4" onSubmit={(e) => e.preventDefault()}>
        <Field label="Site" htmlFor={`${id}-site`}>
          <select id={`${id}-site`} className={inputClass} value={f.site} onChange={(e) => f.set("site", e.target.value)}>
            <option value="">All sites</option>
            {sites.data?.map((s) => (
              <option key={s.site} value={s.site}>
                {s.site} ({s.equipment})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Equipment status" htmlFor={`${id}-status`}>
          <select id={`${id}-status`} className={inputClass} value={f.status} onChange={(e) => f.set("status", e.target.value)}>
            <option value="">Any status</option>
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Events from" htmlFor={`${id}-from`}>
          <input id={`${id}-from`} type="date" className={inputClass} value={f.from} onChange={(e) => f.set("from", e.target.value)} />
        </Field>
        <Field label="Events to" htmlFor={`${id}-to`}>
          <input id={`${id}-to`} type="date" className={inputClass} value={f.to} onChange={(e) => f.set("to", e.target.value)} />
        </Field>
      </form>

      <QueryView query={overview} loadingLabel="Loading equipment…">
        {(data) => <EquipmentSection items={data.items} total={data.total} statusFilter={f.status} demo={demo} title={title} />}
      </QueryView>
      <Freshness query={overview} />

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3" aria-labelledby={`${id}-events`}>
          <CardTitle id={`${id}-events`} aside={<Freshness query={events} />}>
            Recent fault events
          </CardTitle>
          <QueryView query={events} loadingLabel="Loading events…">
            {(page) =>
              page.items.length === 0 ? (
                <Empty>No fault events in this range. Analyses with alarms will list them here.</Empty>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm [&_td]:px-2 [&_th]:px-2">
                    <caption className="sr-only">Most recent fault events, newest first</caption>
                    <thead className="text-xs text-slate-500">
                      <tr>
                        <th scope="col" className="py-2 font-medium">Started</th>
                        <th scope="col" className="font-medium">Result</th>
                        <th scope="col" className="font-medium">Fault</th>
                        <th scope="col" className="font-medium">Hours</th>
                        <th scope="col" className="font-medium">Confidence</th>
                        <th scope="col" className="font-medium">Review</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.items.map((e) => (
                        <tr key={e.id} className="border-t border-slate-100">
                          <td className="py-2 whitespace-nowrap">
                            <Link
                              className="text-sky-800 underline-offset-2 hover:underline"
                              to={`/equipment/${e.equipment_id}?analysis=${e.analysis_id}&event=${e.event_key}`}
                            >
                              {formatDataTime(e.starts_at)}
                            </Link>
                          </td>
                          <td><KindBadge kind={e.kind} /></td>
                          <td>{e.kind === "fault" ? title(e.fault) : "–"}</td>
                          <td className="tabular-nums">{e.hours}</td>
                          <td className="tabular-nums">{formatConfidence(e.confidence)}</td>
                          <td><ReviewBadge status={e.review_status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs text-slate-500">
                    Showing {page.items.length} of {formatNumber(page.total)} events.
                  </p>
                </div>
              )
            }
          </QueryView>
        </Card>

        <Card className="lg:col-span-2" aria-labelledby={`${id}-dist`}>
          <CardTitle id={`${id}-dist`}>Fault distribution</CardTitle>
          <QueryView query={summary} loadingLabel="Loading distribution…">
            {(s) => (s.items.length === 0 ? <Empty>No events to summarise yet.</Empty> : <Distribution summary={s.items} title={title} />)}
          </QueryView>
        </Card>
      </div>
    </div>
  );
}

function EquipmentSection({
  items,
  total,
  statusFilter,
  demo,
  title,
}: {
  items: EquipmentOverview[];
  total: number;
  statusFilter: string;
  demo: boolean;
  title: (f?: string | null) => string;
}) {
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of items) c[e.status] = (c[e.status] ?? 0) + 1;
    return c;
  }, [items]);
  const shown = statusFilter ? items.filter((e) => e.status === statusFilter) : items;
  const scored = items.reduce((a, e) => a + (e.hours_scored ?? 0), 0);
  const alarmed = items.reduce((a, e) => a + (e.hours_alarmed ?? 0), 0);

  if (total === 0) {
    return (
      <Empty>
        No equipment yet. {demo ? "This demo has no sample data loaded." : "Use “Analyse new data” to upload a CSV export and create a unit."}
      </Empty>
    );
  }

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Equipment" value={formatNumber(total)} sample={demo} />
        <Stat label="Fault detected" value={formatNumber(counts.fault ?? 0)} sample={demo} />
        <Stat label="Abnormal, unexplained" value={formatNumber(counts.abnormal ?? 0)} sample={demo} />
        <Stat label="Alarmed hours (latest analyses)" value={scored ? formatPercent(alarmed / scored) : "n/a"} sample={demo} />
      </dl>
      <Card aria-labelledby="equipment-heading">
        <CardTitle id="equipment-heading">Equipment overview</CardTitle>
        {shown.length === 0 ? (
          <Empty>No equipment with this status.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm [&_td]:px-2 [&_th]:px-2">
              <caption className="sr-only">Equipment with the status of its latest analysis</caption>
              <thead className="text-xs text-slate-500">
                <tr>
                  <th scope="col" className="py-2 font-medium">Unit</th>
                  <th scope="col" className="font-medium">Site</th>
                  <th scope="col" className="font-medium">Status</th>
                  <th scope="col" className="font-medium">Main fault</th>
                  <th scope="col" className="font-medium">Events</th>
                  <th scope="col" className="font-medium">Alarmed hours</th>
                  <th scope="col" className="font-medium">Latest analysis</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => (
                  <tr key={e.id} className="border-t border-slate-100">
                    <th scope="row" className="py-2 font-medium">
                      <Link to={`/equipment/${e.id}`} className="text-sky-800 underline-offset-2 hover:underline">
                        {e.name}
                      </Link>
                    </th>
                    <td>{e.site ?? "–"}</td>
                    <td><StatusBadge status={e.status} /></td>
                    <td>{e.top_fault ? title(e.top_fault) : "–"}</td>
                    <td className="tabular-nums">
                      {e.fault_events + e.other_events > 0 ? `${e.fault_events} named, ${e.other_events} other` : "–"}
                    </td>
                    <td className="tabular-nums">
                      {e.hours_scored ? `${formatNumber(e.hours_alarmed)} of ${formatNumber(e.hours_scored)}` : "–"}
                    </td>
                    <td className="whitespace-nowrap">{e.latest_analysis_at ? formatDateTime(e.latest_analysis_at) : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Distribution({
  summary,
  title,
}: {
  summary: { kind: string; fault?: string | null; events: number; hours: number }[];
  title: (f?: string | null) => string;
}) {
  const rows = summary.map((s) => ({ ...s, label: s.kind === "fault" ? title(s.fault) : KIND_LABEL[s.kind] ?? s.kind }));
  const option: ChartOption = useMemo(
    () => ({
      grid: { left: 8, right: 24, top: 8, bottom: 24, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: { type: "value", name: "hours", nameLocation: "middle", nameGap: 22 },
      yAxis: { type: "category", data: rows.map((r) => r.label).reverse(), axisLabel: { width: 150, overflow: "truncate" } },
      series: [{ type: "bar", data: rows.map((r) => r.hours).reverse(), itemStyle: { color: "#0369a1" } }],
    }),
    [rows],
  );
  return (
    <ChartFigure
      title="Event hours by result"
      description="Total hours in fault events, by named fault or result kind."
      option={option}
      height={Math.max(160, rows.length * 30)}
      downsampled={false}
      summary={[]}
      footer={
        <table className="w-full text-left text-xs [&_td]:px-2 [&_th]:px-2">
          <caption className="sr-only">Event hours by result</caption>
          <thead className="text-slate-500">
            <tr>
              <th scope="col" className="py-1 font-medium">Result</th>
              <th scope="col" className="font-medium">Events</th>
              <th scope="col" className="font-medium">Hours</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.kind}-${r.fault}`} className="border-t border-slate-100">
                <th scope="row" className="py-1 font-normal">{r.label}</th>
                <td className="tabular-nums">{r.events}</td>
                <td className="tabular-nums">{formatNumber(r.hours)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    />
  );
}
