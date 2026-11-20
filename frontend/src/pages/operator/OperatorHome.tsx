import { AlertTriangle, ArrowRight, CheckCircle2, CircleHelp, ClipboardCheck, Wrench } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router";

import { usePreferences } from "../../app/preferences";
import { StatusBadge } from "../../components/Badges";
import { IsometricRtu } from "../../components/illustrations/IsometricRtu";
import { COMPONENT_LABEL, isComponent, unitState } from "../../components/illustrations/components";
import { Empty, Freshness, QueryView } from "../../components/QueryState";
import { Badge, Card, CardTitle } from "../../components/ui";
import { HealthRing, IssueCalendar, type DayCell } from "../../components/visuals";
import { useDailyFaultHours, useFaultEvents, useHealth, useLibraryIndex, useOverview } from "../../hooks/queries";
import { formatNumber, formatPercent } from "../../lib/format";
import { faultTitle } from "../../lib/labels";
import { duration, likelihood } from "../../lib/unit";
import { TONE } from "../../lib/tone";
import type { EquipmentOverview, LibraryFault } from "../../types/api";

const NEEDS_ATTENTION = new Set(["fault", "abnormal"]);

export default function OperatorHome() {
  const { site } = usePreferences();
  const overview = useOverview(site || undefined);
  const library = useLibraryIndex();
  const demo = useHealth().data?.demo_mode ?? false;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">How are your rooftop units?</h1>
        <p className="text-sm text-muted">Faults FaultIQ found in your latest analyses, and what to do about them.</p>
      </div>
      <QueryView query={overview} loadingLabel="Checking your units…">
        {(data) =>
          data.total === 0 ? (
            <Empty>No units analysed yet. Switch to the Technician view to upload data, or ask your technician to.</Empty>
          ) : (
            <Overview units={data.items} library={library} demo={demo} />
          )
        }
      </QueryView>
      <Freshness query={overview} />
    </div>
  );
}

