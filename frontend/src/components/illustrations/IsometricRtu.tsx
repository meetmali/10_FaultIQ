// An original isometric illustration of a packaged rooftop unit (ADR 0026). It shows state at a
// glance for the Operator: air moves and fans turn while the unit runs, and the part a fault
// affects glows with a label. Colour is never the only signal: the callout names the part, and the
// whole drawing has a text equivalent.
import { useId } from "react";

import { cn } from "../../lib/cn";
import { COMPONENT_LABEL, type Component, type UnitState } from "./components";

// Isometric projection: x along the unit's length, y across it, z up.
const S = 30;
const OX = 196;
const OY = 118;
const C30 = 0.866;
const iso = (x: number, y: number, z: number) => [OX + (x - y) * C30 * S, OY + (x + y) * 0.5 * S - z * S] as const;
const pts = (...p: (readonly [number, number])[]) => p.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(" ");

const L = 6; // length
const D = 3; // depth
const H = 2.2; // height

/** A rectangle on the long front face (y = D), from x0..x1 along it and z0..z1 up it. */
const front = (x0: number, x1: number, z0: number, z1: number) =>
  pts(iso(x0, D, z0), iso(x1, D, z0), iso(x1, D, z1), iso(x0, D, z1));
/** A rectangle on the end face (x = L). */
const end = (y0: number, y1: number, z0: number, z1: number) =>
  pts(iso(L, y0, z0), iso(L, y1, z0), iso(L, y1, z1), iso(L, y0, z1));

// Where each component sits, as polygons to light up when it is at fault.
const AREAS: Record<Component, string[]> = {
  oa_damper: [front(0.25, 1.45, 0.55, 1.75)],
  evaporator: [front(1.7, 3.0, 0.3, 1.9)],
  refrigerant_circuit: [front(3.2, 4.3, 0.3, 1.5)],
  controller: [front(3.35, 4.15, 1.6, 2.0)],
  liquid_line: [pts(iso(4.0, D, 0.42), iso(4.75, D, 0.42), iso(4.75, D, 0.55), iso(4.0, D, 0.55))],
  suction_line: [pts(iso(4.0, D, 0.7), iso(4.75, D, 0.7), iso(4.75, D, 0.86), iso(4.0, D, 0.86))],
  condenser: [front(4.6, 5.85, 0.25, 1.95), end(0.2, 2.8, 0.25, 1.95)],
  sat_sensor: [pts(iso(3.05, D + 0.55, -0.55), iso(3.45, D + 0.55, -0.55), iso(3.45, D + 0.55, -0.25), iso(3.05, D + 0.55, -0.25))],
};

// Where the callout points for each component.
const ANCHOR: Record<Component, readonly [number, number]> = {
  oa_damper: iso(0.85, D, 1.15),
  evaporator: iso(2.35, D, 1.1),
  refrigerant_circuit: iso(3.75, D, 0.9),
  controller: iso(3.75, D, 1.8),
  liquid_line: iso(4.4, D, 0.48),
  suction_line: iso(4.4, D, 0.78),
  condenser: iso(L, 1.5, 1.1),
  sat_sensor: iso(3.25, D + 0.55, -0.4),
};

const GLOW: Record<UnitState, string> = {
  fault: "var(--fault-glow)",
  unclear: "var(--warn-glow)",
  normal: "var(--ok)",
  analysing: "var(--accent)",
  off: "var(--idle)",
};

