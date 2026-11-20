// Lightweight SVG visuals for the persona views (ADR 0026). They follow the theme through CSS
// variables and each has a text equivalent, so nothing depends on seeing colour.
import { formatNumber } from "../lib/format";
import { TONE_VAR, type Tone } from "../lib/tone";

export interface RingSlice {
  label: string;
  value: number;
  tone: Tone;
}

/** A donut of counts with the total in the middle and a text legend beside it. */
export function HealthRing({ slices, centre, caption }: { slices: RingSlice[]; centre: string; caption: string }) {
  const total = slices.reduce((a, s) => a + s.value, 0) || 1;
  const r = 52;
  const c = 2 * Math.PI * r;
  // Each slice starts where the previous one ended.
  const arcs = slices
    .filter((s) => s.value > 0)
    .map((s, i, all) => ({ ...s, len: (s.value / total) * c, start: all.slice(0, i).reduce((a, x) => a + (x.value / total) * c, 0) }));
  return (
    <figure className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 140 140" className="size-40 shrink-0" role="img" aria-label={`${caption}: ${slices.map((s) => `${s.value} ${s.label}`).join(", ")}`}>
        <circle cx={70} cy={70} r={r} fill="none" stroke="var(--raised)" strokeWidth={16} />
        {arcs.map((s) => (
          <circle
            key={s.label} cx={70} cy={70} r={r} fill="none" stroke={TONE_VAR[s.tone]} strokeWidth={16}
            strokeDasharray={`${s.len} ${c - s.len}`} strokeDashoffset={-s.start} transform="rotate(-90 70 70)"
          />
        ))}
        <text x={70} y={68} textAnchor="middle" fontSize={26} fontWeight={700} fill="var(--ink)">{centre}</text>
        <text x={70} y={88} textAnchor="middle" fontSize={10} fill="var(--muted)">units</text>
      </svg>
      <figcaption className="space-y-1.5">
        {slices.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-sm">
            <span aria-hidden="true" className="size-3 rounded-full" style={{ background: TONE_VAR[s.tone] }} />
            <span className="w-8 font-semibold text-ink tabular-nums">{s.value}</span>
            <span className="text-ink-2">{s.label}</span>
          </div>
        ))}
      </figcaption>
    </figure>
  );
}

export interface DayCell {
  date: string; // YYYY-MM-DD
  faultHours: number;
  otherHours: number;
}

/** A day grid: each square is a day, darker when more unit-hours had a named fault. */
export function IssueCalendar({ days, title }: { days: DayCell[]; title: string }) {
  if (!days.length) return null;
  const byDate = new Map(days.map((d) => [d.date, d]));
  // The last 16 weeks of data, starting on a Monday so each column is one week.
  const last = new Date(`${days[days.length - 1]!.date}T00:00:00Z`);
  const start = new Date(last);
  start.setUTCDate(start.getUTCDate() - (16 * 7 - 1));
  start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
  const total = Math.round((last.getTime() - start.getTime()) / 86_400_000) + 1;
  const weeks = Math.ceil(total / 7);
  const max = Math.max(1, ...days.map((d) => d.faultHours));
  const cells = Array.from({ length: total }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i);
    const key = d.toISOString().slice(0, 10);
    return { key, i, cell: byDate.get(key) };
  });
  const shown = cells.filter((c) => c.cell);
  const worst = [...shown].sort((a, b) => b.cell!.faultHours - a.cell!.faultHours)[0];
  const size = 13;
  return (
    <figure className="space-y-2">
      <figcaption className="text-xs text-muted">{title}</figcaption>
      <svg viewBox={`0 0 ${weeks * (size + 3)} ${7 * (size + 3)}`} className="h-auto w-full max-w-md" role="img"
        aria-label={`${title}. ${shown.length} days with data${worst ? `; the worst day was ${worst.key} with ${worst.cell!.faultHours} unit-hours of named faults` : ""}.`}>
        {cells.map(({ key, i, cell }) => {
          const x = Math.floor(i / 7) * (size + 3);
          const y = (i % 7) * (size + 3);
          const level = cell ? cell.faultHours / max : 0;
          return (
            <rect key={key} x={x} y={y} width={size} height={size} rx={3}
              fill={!cell ? "var(--raised)" : cell.faultHours > 0 ? "var(--fault-glow)" : cell.otherHours > 0 ? "var(--warn-glow)" : "var(--ok)"}
              fillOpacity={!cell ? 1 : cell.faultHours > 0 ? 0.25 + 0.75 * level : 0.45}>
              <title>{cell ? `${key}: ${cell.faultHours} unit-hours with a named fault, ${cell.otherHours} other` : `${key}: no data`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-3 text-xs text-muted">
        <span className="flex items-center gap-1"><span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: "var(--fault-glow)" }} />Named fault (darker = more unit-hours)</span>
        <span className="flex items-center gap-1"><span aria-hidden="true" className="size-2.5 rounded-sm opacity-50" style={{ background: "var(--warn-glow)" }} />Unclear only</span>
        <span className="flex items-center gap-1"><span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: "var(--raised)" }} />No data</span>
      </div>
    </figure>
  );
}

export interface StripSegment {
  tone: Tone | "none";
}

/** One coloured band per hour, with a legend: how long and how often something was wrong. */
export function HealthStrip({
  segments,
  start,
  end,
  label,
  legend,
}: {
  segments: StripSegment[];
  start: string;
  end: string;
  label: string;
  legend: { tone: Tone | "none"; text: string; count: number }[];
}) {
  const n = segments.length || 1;
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${n} 10`} preserveAspectRatio="none" className="h-8 w-full rounded-lg" role="img"
        aria-label={`${label}: ${legend.map((l) => `${formatNumber(l.count)} hours ${l.text.toLowerCase()}`).join(", ")}`}>
        {segments.map((s, i) => (
          <rect key={i} x={i} y={0} width={1.02} height={10} fill={s.tone === "none" ? "var(--raised)" : TONE_VAR[s.tone]} fillOpacity={s.tone === "none" ? 1 : 0.85} />
        ))}
      </svg>
      <div className="flex justify-between text-xs text-muted"><span>{start}</span><span>{end}</span></div>
      <figcaption className="flex flex-wrap gap-3 text-xs text-ink-2">
        {legend.map((l) => (
          <span key={l.text} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ background: l.tone === "none" ? "var(--raised)" : TONE_VAR[l.tone] }} />
            {l.text}: <strong className="tabular-nums">{formatNumber(l.count)} h</strong>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/** A small meter, e.g. how reliably FaultIQ detects a fault. */
export function Meter({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span className="text-muted">{label}</span><span className="font-semibold text-ink tabular-nums">{pct}%</span></div>
      <div className="h-2 rounded-full bg-raised" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="h-2 rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
