// Technician workbench panels (ADR 0026). Each answers one diagnostic question; none plots a
// signal just because it exists.
import { Check, ChevronLeft, ChevronRight, HelpCircle, X } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Link } from "react-router";

import { KindBadge, ReviewBadge } from "../../components/Badges";
import { CutawaySchematic, type Reading } from "../../components/illustrations/CutawaySchematic";
import { COMPONENT_LABEL, isComponent } from "../../components/illustrations/components";
import { Button, Card, CardTitle } from "../../components/ui";
import { cn } from "../../lib/cn";
import { formatConfidence, formatDataTime, formatValue } from "../../lib/format";
import { KIND_LABEL } from "../../lib/labels";
import { KIND_TONE, TONE_VAR, type Tone } from "../../lib/tone";
import { deviationTone, featureSignal, SIGNAL_BAND } from "../../lib/deviation";
import type { DiagnosticResult, FaultEvent, FaultEventResponse, HourlyColumn, HourlyTable, LibraryFault } from "../../types/api";

const median = (xs: number[]) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
};

function eventHours(hourly: HourlyTable, event: FaultEvent): number[] {
  const a = Date.parse(event.start);
  const b = Date.parse(event.end);
  return hourly.t.flatMap((t, i) => (t >= a && t < b ? [i] : []));
}

const MODE_COLOR: Record<string, string> = {
  off: "var(--idle)",
  fan_only: "#94a3b8",
  economizer: "#10b981",
  cooling: "#0284c7",
  economizer_cooling: "#06b6d4",
  heating: "#f97316",
  unknown: "var(--raised)",
};
const MODE_LABEL: Record<string, string> = {
  off: "Off",
  fan_only: "Fan only",
  economizer: "Free cooling",
  cooling: "Mechanical cooling",
  economizer_cooling: "Free + mechanical",
  heating: "Heating",
  unknown: "Unknown",
};

