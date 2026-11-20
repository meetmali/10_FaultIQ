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

// Two themes from the same token values as the CSS (ADR 0026).
const theme = (text: string, muted: string, line: string) => ({
  backgroundColor: "transparent",
  textStyle: { color: text },
  legend: { textStyle: { color: text } },
  categoryAxis: { axisLine: { lineStyle: { color: line } }, axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } } },
  valueAxis: { axisLine: { lineStyle: { color: line } }, axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } }, nameTextStyle: { color: muted } },
  timeAxis: { axisLine: { lineStyle: { color: line } }, axisLabel: { color: muted }, splitLine: { show: false }, nameTextStyle: { color: muted } },
  dataZoom: { textStyle: { color: muted }, borderColor: line },
});
echarts.registerTheme("fq-light", theme("#334155", "#5b6b80", "#dde3ec"));
echarts.registerTheme("fq-dark", theme("#c5d0df", "#94a5bb", "#26344c"));

export default function EChart({ option, height = 280, dark = false }: { option: ChartOption; height?: number; dark?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const instance = echarts.init(el.current, dark ? "fq-dark" : "fq-light", { renderer: "canvas" });
    chart.current = instance;
    const resize = new ResizeObserver(() => instance.resize());
    resize.observe(el.current);
    instance.setOption({ useUTC: true, aria: { enabled: true }, animation: false, ...option }, true);
    return () => {
      resize.disconnect();
      instance.dispose();
      chart.current = null;
    };
    // Re-create on a theme change; option updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark]);

  useEffect(() => {
    chart.current?.setOption({ useUTC: true, aria: { enabled: true }, animation: false, ...option }, true);
  }, [option]);

  return <div ref={el} style={{ height }} className="w-full" />;
}
