import { lazy, Suspense, type ReactNode } from "react";

import { formatValue, unitLabel } from "../../lib/format";
import type { ChartOption } from "./EChart";

const EChart = lazy(() => import("./EChart"));

export type { ChartOption };

/** One axis series to summarise in text: label, unit and values. */
export interface SeriesSummary {
  label: string;
  unit: string;
  values: (number | null)[];
}

function stats(values: (number | null)[]) {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x));
  if (!v.length) return null;
  return { min: Math.min(...v), max: Math.max(...v), mean: v.reduce((a, b) => a + b, 0) / v.length };
}

/**
 * A chart with a caption and a text summary, so the information doesn't depend on seeing the
 * canvas (section 11: accessible chart summaries).
 */
export function ChartFigure({
  title,
  description,
  option,
  summary,
  height,
  downsampled = true,
  footer,
}: {
  title: string;
  description: string;
  option: ChartOption;
  summary: SeriesSummary[];
  height?: number;
  downsampled?: boolean;
  footer?: ReactNode;
}) {
  return (
    <figure className="space-y-2">
      <figcaption>
        <span className="text-sm font-medium text-slate-900">{title}</span>
        <span className="block text-xs text-slate-600">
          {description}
          {downsampled && " Downsampled for display; analysis uses every minute."}
        </span>
      </figcaption>
      <div role="img" aria-label={`${title}. ${description}`}>
        <Suspense fallback={<div style={{ height: height ?? 280 }} className="animate-pulse rounded bg-slate-100" />}>
          <EChart option={option} height={height} />
        </Suspense>
      </div>
      {summary.length > 0 && (
      <details className="text-xs text-slate-700">
        <summary className="cursor-pointer text-sky-800">Data summary</summary>
        <table className="mt-2 w-full text-left [&_td]:px-2 [&_th]:px-2">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 font-medium">Series</th>
              <th className="font-medium">Min</th>
              <th className="font-medium">Mean</th>
              <th className="font-medium">Max</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((s) => {
              const st = stats(s.values);
              return (
                <tr key={s.label} className="border-t border-slate-100">
                  <th scope="row" className="py-1 font-normal">
                    {s.label} {unitLabel(s.unit) && `(${unitLabel(s.unit)})`}
                  </th>
                  <td>{st ? formatValue(st.min, s.unit) : "no data"}</td>
                  <td>{st ? formatValue(st.mean, s.unit) : ""}</td>
                  <td>{st ? formatValue(st.max, s.unit) : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
      )}
      {footer}
    </figure>
  );
}