/** "What was every sensor doing at this moment?" The schematic at one hour, scrubbable. */
export function SchematicScrubber({
  hourly,
  result,
  selected,
  library,
}: {
  hourly: HourlyTable;
  result: DiagnosticResult;
  selected?: FaultEvent;
  library: Map<string, LibraryFault>;
}) {
  const id = useId();
  const first = selected ? Math.max(0, hourly.t.findIndex((t) => t >= Date.parse(selected.start))) : 0;
  const [index, setIndex] = useState(first);
  const i = Math.min(index, hourly.t.length - 1);
  const fault = selected?.fault ? library.get(selected.fault) : undefined;
  const highlight = fault && isComponent(fault.component) ? fault.component : null;
  const emphasise = (fault?.measured.symptoms ?? []).map((s) => featureSignal(s.feature));

  const readings: Record<string, Reading> = {};
  for (const [key, col] of Object.entries(hourly.columns)) {
    if (col.kind !== "signal") continue;
    const v = col.values[i];
    if (v === null || v === undefined) continue;
    const band = hourly.columns[SIGNAL_BAND[key] ?? ""];
    const dev = band?.values[i];
    const tone = band ? deviationTone(dev, band) : "idle";
    readings[key] = {
      text: formatValue(v, col.unit),
      tone,
      note: band && dev != null
        ? `${band.kind === "residual" ? `${dev > 0 ? "+" : ""}${dev.toFixed(1)} typical errors from expected` : `normal ${formatValue(band.normal_low ?? 0, band.unit)} to ${formatValue(band.normal_high ?? 0, band.unit)}`}`
        : "no normal model for this signal",
    };
  }
  const mode = hourly.mode[i] ?? "unknown";
  const comp = hourly.columns.comp_stage?.values[i];
  const compressorOn = mode.includes("cooling") || (comp ?? 0) > 0.15;
  const damper = hourly.columns.oa_damper_cmd?.values[i] ?? null;
  const starts = result.events.map((e) => hourly.t.findIndex((t) => t >= Date.parse(e.start))).filter((x) => x >= 0).sort((a, b) => a - b);
  const prev = [...starts].reverse().find((s) => s < i);
  const next = starts.find((s) => s > i);
  const when = formatDataTime(new Date(hourly.t[i]!).toISOString());
  const answer = hourly.answer[i];

  return (
    <Card aria-labelledby={`${id}-h`}>
      <CardTitle
        id={`${id}-h`}
        sub="Sensor readings where the sensors are, coloured by how far each sits from what the normal-behaviour model expects. Hourly medians."
      >
        Unit schematic
      </CardTitle>
      <CutawaySchematic
        readings={readings}
        fanOn={mode !== "off" && mode !== "unknown"}
        compressorOn={compressorOn}
        damper={damper}
        highlight={highlight}
        emphasise={emphasise}
        title={`Rooftop unit schematic at ${when}: ${MODE_LABEL[mode] ?? mode}.${highlight ? ` Highlighted: ${COMPONENT_LABEL[highlight]}.` : ""}`}
      />
      <div className="mt-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold text-ink tabular-nums">{when}</span>
          <span className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-2" style={{ borderColor: MODE_COLOR[mode] }}>{MODE_LABEL[mode] ?? mode}</span>
          {hourly.alarm[i] ? <KindBadge kind={answer === "fault_free" ? "no_supported_fault" : answer === "inconclusive" || answer === "not_diagnosable" ? answer : "fault"} /> : <span className="text-xs text-muted">No alarm this hour</span>}
          {hourly.alarm[i] && answer && !["fault_free", "inconclusive", "not_diagnosable"].includes(answer) && (
            <span className="text-xs text-ink-2">{library.get(answer)?.title ?? answer} · {formatConfidence(hourly.confidence[i])}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" aria-label="Previous event" disabled={prev === undefined} onClick={() => prev !== undefined && setIndex(prev)}>
            <ChevronLeft aria-hidden="true" className="size-4" />
          </Button>
          <label htmlFor={`${id}-range`} className="sr-only">Hour shown in the schematic</label>
          <input
            id={`${id}-range`}
            type="range"
            min={0}
            max={hourly.t.length - 1}
            value={i}
            onChange={(e) => setIndex(Number(e.target.value))}
            aria-valuetext={`${when}, ${MODE_LABEL[mode] ?? mode}`}
            className="h-2 flex-1 cursor-pointer accent-[var(--accent)]"
          />
          <Button variant="secondary" aria-label="Next event" disabled={next === undefined} onClick={() => next !== undefined && setIndex(next)}>
            <ChevronRight aria-hidden="true" className="size-4" />
          </Button>
        </div>
        <ul className="flex flex-wrap gap-3 text-xs text-muted">
          {(["ok", "warn", "fault", "idle"] as Tone[]).map((t) => (
            <li key={t} className="flex items-center gap-1">
              <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: TONE_VAR[t] }} />
              {{ ok: "Within fault-free range", warn: "Slightly outside", fault: "Well outside", idle: "No normal model", info: "", accent: "" }[t]}
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

/** "Does the data look like this fault?" Each candidate's deciding signals, checked on this event. */
export function SignatureCheck({
  event,
  hourly,
  library,
}: {
  event: FaultEvent;
  hourly: HourlyTable;
  library: Map<string, LibraryFault>;
}) {
  const id = useId();
  const hours = eventHours(hourly, event);
  const probability = new Map((event.model.alternatives ?? []).map((a) => [a.fault, a.probability]));
  const candidates = [event.fault ?? event.model.top_class, ...(event.model.alternatives ?? []).map((a) => a.fault)]
    .filter((f): f is string => Boolean(f) && f !== "fault_free")
    .filter((f, i, all) => all.indexOf(f) === i)
    .slice(0, 3);

  const verdict = (feature: string): { tone: Tone; text: string } => {
    const col = hourly.columns[feature];
    if (!col) return { tone: "idle", text: "not measured" };
    const v = median(hours.map((h) => col.values[h]).filter((x): x is number => x !== null && x !== undefined));
    if (v === null) return { tone: "idle", text: "no data in event" };
    const tone = deviationTone(v, col);
    if (tone === "idle") return { tone, text: "no normal range" };
    return { tone, text: tone === "ok" ? `within normal (${formatValue(v, col.unit === "errors" ? "errors" : col.unit)})` : `abnormal (${formatValue(v, col.unit === "errors" ? "errors" : col.unit)})` };
  };

  return (
    <Card aria-labelledby={`${id}-h`}>
      <CardTitle
        id={`${id}-h`}
        sub="The signals that decided each fault in FaultIQ's held-out tests, checked on this event. A signal outside its fault-free range supports the fault."
      >
        Fault signature check
      </CardTitle>
      {candidates.length === 0 ? (
        <p className="text-sm text-muted">No candidate faults for this event.</p>
      ) : (
        <ul className="space-y-4">
          {candidates.map((f) => {
            const entry = library.get(f);
            const symptoms = entry?.measured.symptoms ?? [];
            const checks = symptoms.map((s) => ({ s, ...verdict(s.feature) }));
            const support = checks.filter((c) => c.tone === "warn" || c.tone === "fault").length;
            return (
              <li key={f} className="space-y-1.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link to={`/library/${f}`} className="font-medium text-accent hover:underline">{entry?.title ?? f}</Link>
                  <span className="text-xs text-muted">
                    {probability.has(f) ? `model ${formatConfidence(probability.get(f))} · ` : ""}
                    {checks.length ? `${support} of ${checks.length} signals support it` : "no measured symptoms"}
                  </span>
                </div>
                <ul className="flex flex-wrap gap-1.5">
                  {checks.map(({ s, tone, text }) => {
                    const Icon = tone === "ok" ? X : tone === "idle" ? HelpCircle : Check;
                    return (
                      <li
                        key={s.feature}
                        className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
                          tone === "ok" ? "border-line text-muted" : tone === "idle" ? "border-dashed border-line text-muted" : "border-fault-line bg-fault-soft text-fault")}
                      >
                        <Icon aria-hidden="true" className="size-3.5" />
                        <span className="font-medium">{s.signal}</span>: {text}
                      </li>
                    );
                  })}
                </ul>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function Sparkline({ col, alarm }: { col: HourlyColumn; alarm: boolean[] }) {
  const vals = col.values;
  const finite = vals.filter((v): v is number => v !== null && v !== undefined);
  const lo = Math.min(...finite, col.normal_low ?? Infinity);
  const hi = Math.max(...finite, col.normal_high ?? -Infinity);
  const n = vals.length;
  const y = (v: number) => 40 - ((v - lo) / Math.max(hi - lo, 1e-6)) * 36 - 2;
  let d = "";
  vals.forEach((v, i) => {
    if (v === null || v === undefined) return;
    d += `${d && vals[i - 1] != null ? "L" : "M"}${(i / Math.max(n - 1, 1)) * 600} ${y(v).toFixed(1)} `;
  });
  return (
    <svg viewBox="0 0 600 42" preserveAspectRatio="none" className="h-10 w-full" aria-hidden="true">
      {alarm.map((a, i) => (a ? <rect key={i} x={(i / n) * 600} y={0} width={600 / n + 0.5} height={42} fill="var(--fault-glow)" fillOpacity={0.12} /> : null))}
      {col.normal_low != null && col.normal_high != null && (
        <rect x={0} width={600} y={y(col.normal_high)} height={Math.max(1, y(col.normal_low) - y(col.normal_high))} fill="var(--ok)" fillOpacity={0.18} />
      )}
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** "Which signals left normal, and when?" Only deviating signals, ranked, with the band shaded. */
export function ResidualExplorer({ hourly }: { hourly: HourlyTable }) {
  const id = useId();
  const rows = useMemo(
    () =>
      Object.entries(hourly.columns)
        .filter(([, c]) => (c.kind === "residual" || c.kind === "physics") && c.normal_low != null && c.normal_high != null)
        .map(([key, c]) => {
          const vals = c.values.filter((v): v is number => v !== null && v !== undefined);
          const outside = vals.filter((v) => v < c.normal_low! || v > c.normal_high!).length;
          return { key, c, share: vals.length ? outside / vals.length : 0 };
        })
        .sort((a, b) => b.share - a.share),
    [hourly],
  );
  const deviating = rows.filter((r) => r.share >= 0.05);
  const quiet = rows.filter((r) => r.share < 0.05);
  return (
    <Card aria-labelledby={`${id}-h`}>
      <CardTitle
        id={`${id}-h`}
        sub="Hourly deviation from the normal-behaviour model (in typical errors) or physics features. Green band: fault-free range from validation. Red: alarmed hours."
      >
        Expected versus measured
      </CardTitle>
      {deviating.length === 0 ? (
        <p className="text-sm text-muted">Every signal stayed within its fault-free range for at least 95% of hours.</p>
      ) : (
        <ul className="space-y-3">
          {deviating.map(({ key, c, share }) => (
            <li key={key}>
              <div className="flex justify-between text-xs">
                <span className="font-medium text-ink">{c.label[0]!.toUpperCase() + c.label.slice(1)} <span className="font-normal text-muted">({c.kind === "residual" ? "vs expected" : "physics"})</span></span>
                <span className="text-muted tabular-nums">outside normal {Math.round(share * 100)}% of hours</span>
              </div>
              <Sparkline col={c} alarm={hourly.alarm} />
            </li>
          ))}
        </ul>
      )}
      {quiet.length > 0 && (
        <p className="mt-3 text-xs text-muted">Within normal almost all the time: {quiet.map((q) => q.c.label).join(", ")}.</p>
      )}
    </Card>
  );
}

function Band({ label, colours, titleFor }: { label: string; colours: string[]; titleFor: (i: number) => string }) {
  const n = colours.length || 1;
  return (
    <div className="grid grid-cols-[8.5rem_1fr] items-center gap-2">
      <span className="text-xs text-muted">{label}</span>
      <svg viewBox={`0 0 ${n} 10`} preserveAspectRatio="none" className="h-4 w-full rounded" role="img" aria-label={label}>
        {colours.map((c, i) => (
          <rect key={i} x={i} y={0} width={1.02} height={10} fill={c}>
            {n < 800 && <title>{titleFor(i)}</title>}
          </rect>
        ))}
      </svg>
    </div>
  );
}

/** "Why was this hour (not) diagnosable?" Mode, diagnosability, alarms and answers, aligned. */
export function ContextTimeline({ hourly }: { hourly: HourlyTable }) {
  const id = useId();
  const counts = new Map<string, number>();
  for (const m of hourly.mode) counts.set(m ?? "unknown", (counts.get(m ?? "unknown") ?? 0) + 1);
  const when = (i: number) => formatDataTime(new Date(hourly.t[i]!).toISOString());
  const kindOf = (a: string) => (a === "fault_free" ? "no_supported_fault" : a === "inconclusive" || a === "not_diagnosable" ? a : "fault");
  const ruleCols = Object.entries(hourly.columns).filter(([, c]) => c.kind === "rule");
  return (
    <Card aria-labelledby={`${id}-h`}>
      <CardTitle id={`${id}-h`} sub="One column per hour. Hours are diagnosed only when the relevant equipment ran steadily for 30 minutes or more.">
        Operating context
      </CardTitle>
      <div className="space-y-1.5">
        <Band label="Operating mode" colours={hourly.mode.map((m) => MODE_COLOR[m ?? "unknown"] ?? "var(--raised)")} titleFor={(i) => `${when(i)}: ${MODE_LABEL[hourly.mode[i] ?? "unknown"]}`} />
        <Band label="Diagnosable" colours={hourly.diagnosable.map((d) => (d ? "var(--ok)" : "var(--raised)"))} titleFor={(i) => `${when(i)}: ${hourly.diagnosable[i] ? "diagnosable" : "not diagnosable"}`} />
        <Band label="Detector alarm" colours={hourly.alarm.map((a) => (a ? "var(--fault-glow)" : "var(--raised)"))} titleFor={(i) => `${when(i)}: ${hourly.alarm[i] ? "alarm" : "no alarm"}`} />
        <Band
          label="Diagnosis"
          colours={hourly.answer.map((a, i) => (hourly.alarm[i] ? TONE_VAR[KIND_TONE[kindOf(a)] ?? "idle"] : "var(--raised)"))}
          titleFor={(i) => `${when(i)}: ${hourly.alarm[i] ? KIND_LABEL[kindOf(hourly.answer[i]!)] : "no alarm"}`}
        />
        {ruleCols.map(([key, c]) => (
          <Band
            key={key}
            label={`Rule: ${c.label}`}
            colours={c.values.map((v) => (v === null || v === undefined ? "var(--raised)" : v > 0.5 ? "var(--fault-glow)" : v > 0 ? "var(--warn-glow)" : "var(--ok)"))}
            titleFor={(i) => `${when(i)}: ${c.values[i] == null ? "rule not applicable" : `${Math.round((c.values[i] ?? 0) * 100)}% of minutes`}`}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-3 text-xs text-ink-2">
        {[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([m, n]) => (
          <li key={m} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: MODE_COLOR[m] }} />
            {MODE_LABEL[m] ?? m}: <strong className="tabular-nums">{n} h</strong>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** "What pushed the model?" The deciding features' summed contributions for this event. */
export function EvidenceWeights({ event }: { event: FaultEvent }) {
  const ev = event.evidence.filter((e) => e.weight > 0);
  if (!ev.length || (event.kind !== "fault" && event.kind !== "inconclusive")) return null;
  const max = Math.max(...ev.map((e) => e.weight));
  return (
    <section aria-labelledby="weights-heading" className="space-y-2">
      <h3 id="weights-heading" className="text-sm font-semibold text-ink">What pushed the model</h3>
      <p className="text-xs text-muted">Summed contribution toward the answer over the event (log-odds). Longer bars mattered more.</p>
      <ul className="space-y-1.5">
        {ev.map((e) => (
          <li key={e.id} className="grid grid-cols-[minmax(0,14rem)_1fr_3.5rem] items-center gap-3 text-sm">
            <span className="truncate text-ink-2">{e.signal}</span>
            <span className="h-2 rounded bg-raised" aria-hidden="true">
              <span className="block h-2 rounded bg-accent" style={{ width: `${(e.weight / max) * 100}%` }} />
            </span>
            <span className="text-right text-xs text-muted tabular-nums">{e.weight.toFixed(1)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Other events of the same fault on this unit, with their review outcomes. */
export function CaseHistory({
  result,
  event,
  rows,
  onSelect,
}: {
  result: DiagnosticResult;
  event: FaultEvent;
  rows: Map<string, FaultEventResponse>;
  onSelect: (key: string) => void;
}) {
  const same = result.events.filter((e) => e.id !== event.id && e.kind === event.kind && e.fault === event.fault);
  if (!same.length) return null;
  return (
    <section aria-labelledby="history-heading" className="space-y-2">
      <h3 id="history-heading" className="text-sm font-semibold text-ink">
        Same finding elsewhere in this analysis ({same.length})
      </h3>
      <ul className="flex flex-wrap gap-2">
        {same.slice(0, 12).map((e) => (
          <li key={e.id}>
            <button
              type="button"
              onClick={() => onSelect(e.id)}
              className="inline-flex items-center gap-2 rounded-lg border border-line px-2 py-1 text-xs text-ink-2 hover:border-accent"
            >
              {formatDataTime(e.start)} · {e.hours} h
              <ReviewBadge status={rows.get(e.id)?.review_status ?? "unreviewed"} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