export function IsometricRtu({
  state,
  component,
  title,
  variant = "hero",
  className,
}: {
  state: UnitState;
  /** The part to highlight (fault or unclear only). */
  component?: Component | null;
  /** Text equivalent, e.g. "Rooftop unit RTU-1, running. Problem area: outdoor coil." */
  title: string;
  variant?: "hero" | "card" | "thumb";
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const running = state !== "off";
  const animate = running && variant !== "thumb";
  const highlight = component && (state === "fault" || state === "unclear") ? component : null;
  const glow = GLOW[state];

  const louvres = (x0: number, x1: number, z0: number, z1: number, n: number, face: "front" | "end", y0 = 0, y1 = 0) =>
    Array.from({ length: n }, (_, i) => {
      const z = z0 + ((z1 - z0) * (i + 0.5)) / n;
      const [a, b] = face === "front" ? [iso(x0, D, z), iso(x1, D, z)] : [iso(L, y0, z), iso(L, y1, z)];
      return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="var(--metal-edge)" strokeWidth={0.9} opacity={0.75} />;
    });

  const [fx, fy] = iso(5.0, 1.5, H);
  const callout = highlight ? ANCHOR[highlight] : null;

  return (
    <svg viewBox="0 0 400 300" role="img" aria-label={title} className={cn("h-auto w-full", className)}>
      <title>{title}</title>
      <defs>
        <linearGradient id={`roof-${uid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--roof)" />
          <stop offset="1" stopColor="var(--raised)" />
        </linearGradient>
        <linearGradient id={`scan-${uid}`} x1="0" x2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="0.5" stopColor="var(--accent)" stopOpacity="0.35" />
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
        <clipPath id={`unit-${uid}`}>
          <polygon points={pts(iso(0, 0, H), iso(L, 0, H), iso(L, D, H), iso(L, D, 0), iso(0, D, 0), iso(0, D, H))} />
        </clipPath>
      </defs>

      {/* Roof deck and curb */}
      <polygon points={pts(iso(-1.4, -1, -0.05), iso(L + 1.4, -1, -0.05), iso(L + 1.4, D + 1.8, -0.05), iso(-1.4, D + 1.8, -0.05))} fill={`url(#roof-${uid})`} />
      <polygon points={pts(iso(-0.15, D + 0.15, 0), iso(L + 0.15, D + 0.15, 0), iso(L + 0.15, D + 0.15, -0.12), iso(-0.15, D + 0.15, -0.12))} fill="var(--metal-3)" />

      {/* Ducts dropping into the roof: return (warm, rising) and supply (cool, falling) */}
      {[
        { x: 1.95, color: "var(--air-warm)", label: "return" },
        { x: 3.05, color: "var(--air-cool)", label: "supply" },
      ].map((d) => {
        const a = iso(d.x, D + 0.55, 0);
        const b = iso(d.x + 0.55, D + 0.55, 0);
        const c = iso(d.x + 0.55, D + 0.55, -1.1);
        const e = iso(d.x, D + 0.55, -1.1);
        const mid = iso(d.x + 0.27, D + 0.55, 0);
        const low = iso(d.x + 0.27, D + 0.55, -1.0);
        return (
          <g key={d.label}>
            <polygon points={pts(a, b, c, e)} fill="var(--metal-2)" stroke="var(--metal-edge)" strokeWidth={0.8} />
            {animate && (
              <line
                x1={mid[0]} y1={d.label === "return" ? low[1] : mid[1]} x2={low[0]} y2={d.label === "return" ? mid[1] : low[1]}
                stroke={d.color} strokeWidth={2.4} strokeLinecap="round" className="fq-flow" opacity={0.9}
              />
            )}
          </g>
        );
      })}

      {/* Cabinet: top, front (long) and end faces */}
      <polygon points={pts(iso(0, 0, H), iso(L, 0, H), iso(L, D, H), iso(0, D, H))} fill="var(--metal-1)" stroke="var(--metal-edge)" strokeWidth={1} />
      <polygon points={front(0, L, 0, H)} fill="var(--metal-2)" stroke="var(--metal-edge)" strokeWidth={1} />
      <polygon points={end(0, D, 0, H)} fill="var(--metal-3)" stroke="var(--metal-edge)" strokeWidth={1} />

      {/* Outdoor-air hood with damper louvres */}
      <polygon points={front(0.25, 1.45, 0.55, 1.75)} fill="var(--metal-3)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      {louvres(0.3, 1.4, 0.6, 1.7, 6, "front")}
      {animate && (
        <path
          d={`M ${iso(0.85, D + 1.3, 1.15)[0]} ${iso(0.85, D + 1.3, 1.15)[1]} L ${iso(0.85, D + 0.15, 1.15)[0]} ${iso(0.85, D + 0.15, 1.15)[1]}`}
          stroke="var(--air-cool)" strokeWidth={2.4} strokeLinecap="round" className="fq-flow" fill="none"
        />
      )}

      {/* Access panels: evaporator section, compressor section, controller */}
      <polygon points={front(1.7, 3.0, 0.3, 1.9)} fill="var(--metal-1)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      <polygon points={front(3.2, 4.3, 0.3, 1.5)} fill="var(--metal-1)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      <polygon points={front(3.35, 4.15, 1.6, 2.0)} fill="var(--surface)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      {(() => {
        const [lx, ly] = iso(4.0, D, 1.8);
        return <circle cx={lx} cy={ly} r={2.6} fill={glow} className={state === "fault" || state === "unclear" ? "fq-pulse" : undefined} />;
      })()}

      {/* Refrigerant lines between the compressor and condenser sections */}
      {[0.48, 0.78].map((z, i) => {
        const [a0, a1] = iso(4.0, D, z);
        const [b0, b1] = iso(4.75, D, z);
        return <line key={z} x1={a0} y1={a1} x2={b0} y2={b1} stroke="var(--refrigerant)" strokeWidth={i === 0 ? 2 : 3.2} strokeLinecap="round" />;
      })}

      {/* Condenser coil, wrapping the end */}
      <polygon points={front(4.6, 5.85, 0.25, 1.95)} fill="var(--metal-3)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      {louvres(4.65, 5.8, 0.3, 1.9, 9, "front")}
      <polygon points={end(0.2, 2.8, 0.25, 1.95)} fill="var(--metal-3)" stroke="var(--metal-edge)" strokeWidth={0.8} />
      {louvres(0, 0, 0.3, 1.9, 9, "end", 0.25, 2.75)}

      {/* Condenser fan on top, spinning in perspective; warm air rising when running */}
      <g transform={`translate(${fx} ${fy}) scale(1 0.55)`}>
        <circle r={27} fill="var(--metal-2)" stroke="var(--metal-edge)" strokeWidth={1.4} />
        <g className={animate ? "fq-spin" : undefined}>
          {[0, 90, 180, 270].map((a) => (
            <path key={a} d="M0 0 C 6 -6, 18 -10, 23 -3 C 14 -1, 6 2, 0 0 Z" fill="var(--metal-edge)" transform={`rotate(${a})`} />
          ))}
          <circle r={4} fill="var(--metal-3)" />
        </g>
      </g>
      {animate &&
        [-14, 0, 14].map((dx) => (
          <path
            key={dx}
            d={`M ${fx + dx} ${fy - 10} q 6 -12 0 -24 q -6 -12 0 -24`}
            stroke="var(--air-warm)" strokeWidth={2} fill="none" strokeLinecap="round" className="fq-flow" opacity={0.75}
          />
        ))}

      {/* Supply-air sensor on the supply duct */}
      {(() => {
        const [sx, sy] = iso(3.25, D + 0.55, -0.4);
        return <circle cx={sx} cy={sy} r={3.4} fill="var(--surface)" stroke="var(--metal-edge)" strokeWidth={1.2} />;
      })()}

      {/* Fault or unclear highlight */}
      {highlight &&
        AREAS[highlight].map((p, i) => (
          <polygon key={i} points={p} fill={glow} fillOpacity={0.45} stroke={glow} strokeWidth={2.2} className={variant === "thumb" ? undefined : "fq-pulse"} />
        ))}

      {/* Analysing: a scan sweeping across the unit */}
      {state === "analysing" && variant !== "thumb" && (
        <g clipPath={`url(#unit-${uid})`}>
          <rect x={60} y={20} width={140} height={240} fill={`url(#scan-${uid})`} className="fq-scan" />
        </g>
      )}

      {/* Callout naming the part, so colour is never the only signal. It sits in the empty top
          corner on the part's side, sized to its text. */}
      {callout && variant !== "thumb" && highlight && (() => {
        const label = COMPONENT_LABEL[highlight];
        const size = variant === "card" ? 15 : 12.5;
        const w = label.length * size * 0.56 + 18;
        const h = size + 14;
        const left = callout[0] < 200;
        const bx = left ? 6 : 394 - w;
        const by = 6;
        return (
          <g>
            <line x1={callout[0]} y1={callout[1]} x2={left ? bx + w * 0.6 : bx + w * 0.4} y2={by + h} stroke={glow} strokeWidth={1.4} />
            <circle cx={callout[0]} cy={callout[1]} r={3} fill={glow} />
            <rect x={bx} y={by} width={w} height={h} rx={7} fill="var(--surface)" stroke={glow} strokeWidth={1.4} />
            <text x={bx + w / 2} y={by + h / 2 + size * 0.36} textAnchor="middle" fontSize={size} fontWeight={600} fill="var(--ink)">
              {label}
            </text>
          </g>
        );
      })()}
    </svg>
  );
}
