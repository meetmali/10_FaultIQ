// An original cutaway schematic of a packaged rooftop unit for the Technician (ADR 0026): the air
// path on top, the refrigerant loop below, and sensor readings where the sensors physically are.
// Readings are coloured by how far they sit from expected, not by raw value, so the drawing answers
// "what looks wrong right now?". Every tag also carries its value in text.
import { useId } from "react";

import { cn } from "../../lib/cn";
import { TONE_VAR, type Tone } from "../../lib/tone";
import { COMPONENT_LABEL, type Component } from "./components";

export interface Reading {
  text: string;
  tone: Tone;
  /** Why it has this tone, e.g. "+5.8 typical errors from expected". */
  note?: string;
}

interface Group {
  title: string;
  keys: [string, string][]; // [signal key, short label]
  x: number;
  y: number;
  anchor?: [number, number];
}

// Tags grouped by location, placed so none overlap the drawing.
const GROUPS: Group[] = [
  { title: "Outdoor air", keys: [["oat", "Temp"]], x: 6, y: 46, anchor: [64, 98] },
  { title: "OA damper", keys: [["oa_damper_cmd", "Command"]], x: 6, y: 118, anchor: [150, 104] },
  { title: "Return air", keys: [["rat", "Temp"]], x: 6, y: 246, anchor: [206, 280] },
  { title: "Zone", keys: [["zone_temp", "Temp"]], x: 6, y: 318 },
  { title: "Mixed air", keys: [["mat", "Temp"]], x: 180, y: 4, anchor: [240, 130] },
  { title: "Supply fan", keys: [["power_fan", "Power"]], x: 372, y: 4, anchor: [430, 104] },
  {
    title: "Supply air",
    keys: [["sat", "Temp"], ["sa_flow", "Airflow"], ["vav_sat_min", "VAV min"]],
    x: 376, y: 244, anchor: [540, 264],
  },
  {
    title: "Suction",
    keys: [["refg_suct_pres", "Pressure"], ["refg_suct_temp", "Temp"], ["superheat", "Superheat"]],
    x: 300, y: 374, anchor: [392, 362],
  },
  { title: "Compressor", keys: [["comp_stage", "Stage"], ["power_comp", "Power"]], x: 506, y: 374, anchor: [488, 372] },
  { title: "Discharge", keys: [["refg_disc_pres", "Pressure"], ["refg_disc_temp", "Temp"]], x: 556, y: 290, anchor: [700, 316] },
  { title: "Liquid", keys: [["subcooling", "Subcooling"]], x: 610, y: 458, anchor: [650, 452] },
  { title: "Condenser", keys: [["condensing_approach", "Approach"]], x: 752, y: 116, anchor: [742, 150] },
];

// Highlight shapes for a component at fault.
const AREAS: Record<Component, { d: string }> = {
  oa_damper: { d: "M140 70 h20 v62 h-20 Z" },
  evaporator: { d: "M276 72 h78 v156 h-78 Z" },
  refrigerant_circuit: { d: "M444 336 a26 26 0 1 0 52 0 a26 26 0 1 0 -52 0 Z" },
  controller: { d: "M560 70 h52 v34 h-52 Z" },
  liquid_line: { d: "M735 232 V452 H315 V300" },
  suction_line: { d: "M345 232 V362 H444" },
  condenser: { d: "M630 64 h110 v168 h-110 Z" },
  sat_sensor: { d: "M548 252 h24 v24 h-24 Z" },
};

const TAG_W = 138;
const LINE_H = 15;

