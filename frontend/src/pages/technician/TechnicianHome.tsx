import { useMemo } from "react";
import { Link } from "react-router";

import { usePreferences } from "../../app/preferences";
import { KindBadge, ReviewBadge, StatusBadge } from "../../components/Badges";
import { ChartFigure, type ChartOption } from "../../components/charts";
import { Empty, Freshness, QueryView } from "../../components/QueryState";
import { Card, CardTitle, Stat, tableClass } from "../../components/ui";
import { UploadDialog } from "../../components/UploadDialog";
import { useEventSummary, useFaultEvents, useFaultTitles, useHealth, useOverview } from "../../hooks/queries";
import { formatConfidence, formatDataTime, formatDateTime, formatNumber, formatPercent } from "../../lib/format";
import { faultTitle, KIND_LABEL } from "../../lib/labels";

export default function TechnicianHome() {
  const { site } = usePreferences();
  const titles = useFaultTitles();
  const demo = useHealth().data?.demo_mode ?? false;
  const overview = useOverview(site || undefined);
  // The 100 longest unreviewed named faults, then ranked by hours × confidence.
  const queue = useFaultEvents({ site: site || undefined, kind: "fault", review_status: "unreviewed", order: "hours", page_size: 100 });
  const summary = useEventSummary({ site: site || undefined });
  const confirmed = useFaultEvents({ site: site || undefined, review_status: "confirmed", page_size: 1 });
  const rejected = useFaultEvents({ site: site || undefined, review_status: "rejected", page_size: 1 });
  const needs = useFaultEvents({ site: site || undefined, review_status: "needs_review", page_size: 1 });
  const title = (f?: string | null) => (f ? (titles[f] ?? faultTitle(f)) : "–");
  const names = new Map(overview.data?.items.map((u) => [u.id, u.name]));

  // Work queue: unreviewed named faults, biggest and most certain first.
  const ranked = useMemo(
    () => [...(queue.data?.items ?? [])].sort((a, b) => b.hours * (b.confidence ?? 0) - a.hours * (a.confidence ?? 0)),
    [queue.data],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Work queue</h1>
          <p className="text-sm text-muted">Named faults waiting for a technician, ranked by duration × confidence.</p>
        </div>
        {!demo && <UploadDialog equipment={overview.data?.items ?? []} />}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" aria-labelledby="queue-heading">
          <CardTitle id="queue-heading" aside={<Freshness query={queue} />} sub={`${formatNumber(queue.data?.total)} unreviewed named faults`}>
            To investigate
          </CardTitle>
          <QueryView query={queue} loadingLabel="Loading the queue…">
            {() =>
              ranked.length === 0 ? (
                <Empty>Nothing waiting. Every named fault has been reviewed.</Empty>
              ) : (
                <ol className="divide-y divide-line">
                  {ranked.slice(0, 12).map((e, i) => (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
                      <span className="w-6 text-right text-sm font-semibold text-muted tabular-nums">{i + 1}</span>
                      <Link
                        to={`/equipment/${e.equipment_id}?analysis=${e.analysis_id}&event=${e.event_key}`}
                        className="min-w-48 flex-1 font-medium text-accent hover:underline"
                      >
                        {title(e.fault)}
                      </Link>
                      <span className="text-sm text-ink-2">{names.get(e.equipment_id) ?? "Unit"}</span>
                      <span className="text-sm text-muted tabular-nums">{e.hours} h · {formatConfidence(e.confidence)}</span>
                      <span className="text-xs text-muted">{formatDataTime(e.starts_at)}</span>
                    </li>
                  ))}
                </ol>
              )
            }
          </QueryView>
        </Card>

        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-3">
            <Stat label="Confirmed" value={formatNumber(confirmed.data?.total)} hint="future training labels" sample={demo} />
            <Stat label="Rejected" value={formatNumber(rejected.data?.total)} hint="model was wrong" sample={demo} />
            <Stat label="Needs review" value={formatNumber(needs.data?.total)} sample={demo} />
            <Stat
              label="Units with faults"
              value={formatNumber(overview.data?.items.filter((u) => u.status === "fault").length)}
              hint={`of ${formatNumber(overview.data?.total)}`}
              sample={demo}
            />
          </dl>
          <Card aria-labelledby="mix-heading">
            <CardTitle id="mix-heading">Fault mix</CardTitle>
            <QueryView query={summary}>
              {(s) => (s.items.length === 0 ? <Empty>No events yet.</Empty> : <Mix items={s.items} title={title} />)}
            </QueryView>
          </Card>
        </div>
      </div>

      <Card aria-labelledby="detect-heading">
        <CardTitle id="detect-heading" aside={<Freshness query={overview} />} sub="Latest analysis per unit: alarmed share of scored hours and named versus other events.">
          Detection health
        </CardTitle>
        <QueryView query={overview}>
          {(o) =>
            o.items.length === 0 ? (
              <Empty>No units yet. Upload an export to start.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <caption className="sr-only">Detection health per unit</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="py-2 font-medium">Unit</th>
                      <th scope="col" className="font-medium">Status</th>
                      <th scope="col" className="font-medium">Main fault</th>
                      <th scope="col" className="w-48 font-medium">Alarmed share</th>
                      <th scope="col" className="font-medium">Events</th>
                      <th scope="col" className="font-medium">Analysed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.items.map((u) => {
                      const share = u.hours_scored ? (u.hours_alarmed ?? 0) / u.hours_scored : null;
                      return (
                        <tr key={u.id} className="border-t border-line">
                          <th scope="row" className="py-2 font-medium">
                            <Link to={`/equipment/${u.id}`} className="text-accent hover:underline">{u.name}</Link>
                            <span className="block text-xs font-normal text-muted">{u.site ?? ""}</span>
                          </th>
                          <td><StatusBadge status={u.status} /></td>
                          <td className="text-ink-2">{title(u.top_fault)}</td>
                          <td>
                            {share === null ? "–" : (
                              <span className="flex items-center gap-2">
                                <span className="h-1.5 w-24 rounded-full bg-raised" aria-hidden="true">
                                  <span className="block h-1.5 rounded-full bg-fault" style={{ width: `${Math.max(2, share * 100)}%` }} />
                                </span>
                                <span className="tabular-nums">{formatPercent(share)}</span>
                              </span>
                            )}
                          </td>
                          <td className="tabular-nums">{u.fault_events + u.other_events ? `${u.fault_events} / ${u.other_events}` : "–"}</td>
                          <td className="text-xs whitespace-nowrap text-muted">{u.latest_analysis_at ? formatDateTime(u.latest_analysis_at) : "–"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryView>
      </Card>

      <RecentEvents names={names} title={title} />
    </div>
  );
}

function Mix({ items, title }: { items: { kind: string; fault?: string | null; events: number; hours: number }[]; title: (f?: string | null) => string }) {
  const rows = items.map((s) => ({ ...s, label: s.kind === "fault" ? title(s.fault) : KIND_LABEL[s.kind] ?? s.kind }));
  const option: ChartOption = useMemo(
    () => ({
      grid: { left: 8, right: 20, top: 8, bottom: 24, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: { type: "value", name: "hours", nameLocation: "middle", nameGap: 22 },
      yAxis: { type: "category", data: rows.map((r) => r.label).reverse(), axisLabel: { width: 130, overflow: "truncate" } },
      series: [{ type: "bar", data: rows.map((r) => r.hours).reverse(), itemStyle: { color: "#0284c7", borderRadius: 3 } }],
    }),
    [rows],
  );
  return (
    <ChartFigure
      title="Event hours by result"
      description="Hours in fault events, by named fault or result kind."
      option={option}
      height={Math.max(150, rows.length * 26)}
      downsampled={false}
      summary={[]}
      footer={
        <details className="text-xs text-ink-2">
          <summary className="cursor-pointer text-accent">Table</summary>
          <table className={tableClass}>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.kind}-${r.fault}`} className="border-t border-line">
                  <th scope="row" className="py-1 font-normal">{r.label}</th>
                  <td className="tabular-nums">{r.events} events</td>
                  <td className="tabular-nums">{formatNumber(r.hours)} h</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      }
    />
  );
}

function RecentEvents({ names, title }: { names: Map<string, string>; title: (f?: string | null) => string }) {
  const { site } = usePreferences();
  const events = useFaultEvents({ site: site || undefined, page_size: 10 });
  return (
    <Card aria-labelledby="recent-heading">
      <CardTitle id="recent-heading" aside={<Freshness query={events} />}>Latest events</CardTitle>
      <QueryView query={events}>
        {(p) =>
          p.items.length === 0 ? (
            <Empty>No events yet.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <caption className="sr-only">Latest fault events across units</caption>
                <thead>
                  <tr>
                    <th scope="col" className="py-2 font-medium">Started</th>
                    <th scope="col" className="font-medium">Unit</th>
                    <th scope="col" className="font-medium">Result</th>
                    <th scope="col" className="font-medium">Fault</th>
                    <th scope="col" className="font-medium">Hours</th>
                    <th scope="col" className="font-medium">Confidence</th>
                    <th scope="col" className="font-medium">Review</th>
                  </tr>
                </thead>
                <tbody>
                  {p.items.map((e) => (
                    <tr key={e.id} className="border-t border-line">
                      <td className="py-2 whitespace-nowrap">
                        <Link className="text-accent hover:underline" to={`/equipment/${e.equipment_id}?analysis=${e.analysis_id}&event=${e.event_key}`}>
                          {formatDataTime(e.starts_at)}
                        </Link>
                      </td>
                      <td>{names.get(e.equipment_id) ?? "–"}</td>
                      <td><KindBadge kind={e.kind} /></td>
                      <td>{e.kind === "fault" ? title(e.fault) : "–"}</td>
                      <td className="tabular-nums">{e.hours}</td>
                      <td className="tabular-nums">{e.kind === "not_diagnosable" ? "–" : formatConfidence(e.confidence)}</td>
                      <td><ReviewBadge status={e.review_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </QueryView>
    </Card>
  );
}
