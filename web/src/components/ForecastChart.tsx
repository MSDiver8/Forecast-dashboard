import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import { CustomChart, type CustomSeriesOption, LineChart, type LineSeriesOption } from "echarts/charts";
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import { withAlpha } from "../colors";
import { formatPeriod, formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { ChartLine } from "../lines";

echarts.use([
  LineChart, CustomChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent,
  MarkAreaComponent, LabelLayout, CanvasRenderer,
]);

export interface ChartHandle {
  zoomTo: (start: string | null, end: string | null) => void;
  png: (name: string) => void;
}

interface Props {
  lines: ChartLine[];
  periods: string[];
  unit: string;
  precision: number;
  showBands: boolean;
  showIntervals: boolean;
  lastFact: string | null;
  asofPeriod: string | null;
  asofDate: string;
  initialStart: string | null;
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export const ForecastChart = forwardRef<ChartHandle, Props>(function ForecastChart(
  { lines, periods, unit, precision, showBands, showIntervals, lastFact, asofPeriod, asofDate, initialStart }, ref,
) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const byKey = useMemo(() => new Map(lines.map((l) => [l.key, l])), [lines]);

  useEffect(() => {
    if (!box.current) return;
    const instance = echarts.init(box.current, undefined, { renderer: "canvas" });
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(box.current);
    return () => { observer.disconnect(); instance.dispose(); chart.current = null; };
  }, []);

  useImperativeHandle(ref, () => ({
    zoomTo: (start, end) => {
      chart.current?.dispatchAction({
        type: "dataZoom", startValue: start ?? periods[0], endValue: end ?? periods[periods.length - 1],
      });
    },
    png: (name) => {
      const url = chart.current?.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
      if (!url) return;
      const link = document.createElement("a");
      link.href = url;
      link.download = `${name}.png`;
      link.click();
    },
  }), [periods]);

  useEffect(() => {
    const instance = chart.current;
    if (!instance) return;
    const index = new Map(periods.map((p, i) => [p, i]));
    const series: (LineSeriesOption | CustomSeriesOption)[] = [];
    // Published ranges of releases are drawn as whiskers, slightly apart when several share a period.
    const ranged = lines.filter((l) => l.kind === "release" && l.points.some((p) => p.lower != null && p.upper != null));
    for (const line of lines) {
      const data: (number | null)[] = periods.map(() => null);
      for (const p of line.points) {
        const i = index.get(p.period);
        if (i !== undefined) data[i] = p.value;
      }
      const isActual = line.kind === "actual";
      const isModel = line.kind === "model";
      const sparse = line.points.length <= 12 || !line.connect;
      series.push({
        id: line.key,
        name: line.group,
        type: "line",
        data,
        connectNulls: line.connect,
        smooth: false,
        z: isActual ? 6 : isModel ? 4 : line.latest ? 5 : 3,
        color: line.color,
        lineStyle: {
          width: isActual ? 3.5 : line.latest ? 2.6 : 1.6,
          type: isModel ? "dashed" : "solid",
          color: line.color,
        },
        symbol: !line.connect && !isActual ? "diamond" : sparse ? "circle" : "none",
        symbolSize: !line.connect && !isActual ? 11 : isActual ? 6 : 5,
        showSymbol: sparse,
        emphasis: { focus: "series", lineStyle: { width: isActual ? 4 : 3.2 } },
        endLabel: {
          show: line.latest && !isActual,
          formatter: (p) => `${line.group}  ${formatValue(p.value as number, precision)}`,
          color: line.color,
          fontWeight: isActual ? 700 : 600,
          fontSize: 12,
          distance: 6,
        },
        labelLayout: { moveOverlap: "shiftY" },
        ...(isActual && lastFact
          ? {
            markLine: {
              silent: true, symbol: "none",
              lineStyle: { color: "#9aa8b5", type: "dashed", width: 1 },
              label: { formatter: t("chart.lastFact", { period: formatPeriod(lastFact) }), color: "#697583", fontSize: 11 },
              data: [{ xAxis: lastFact }, ...(asofPeriod ? [{
                xAxis: asofPeriod,
                label: { formatter: t("chart.asof", { date: formatShortDate(asofDate) }), color: "#b44343", fontSize: 11, position: "insideEndBottom" as const },
                lineStyle: { color: "#b44343", type: "solid" as const, width: 1 },
              }] : [])],
            },
            markArea: periods.indexOf(lastFact) < periods.length - 1 ? {
              silent: true,
              itemStyle: { color: "rgba(23, 60, 104, 0.035)" },
              label: { show: true, position: "insideTopRight", formatter: t("chart.forecasts"), color: "#9aa8b5", fontSize: 11 },
              data: [[{ xAxis: periods[periods.indexOf(lastFact) + 1] }, { xAxis: periods[periods.length - 1] }]],
            } : undefined,
          }
          : {}),
      });
      const hasRange = line.points.some((p) => p.lower != null && p.upper != null);
      if (showIntervals && hasRange && isModel) {
        // Fan chart: 95% interval lighter, 80% interval darker.
        for (const [level, lo, hi, alpha] of [["95", "lower", "upper", 0.07], ["80", "lower80", "upper80", 0.13]] as const) {
          const lower: (number | null)[] = periods.map(() => null);
          const width: (number | null)[] = periods.map(() => null);
          for (const p of line.points) {
            const i = index.get(p.period);
            const a = p[lo];
            const b = p[hi];
            if (i === undefined || a == null || b == null) continue;
            lower[i] = a;
            width[i] = b - a;
          }
          const common = {
            type: "line" as const, name: line.group, stack: `band${level}:${line.key}`, symbol: "none", silent: true,
            connectNulls: true, lineStyle: { opacity: 0 }, tooltip: { show: false }, z: 1,
          };
          series.push({ ...common, id: `band${level}-lo:${line.key}`, data: lower, areaStyle: { opacity: 0 } });
          series.push({ ...common, id: `band${level}-w:${line.key}`, data: width, areaStyle: { color: withAlpha(line.color, alpha) } });
        }
      } else if (showBands && hasRange) {
        const slot = ranged.indexOf(line);
        const dx = (slot - (ranged.length - 1) / 2) * 7;
        const data = line.points
          .filter((p) => p.lower != null && p.upper != null && index.has(p.period))
          .map((p) => [index.get(p.period)!, p.lower!, p.upper!]);
        series.push({
          type: "custom", id: `range:${line.key}`, name: line.group, silent: true, z: 2, tooltip: { show: false },
          data,
          renderItem: (_params, api) => {
            const top = api.coord([api.value(0), api.value(2)]);
            const bottom = api.coord([api.value(0), api.value(1)]);
            const x = top[0] + dx;
            const stroke = { stroke: line.color, lineWidth: line.latest ? 2 : 1.4, opacity: line.latest ? 0.85 : 0.5 };
            return {
              type: "group",
              children: [
                { type: "line", shape: { x1: x, y1: top[1], x2: x, y2: bottom[1] }, style: stroke },
                { type: "line", shape: { x1: x - 5, y1: top[1], x2: x + 5, y2: top[1] }, style: stroke },
                { type: "line", shape: { x1: x - 5, y1: bottom[1], x2: x + 5, y2: bottom[1] }, style: stroke },
              ],
            };
          },
        });
      }
    }

    const legend = [...new Set(lines.map((l) => l.group))];
    const biggest = Math.max(0, ...lines.flatMap((l) => l.points.map((p) => Math.abs(p.value))));
    const digits = biggest >= 20 ? 0 : biggest >= 2 ? 1 : 2;
    const startIndex = initialStart ? Math.max(0, periods.indexOf(initialStart)) : 0;
    instance.setOption({
      animationDuration: 300,
      grid: { left: 12, right: 150, top: 56, bottom: 78, containLabel: true },
      legend: {
        type: "scroll", top: 0, left: 0, right: 0, data: legend, itemWidth: 22, itemHeight: 10, icon: "roundRect",
        textStyle: { color: "#202a35", fontSize: 13 }, pageIconSize: 11,
      },
      tooltip: {
        trigger: "axis",
        confine: true,
        backgroundColor: "rgba(255,255,255,0.98)",
        borderColor: "#bfcbd4",
        padding: [10, 12],
        textStyle: { color: "#202a35", fontSize: 12 },
        axisPointer: { type: "line", lineStyle: { color: "#9aa8b5" } },
        formatter: (params: unknown) => {
          const items = (Array.isArray(params) ? params : [params]) as { seriesId: string; value: number | null; axisValue: string }[];
          const rows = items
            .filter((i) => i.value != null && byKey.has(i.seriesId))
            .map((i) => ({ line: byKey.get(i.seriesId)!, value: i.value as number, period: i.axisValue }))
            .sort((a, b) => b.value - a.value);
          if (!rows.length) return "";
          const period = rows[0].period;
          const body = rows.map(({ line, value }) => {
            const point = line.points.find((p) => p.period === period);
            const range = point && point.lower != null && point.upper != null
              ? ` <span style="color:#697583">(${formatValue(point.lower, precision)}–${formatValue(point.upper, precision)})</span>`
              : "";
            const vintage = line.vintage ? `<div style="color:#697583;font-size:11px">${t("chart.vintage", { date: formatShortDate(line.vintage) })}</div>` : "";
            const dash = line.kind === "model" ? "border-top:2px dashed" : "border-top:3px solid";
            return `<div style="display:grid;grid-template-columns:14px 1fr auto;gap:8px;align-items:start;padding:3px 0">
              <i style="display:block;margin-top:7px;width:14px;${dash} ${line.color}"></i>
              <div>${escapeHtml(line.label)}${vintage}</div>
              <b style="white-space:nowrap">${formatValue(value, precision)}${range}</b></div>`;
          }).join("");
          return `<div style="min-width:240px;max-width:380px"><div style="font-weight:700;margin-bottom:6px">${formatPeriod(period)} · <span style="font-weight:400;color:#697583">${escapeHtml(unit)}</span></div>${body}</div>`;
        },
      },
      xAxis: {
        type: "category", data: periods, boundaryGap: false,
        axisLabel: { formatter: (v: string) => formatPeriod(v), color: "#65717f", fontSize: 12, hideOverlap: true },
        axisLine: { lineStyle: { color: "#c9d3dc" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value", scale: true, name: unit, nameLocation: "end", nameGap: 14,
        nameTextStyle: { color: "#697583", fontSize: 12, align: "left" },
        axisLabel: { color: "#65717f", fontSize: 12, formatter: (v: number) => formatValue(v, digits) },
        splitLine: { lineStyle: { color: "#e5ebf0" } },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0, filterMode: "weakFilter", startValue: periods[startIndex], endValue: periods[periods.length - 1] },
        {
          type: "slider", xAxisIndex: 0, filterMode: "weakFilter", height: 26, bottom: 18,
          startValue: periods[startIndex], endValue: periods[periods.length - 1],
          labelFormatter: (_: number, value: string) => formatPeriod(value),
          borderColor: "#d7dfe7", fillerColor: "rgba(8,117,189,0.12)", handleStyle: { color: "#0875bd" },
          dataBackground: { lineStyle: { color: "#9ccbe6" }, areaStyle: { color: "rgba(98,180,220,0.18)" } },
        },
      ],
      series,
    }, { notMerge: true });
  }, [lines, periods, unit, precision, showBands, showIntervals, lastFact, asofPeriod, asofDate, initialStart, byKey]);

  return <div ref={box} className="echart" role="img" aria-label={unit} />;
});