function Overview({ units, library, demo }: { units: EquipmentOverview[]; library: Map<string, LibraryFault>; demo: boolean }) {
  const { site } = usePreferences();
  const count = (s: string[]) => units.filter((u) => s.includes(u.status)).length;
  const attention = units
    .filter((u) => NEEDS_ATTENTION.has(u.status))
    .sort((a, b) => (b.status === "fault" ? 1 : 0) - (a.status === "fault" ? 1 : 0) || (b.hours_alarmed ?? 0) - (a.hours_alarmed ?? 0));
  const plain = (f?: string | null) => (f ? (library.get(f)?.plain_name ?? faultTitle(f)) : "");

  // Headlines are counted from the data, never written by hand.
  const headlines = useMemo(() => {
    const byFault = new Map<string, number>();
    for (const u of units) if (u.status === "fault" && u.top_fault) byFault.set(u.top_fault, (byFault.get(u.top_fault) ?? 0) + 1);
    const lines: { text: string; tone: "fault" | "warn" | "ok" }[] = [];
    const need = units.filter((u) => NEEDS_ATTENTION.has(u.status)).length;
    lines.push(need
      ? { text: `${need} of ${units.length} rooftop units need attention.`, tone: "fault" }
      : { text: `All ${units.length} rooftop units look healthy.`, tone: "ok" });
    for (const [f, n] of [...byFault.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2)) {
      lines.push({ text: `${plain(f)} on ${n} ${n === 1 ? "unit" : "units"}.`, tone: "fault" });
    }
    const unclear = units.filter((u) => u.status === "abnormal").length;
    if (unclear) lines.push({ text: `${unclear} ${unclear === 1 ? "unit behaves" : "units behave"} unusually in a way FaultIQ can't name yet.`, tone: "warn" });
    const healthy = units.filter((u) => u.status === "normal").length;
    if (need && healthy) lines.push({ text: `${healthy} ${healthy === 1 ? "unit is" : "units are"} running normally.`, tone: "ok" });
    return lines;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [units, library]);

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2" aria-labelledby="health-heading">
          <CardTitle id="health-heading" aside={demo ? <Badge className={TONE.warn}>Sample data</Badge> : undefined}>Fleet health</CardTitle>
          <HealthRing
            caption="Rooftop units by status"
            centre={String(units.length)}
            slices={[
              { label: "Fault found", value: count(["fault"]), tone: "fault" },
              { label: "Unusual, unclear cause", value: count(["abnormal"]), tone: "warn" },
              { label: "Healthy", value: count(["normal"]), tone: "ok" },
              { label: "Analysing or no data", value: count(["analysing", "no_data", "analysis_failed"]), tone: "idle" },
            ]}
          />
        </Card>
        <Card className="lg:col-span-3" aria-labelledby="news-heading">
          <CardTitle id="news-heading">What's going on</CardTitle>
          <ul className="space-y-3">
            {headlines.map((h) => (
              <li key={h.text} className="flex items-start gap-3 text-base text-ink">
                {h.tone === "ok" ? (
                  <CheckCircle2 aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ok" />
                ) : h.tone === "warn" ? (
                  <CircleHelp aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-warn" />
                ) : (
                  <AlertTriangle aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-fault" />
                )}
                {h.text}
              </li>
            ))}
          </ul>
          <NextSteps />
        </Card>
      </div>

      {attention.length > 0 && (
        <section aria-labelledby="attention-heading" className="space-y-3">
          <h2 id="attention-heading" className="text-lg font-semibold text-ink">Needs attention</h2>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {attention.slice(0, 8).map((u) => (
              <li key={u.id}>
                <AttentionCard unit={u} fault={u.top_fault ? library.get(u.top_fault) : undefined} plainName={plain(u.top_fault)} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <Card aria-labelledby="fleet-heading">
        <CardTitle id="fleet-heading" sub="Every unit at a glance. Choose one to see what's wrong.">Your fleet</CardTitle>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {units.map((u) => {
            const comp = u.top_fault ? library.get(u.top_fault)?.component : null;
            return (
              <li key={u.id}>
                <Link to={`/equipment/${u.id}`} className="block rounded-xl border border-line p-2 text-center hover:border-accent focus-visible:outline-2 focus-visible:outline-accent">
                  <IsometricRtu variant="thumb" state={unitState(u.status)} component={isComponent(comp) ? comp : null} title={`${u.name}: ${u.status}`} />
                  <span className="mt-1 block text-sm font-medium text-ink">{u.name}</span>
                  <span className="mt-1 flex justify-center"><StatusBadge status={u.status} /></span>
                </Link>
              </li>
            );
          })}
        </ul>
      </Card>

      <Calendar site={site} />
    </div>
  );
}

function AttentionCard({ unit, fault, plainName }: { unit: EquipmentOverview; fault?: LibraryFault; plainName: string }) {
  const events = useFaultEvents({ analysis_id: unit.latest_analysis_id ?? undefined, kind: "fault", page_size: 100 });
  const main = events.data?.items.filter((e) => e.fault === unit.top_fault).sort((a, b) => b.hours - a.hours)[0];
  const hours = events.data?.items.filter((e) => e.fault === unit.top_fault).reduce((a, e) => a + e.hours, 0) ?? 0;
  const comp = fault?.component;
  const like = unit.status === "fault" && main ? likelihood({ kind: "fault", model: { confidence: main.confidence } }) : "Unclear";
  return (
    <Link
      to={`/equipment/${unit.id}`}
      className="flex h-full flex-col rounded-2xl border border-line bg-surface p-4 shadow-sm transition hover:border-accent focus-visible:outline-2 focus-visible:outline-accent"
    >
      <IsometricRtu
        variant="card"
        state={unitState(unit.status)}
        component={isComponent(comp) ? comp : null}
        title={`${unit.name}. ${unit.status === "fault" ? `Problem area: ${isComponent(comp) ? COMPONENT_LABEL[comp] : plainName}` : "Unusual behaviour"}.`}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="font-semibold text-ink">{unit.name}</span>
        <Badge className={like === "Likely" ? TONE.fault : TONE.warn}>{like}</Badge>
      </div>
      <p className="mt-1 text-sm text-ink-2">{unit.status === "fault" ? plainName : "Unusual behaviour, cause unclear"}</p>
      <p className="mt-auto pt-2 text-xs text-muted">
        {hours > 0 ? `Seen for ${duration(hours)}` : `${formatNumber(unit.hours_alarmed)} unusual hours`} ·{" "}
        {unit.hours_scored ? `${formatPercent((unit.hours_alarmed ?? 0) / unit.hours_scored)} of running time` : ""}
      </p>
      <span className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-accent">
        What to do <ArrowRight aria-hidden="true" className="size-4" />
      </span>
    </Link>
  );
}

function NextSteps() {
  const { site } = usePreferences();
  const waiting = useFaultEvents({ site: site || undefined, kind: "fault", review_status: "unreviewed", page_size: 1 });
  const confirmed = useFaultEvents({ site: site || undefined, review_status: "confirmed", page_size: 1 });
  return (
    <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4">
      <div className="grid grid-cols-[2rem_1fr] items-center gap-x-3">
        <dt className="col-start-2 row-start-2 text-xs text-muted">findings waiting for a technician</dt>
        <dd className="col-start-1 row-span-2 row-start-1"><Wrench aria-hidden="true" className="size-8 rounded-lg bg-warn-soft p-1.5 text-warn" /></dd>
        <dd className="col-start-2 row-start-1 text-xl font-semibold text-ink tabular-nums">{waiting.data?.total ?? "…"}</dd>
      </div>
      <div className="grid grid-cols-[2rem_1fr] items-center gap-x-3">
        <dt className="col-start-2 row-start-2 text-xs text-muted">confirmed on site</dt>
        <dd className="col-start-1 row-span-2 row-start-1"><ClipboardCheck aria-hidden="true" className="size-8 rounded-lg bg-ok-soft p-1.5 text-ok" /></dd>
        <dd className="col-start-2 row-start-1 text-xl font-semibold text-ink tabular-nums">{confirmed.data?.total ?? "…"}</dd>
      </div>
    </dl>
  );
}

function Calendar({ site }: { site: string }) {
  const daily = useDailyFaultHours({ site: site || undefined });
  // One calendar per site with data: sites can be years apart, so one shared grid would be empty.
  const bySite = useMemo(() => {
    const cells = new Map<string, DayCell>();
    for (const d of daily.data ?? []) {
      const c = cells.get(d.date) ?? { date: d.date, faultHours: 0, otherHours: 0 };
      if (d.kind === "fault") c.faultHours += d.hours;
      else c.otherHours += d.hours;
      cells.set(d.date, c);
    }
    const sorted = [...cells.values()].sort((a, b) => a.date.localeCompare(b.date));
    // Split into runs separated by more than 120 days (different sites or seasons).
    const runs: DayCell[][] = [];
    for (const c of sorted) {
      const prev = runs[runs.length - 1]?.at(-1);
      if (!prev || Date.parse(c.date) - Date.parse(prev.date) > 120 * 86_400_000) runs.push([c]);
      else runs[runs.length - 1]!.push(c);
    }
    return runs;
  }, [daily.data]);

  return (
    <Card aria-labelledby="calendar-heading">
      <CardTitle id="calendar-heading" sub="Each square is a day of data. Darker red means more unit-hours with a named fault.">
        Is it getting better or worse?
      </CardTitle>
      {bySite.length === 0 ? (
        <Empty>No fault days yet.</Empty>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {bySite.map((run) => (
            <IssueCalendar key={run[0]!.date} days={run} title={`${run[0]!.date} to ${run.at(-1)!.date}`} />
          ))}
        </div>
      )}
    </Card>
  );
}