export function CutawaySchematic({
  readings,
  fanOn,
  compressorOn,
  damper,
  highlight,
  emphasise = [],
  title,
  className,
}: {
  readings: Record<string, Reading>;
  fanOn: boolean;
  compressorOn: boolean;
  /** Outdoor-air damper command, 0 to 1, or null when unknown. */
  damper: number | null;
  highlight?: Component | null;
  /** Signals to emphasise, e.g. the diagnosed fault's deciding signals. */
  emphasise?: string[];
  title: string;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const blade = damper === null ? 0 : Math.max(0, Math.min(1, damper)) * 75; // 0 = closed, 75 deg = open

  return (
    <svg viewBox="0 0 900 500" role="img" aria-label={title} className={cn("h-auto w-full", className)}>
      <title>{title}</title>
      <defs>
        <marker id={`arrow-${uid}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--muted)" />
        </marker>
      </defs>

      {/* Cabinet: air section and condenser section */}
      <rect x={140} y={60} width={600} height={172} rx={8} fill="var(--metal-1)" stroke="var(--metal-edge)" strokeWidth={1.5} />
      <line x1={620} y1={60} x2={620} y2={232} stroke="var(--metal-edge)" strokeWidth={1.5} />

      {/* Outdoor-air inlet and damper blades (rotate with the command) */}
      <path d="M60 98 H140" stroke="var(--air-cool)" strokeWidth={3} className={fanOn ? "fq-flow" : undefined} markerEnd={`url(#arrow-${uid})`} />
      {[76, 92, 108, 124].map((y) => (
        <line key={y} x1={150} y1={y - 7} x2={150} y2={y + 7} stroke="var(--metal-edge)" strokeWidth={3} strokeLinecap="round" transform={`rotate(${blade} 150 ${y})`} />
      ))}

      {/* Return duct from the building (warm air rising) */}
      <rect x={180} y={232} width={52} height={70} fill="var(--metal-2)" stroke="var(--metal-edge)" />
      <path d="M206 300 V236" stroke="var(--air-warm)" strokeWidth={3} className={fanOn ? "fq-flow" : undefined} markerEnd={`url(#arrow-${uid})`} />

      {/* Filter and evaporator coil */}
      <rect x={280} y={76} width={12} height={148} fill="var(--raised)" stroke="var(--metal-edge)" />
      {Array.from({ length: 9 }, (_, i) => (
        <line key={i} x1={281} y1={82 + i * 16} x2={291} y2={90 + i * 16} stroke="var(--metal-edge)" strokeWidth={0.8} />
      ))}
      <path d={`M300 76 ${Array.from({ length: 10 }, (_, i) => `L${i % 2 ? 300 : 348} ${76 + (i + 1) * 14.8}`).join(" ")}`} fill="none" stroke="var(--air-cool)" strokeWidth={2} />
      <text x={314} y={240} fontSize={10} fill="var(--muted)" textAnchor="middle">evaporator</text>

      {/* Air path through the unit */}
      <path d="M170 150 H520" stroke="var(--air-cool)" strokeWidth={2.4} fill="none" className={fanOn ? "fq-flow" : undefined} opacity={0.8} />

      {/* Supply fan */}
      <circle cx={430} cy={150} r={40} fill="var(--metal-2)" stroke="var(--metal-edge)" strokeWidth={1.5} />
      <g transform="translate(430 150)">
        <g className={fanOn ? "fq-spin" : undefined}>
          {[0, 72, 144, 216, 288].map((a) => (
            <path key={a} d="M0 0 C 8 -10, 26 -14, 32 -4 C 20 -2, 8 4, 0 0 Z" fill="var(--metal-edge)" transform={`rotate(${a})`} />
          ))}
          <circle r={5} fill="var(--metal-3)" />
        </g>
      </g>

      {/* Supply duct down to the building, supply-air sensor */}
      <rect x={520} y={232} width={40} height={60} fill="var(--metal-2)" stroke="var(--metal-edge)" />
      <path d="M520 150 H540 V290" stroke="var(--air-cool)" strokeWidth={3} fill="none" className={fanOn ? "fq-flow" : undefined} markerEnd={`url(#arrow-${uid})`} />
      <circle cx={560} cy={264} r={6} fill="var(--surface)" stroke="var(--metal-edge)" strokeWidth={1.5} />

      {/* Controller */}
      <rect x={560} y={72} width={50} height={30} rx={4} fill="var(--surface)" stroke="var(--metal-edge)" />
      <text x={585} y={91} fontSize={10} textAnchor="middle" fill="var(--muted)">control</text>

      {/* Condenser coil and fan */}
      <path d={`M640 72 ${Array.from({ length: 12 }, (_, i) => `L${i % 2 ? 640 : 730} ${72 + (i + 1) * 13}`).join(" ")}`} fill="none" stroke="var(--air-warm)" strokeWidth={2} />
      <g transform="translate(685 40)">
        <ellipse rx={30} ry={10} fill="var(--metal-2)" stroke="var(--metal-edge)" />
        <g transform="scale(1 0.33)">
          <g className={compressorOn ? "fq-spin" : undefined}>
            {[0, 120, 240].map((a) => (
              <path key={a} d="M0 0 C 6 -8, 20 -12, 26 -4 C 16 -2, 6 3, 0 0 Z" fill="var(--metal-edge)" transform={`rotate(${a})`} />
            ))}
          </g>
        </g>
      </g>
      {compressorOn && [-14, 0, 14].map((dx) => (
        <path key={dx} d={`M${685 + dx} 28 q 5 -8 0 -16 q -5 -8 0 -16`} stroke="var(--air-warm)" strokeWidth={1.8} fill="none" className="fq-flow" />
      ))}

      {/* Refrigerant loop: suction (to compressor), discharge (to condenser), liquid (back to the valve) */}
      <path d="M345 232 V362 H444" stroke="var(--refrigerant)" strokeWidth={5} fill="none" className={compressorOn ? "fq-flow" : undefined} />
      <path d="M496 362 H700 V232" stroke="var(--air-warm)" strokeWidth={4} fill="none" className={compressorOn ? "fq-flow" : undefined} />
      <path d="M735 232 V452 H315 V232" stroke="var(--refrigerant)" strokeWidth={2.5} fill="none" className={compressorOn ? "fq-flow" : undefined} />
      <rect x={510} y={445} width={26} height={14} rx={4} fill="var(--metal-2)" stroke="var(--metal-edge)" />
      <path d="M307 292 L323 308 M307 308 L323 292" stroke="var(--metal-edge)" strokeWidth={2.5} />
      <text x={292} y={322} fontSize={10} fill="var(--muted)" textAnchor="end">expansion valve</text>
      <circle cx={470} cy={362} r={26} fill="var(--metal-2)" stroke="var(--metal-edge)" strokeWidth={1.5} />
      <text x={470} y={366} fontSize={11} textAnchor="middle" fontWeight={600} fill="var(--ink-2)">C</text>

      {/* Highlight for the component at fault */}
      {highlight && (
        <path
          d={AREAS[highlight].d}
          fill={highlight === "liquid_line" || highlight === "suction_line" ? "none" : "var(--fault-glow)"}
          fillOpacity={0.25}
          stroke="var(--fault-glow)"
          strokeWidth={highlight === "liquid_line" || highlight === "suction_line" ? 9 : 3}
          strokeOpacity={0.7}
          className="fq-pulse"
        >
          <title>{COMPONENT_LABEL[highlight]}</title>
        </path>
      )}

      {/* Sensor tags: readings where the sensors are, coloured by deviation from expected */}
      {GROUPS.map((g) => {
        const lines = g.keys.filter(([k]) => readings[k]);
        if (!lines.length) return null;
        const worst = (["fault", "warn", "ok", "idle"] as Tone[]).find((t) => lines.some(([k]) => readings[k]!.tone === t)) ?? "idle";
        const h = 18 + lines.length * LINE_H;
        const emph = lines.some(([k]) => emphasise.includes(k));
        return (
          <g key={g.title}>
            {g.anchor && (
              <line
                x1={g.anchor[0]} y1={g.anchor[1]}
                x2={g.x + (g.anchor[0] > g.x + TAG_W ? TAG_W : g.anchor[0] < g.x ? 0 : TAG_W / 2)}
                y2={g.y + (g.anchor[1] > g.y + h ? h : g.anchor[1] < g.y ? 0 : h / 2)}
                stroke={TONE_VAR[worst]} strokeWidth={1} strokeDasharray="3 3"
              />
            )}
            <rect x={g.x} y={g.y} width={TAG_W} height={h} rx={7} fill="var(--surface)" stroke={TONE_VAR[worst]} strokeWidth={emph ? 2.6 : 1.4} />
            <text x={g.x + 8} y={g.y + 13} fontSize={10} fontWeight={600} fill="var(--muted)">{g.title.toUpperCase()}</text>
            {lines.map(([k, label], i) => {
              const r = readings[k]!;
              return (
                <g key={k}>
                  <title>{`${g.title} ${label}: ${r.text}${r.note ? ` (${r.note})` : ""}`}</title>
                  <circle cx={g.x + 11} cy={g.y + 24 + i * LINE_H} r={3} fill={TONE_VAR[r.tone]} />
                  <text x={g.x + 18} y={g.y + 28 + i * LINE_H} fontSize={10.5} fill="var(--muted)">{label}</text>
                  <text x={g.x + TAG_W - 7} y={g.y + 28 + i * LINE_H} fontSize={11} fontWeight={600} textAnchor="end" fill="var(--ink)">{r.text}</text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
