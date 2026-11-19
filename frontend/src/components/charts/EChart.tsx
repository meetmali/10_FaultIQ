// The only file that imports ECharts. Loaded lazily, with only the modules FaultIQ uses (ADR 0009).
import { BarChart, LineChart } from "echarts/charts";
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([
  LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent,
  DataZoomComponent, AriaComponent, CanvasRenderer,
]);

export type ChartOption = echarts.EChartsCoreOption;

export default function EChart({ option, height = 280 }: { option: ChartOption; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const instance = echarts.init(el.current, undefined, { renderer: "canvas" });
    chart.current = instance;
    const resize = new ResizeObserver(() => instance.resize());
    resize.observe(el.current);
    return () => {
      resize.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption({ useUTC: true, aria: { enabled: true }, animation: false, ...option }, true);
  }, [option]);

  return <div ref={el} style={{ height }} className="w-full" />;
}
