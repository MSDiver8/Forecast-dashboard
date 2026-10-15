import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { LineChart, type LineSeriesOption, ScatterChart, type ScatterSeriesOption } from "echarts/charts";
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import { ACTUAL_COLOR } from "../colors";
import { formatMonth, formatPeriod, formatShortDate, formatValue, SHORT_MONTHS } from "../format";
import { t } from "../i18n";
import type { EvalForecast, Evaluation } from "../types";

echarts.use([
  LineChart, ScatterChart, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
  DataZoomComponent, LabelLayout, CanvasRenderer,
]);

const CONTEXT_COLOR = "#8cc6e6";
const DAY = 864e5;

/** A series drawn on the accuracy chart: a selected agency or benchmark model. */
export interface ChartSeries { key: string; name: string; color: string; model: boolean }

export interface AccuracyChartHandle { zoomAll: () => void; png: (name: string) => void }

interface Props {
  data: Evaluation;
  mode: "periods" | "evolution";
  period: string | null;
  series: ChartSeries[];
  periodLabel: (period: string) => string;
  onSelect: (period: string) => void;
}

interface Point { value: [string, number | null]; tip?: string; period?: string; symbolSize?: number; itemStyle?: object }

/** Rounded as shown: an error that rounds to zero gets no sign. */
export function roundTo(value: number, digits: number): number {
  return Math.round(value * 10 ** digits) / 10 ** digits || 0;
}

export function signed(value: number, digits: number): string {
  const shown = roundTo(value, digits);
  return `${shown > 0 ? "+" : ""}${formatValue(shown, digits)}`.replace("-", "−");
}

export function monthLabel(day: string): string {
  return formatMonth(day.slice(0, 10));
}

const ms = (day: string) => Date.parse(`${day.slice(0, 10)}T00:00:00Z`);

/** Models of a window that has not ended yet are estimated on what is known today. */
export function asOf(windowEnd: string): string {
  const today = new Date().toISOString().slice(0, 10);
  return windowEnd < today ? windowEnd : today;
}
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);

/** "для 2025 года", "для I кв. 2026": the period after a preposition. */
function genitive(data: Evaluation, period: string): string {
  return data.frequency === "A" ? t("acc.yearGen", { period }) : formatPeriod(period);
}

function issued(f: { vintage_date: string; approx: boolean }): string {
  return f.approx ? t("acc.issuedApprox", { month: monthLabel(f.vintage_date) }) : t("acc.issued", { date: formatShortDate(f.vintage_date) });
}

export const AccuracyChart = forwardRef<AccuracyChartHandle, Props>(function AccuracyChart(
  { data, mode, period, series, periodLabel, onSelect }, ref,
) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    if (!box.current) return;
    const instance = echarts.init(box.current, undefined, { renderer: "canvas" });
    chart.current = instance;
    instance.on("click", (params) => {
      const target = (params.data as Point | undefined)?.period;
      if (target) select.current(target);
    });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(box.current);
    return () => { observer.disconnect(); instance.dispose(); chart.current = null; };
  }, []);

  useImperativeHandle(ref, () => ({
    zoomAll: () => chart.current?.dispatchAction({ type: "dataZoom", start: 0, end: 100 }),
    png: (name) => {
      const url = chart.current?.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
      if (!url) return;
      const link = document.createElement("a");
      link.href = url;
      link.download = `${name}.png`;
      link.click();
    },
  }), []);

  useEffect(() => {
    const instance = chart.current;
    if (!instance) return;
    const option = mode === "evolution" ? evolutionOption(data, series, periodLabel) : periodsOption(data, period, series, periodLabel);
    if (option) instance.setOption(option, true);
    else instance.clear();
  }, [data, mode, period, series, periodLabel]);

  return <div ref={box} className="acc-chart" />;
});

const base = {
  animation: false,
  textStyle: { fontFamily: "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif" },
  tooltip: {
    trigger: "item", backgroundColor: "#fff", borderColor: "#cbd5dd", textStyle: { color: "#202a35", fontSize: 12 },
    formatter: (p: { data?: Point }) => p.data?.tip ?? "",
  },
};

function zoom(start?: number) {
  return [
    { type: "inside", filterMode: "none", startValue: start },
    {
      type: "slider", filterMode: "none", bottom: 12, height: 22, startValue: start, borderColor: "#d7dfe7",
      fillerColor: "rgba(8,117,189,.10)", handleStyle: { color: "#0875bd" }, textStyle: { color: "#697583", fontSize: 11 },
      labelFormatter: (v: number) => { const d = new Date(v); return `${SHORT_MONTHS[d.getMonth()]} ${d.getFullYear()}`; },
    },
  ];
}

function timeAxis(min: number, max: number, name?: string) {
  return {
    type: "time", min, max, name, nameLocation: "middle", nameGap: 30, nameTextStyle: { color: "#7a8590", fontSize: 12 },
    axisLabel: {
      color: "#697583", fontSize: 12, hideOverlap: true,
      // ECharts puts ticks at local midnight, so the label is read in local time too.
      formatter: (v: number) => { const d = new Date(v); return d.getMonth() === 0 ? `{y|${d.getFullYear()}}` : SHORT_MONTHS[d.getMonth()]; },
      rich: { y: { fontWeight: 800, color: "#173c68", fontSize: 13 } },
    },
    axisLine: { lineStyle: { color: "#b8c4ce" } }, splitLine: { show: false },
  };
}

const valueAxis = {
  type: "value", scale: true, boundaryGap: ["10%", "10%"],
  axisLabel: { color: "#697583", formatter: (v: number) => formatValue(v, Number.isInteger(v) ? 0 : 1) },
  splitLine: { lineStyle: { color: "#e6ecf0" } },
};

const legend = { top: 0, left: 44, itemGap: 16, textStyle: { color: "#4b5866", fontSize: 12 } };

function bandPair(start: string, end: string, color: string, label: string, textColor: string) {
  return [
    {
      xAxis: start, itemStyle: { color },
      label: { show: true, position: "top", distance: 6, color: textColor, fontWeight: 800, fontSize: 11, lineHeight: 14, formatter: label },
    },
    { xAxis: end },
  ];
}

function contextSeries(data: Evaluation, min: number, max: number): LineSeriesOption | null {
  if (!data.context) return null;
  const points = data.context.points.filter((p) => ms(p.date) >= min - 62 * DAY && ms(p.date) <= max + 62 * DAY);
  return {
    name: t("acc.factContext", { label: data.context.label }), type: "line", symbol: "none", z: 1, silent: true,
    lineStyle: { width: 1.6, color: CONTEXT_COLOR }, itemStyle: { color: CONTEXT_COLOR },
    data: points.map((p) => [p.date, p.value]),
  };
}

/** Where an actual is drawn: the middle of its period, or December of the context line for Dec/Dec. */
const factDay = (data: Evaluation, entry: { period: string; start: string; end: string }) =>
  data.fact_shape === "point" ? `${entry.period.slice(0, 4)}-12-15` : iso((ms(entry.start) + ms(entry.end)) / 2);

function factTip(data: Evaluation, label: string, value: number): string {
  const unit = data.value_unit === "%" ? " %" : ` ${data.value_unit}`;
  return `<b>${t("acc.tipFact")}</b> · ${label}<br>${formatValue(value, 2)}${unit}`;
}

/** Periods view: every forecast stands over the period it is for, next to the actual of that period. */
function periodsOption(data: Evaluation, period: string | null, series: ChartSeries[], periodLabel: (p: string) => string) {
  const rows = data.rows;
  if (!rows.length) return null;
  const entryOf = (p: string) => data.periods.find((x) => x.period === p);
  const first = entryOf(rows[0].period) ?? data.periods[0];
  const last = entryOf(rows[rows.length - 1].period) ?? data.periods[data.periods.length - 1];
  const min = ms(first.start) - 20 * DAY;
  const max = ms(last.end) + 20 * DAY;
  const unit = data.value_unit === "%" ? " %" : ` ${data.value_unit}`;
  const facts = data.periods.filter((p) => p.fact != null && p.period >= rows[0].period && ms(p.start) <= max);
  const out: (LineSeriesOption | ScatterSeriesOption)[] = [];
  const context = contextSeries(data, min, max);
  if (context) out.push(context);
  const selected = period ? entryOf(period) : undefined;
  const window = selected?.windows[data.window];
  const markArea = {
    silent: true,
    data: selected && window ? [
      bandPair(window.start, window.end, "rgba(8,117,189,.08)", t("acc.windowBand", { period: genitive(data, selected.period) }), "#0875bd"),
      bandPair(selected.start, selected.end, "rgba(23,60,104,.07)", periodLabel(selected.period), "#173c68"),
    ] : [],
  } as never;
  const factName = t(`acc.factPeriod${data.frequency}`);
  const factPoints = facts.map((p) => ({ value: [factDay(data, p), p.fact], period: p.period, tip: factTip(data, periodLabel(p.period), p.fact!) }));
  if (data.fact_shape === "segment") {
    out.push({
      name: factName, type: "line", connectNulls: false, symbol: "none", z: 3, lineStyle: { width: 5, color: ACTUAL_COLOR },
      itemStyle: { color: ACTUAL_COLOR }, markArea, silent: true,
      data: facts.flatMap((p) => [[p.start, p.fact], [p.end, p.fact], [p.end, null]]) as never,
    });
    out.push({ name: factName, type: "scatter", symbolSize: 16, z: 2, itemStyle: { color: "rgba(0,0,0,0)" }, data: factPoints as never });
  } else {
    out.push({
      name: factName, type: "scatter", symbolSize: 12, z: 5, itemStyle: { color: ACTUAL_COLOR, borderColor: "#fff", borderWidth: 2 },
      markArea, data: factPoints as never,
    });
  }
  // One slot per series inside a period; for the Dec/Dec point they gather in the last quarter of the year.
  const slot = (target: string, i: number) => {
    const entry = entryOf(target);
    const start = entry ? ms(entry.start) : ms(`${target.slice(0, 4)}-01-01`);
    const end = entry ? ms(entry.end) : start + 365 * DAY;
    const from = data.fact_shape === "point" ? end - 0.25 * (end - start) : start;
    return iso(from + ((i + 1) / (series.length + 1)) * (end - from));
  };
  series.forEach((s, i) => {
    const points = rows.flatMap((row) => {
      const cell = s.model ? row.models[s.key] : row.picks[s.key];
      if (!cell) return [];
      const lines = [`<b>${s.name}</b> · ${t("acc.tipForecast", { period: periodLabel(row.period) })}`];
      lines.push(s.model ? t("acc.tipModel", { date: formatShortDate(asOf(row.window_end)) }) : issued(row.picks[s.key]));
      lines.push(`${formatValue(cell.value, 2)}${unit}`);
      if (row.fact != null && cell.error != null) {
        lines.push(`${t("acc.tipFact")}: ${formatValue(row.fact, 2)}${unit} · ${t("acc.tipError")}: ${signed(cell.error, 1)} ${data.error_unit}`);
      }
      return [{ row, value: cell.value, tip: lines.join("<br>") }];
    });
    out.push({
      name: s.name, type: "scatter", z: 6, symbol: s.model ? "diamond" : "circle", symbolSize: s.model ? 11 : 10,
      itemStyle: { color: s.model ? "#fff" : s.color, borderColor: s.color, borderWidth: s.model ? 2 : 1.5 },
      data: points.map((p) => ({
        value: [slot(p.row.period, i), p.value], period: p.row.period, tip: p.tip,
        itemStyle: p.row.fact == null ? { opacity: 0.45 } : undefined,
      })) as never,
      markLine: {
        silent: true, symbol: "none", label: { show: false },
        lineStyle: { color: s.color, width: s.model ? 1.5 : 2, type: s.model ? "dashed" : "solid" },
        data: points.filter((p) => p.row.fact != null).map((p) => [
          { coord: [slot(p.row.period, i), p.value] }, { coord: [slot(p.row.period, i), p.row.fact] },
        ]) as never,
      },
    });
  });
  // Long quarterly or monthly histories open on the last 12 periods.
  const recent = rows.length > 12 ? entryOf(rows[rows.length - 12].period) : undefined;
  return {
    ...base,
    grid: { left: 54, right: 24, top: 74, bottom: 76 },
    legend,
    dataZoom: zoom(recent ? ms(recent.start) - 20 * DAY : undefined),
    xAxis: timeAxis(min, max),
    yAxis: valueAxis,
    series: out,
  };
}

/** Evolution view: forecasts for one period by publication date, models as known on each date. */
function evolutionOption(data: Evaluation, series: ChartSeries[], periodLabel: (p: string) => string) {
  const ev = data.evolution;
  if (!ev) return null;
  const unit = data.value_unit === "%" ? " %" : ` ${data.value_unit}`;
  const row = data.rows.find((r) => r.period === ev.period);
  const dates = Object.values(ev.tracks).flat().map((f) => ms(f.vintage_date));
  const min = Math.min(ms(ev.window.start), ...dates) - 45 * DAY;
  const max = ms(ev.end) + 45 * DAY;
  const out: (LineSeriesOption | ScatterSeriesOption)[] = [];
  const context = contextSeries(data, min, max);
  if (context) out.push(context);
  const label = periodLabel(ev.period);
  const markArea = {
    silent: true,
    data: [
      bandPair(ev.window.start, ev.window.end, "rgba(8,117,189,.08)", t("acc.windowBand", { period: genitive(data, ev.period) }), "#0875bd"),
      bandPair(ev.start, ev.end, "rgba(23,60,104,.07)", label, "#173c68"),
    ],
  } as never;
  const factName = t(`acc.factPeriod${data.frequency}`);
  if (ev.fact != null && data.fact_shape === "segment") {
    out.push({
      name: factName, type: "line", symbol: "none", z: 3, lineStyle: { width: 5, color: ACTUAL_COLOR }, itemStyle: { color: ACTUAL_COLOR },
      data: [[ev.start, ev.fact], [ev.end, ev.fact]], markArea, silent: true,
    });
  } else {
    out.push({
      name: factName, type: "scatter", symbolSize: 12, z: 5, itemStyle: { color: ACTUAL_COLOR, borderColor: "#fff", borderWidth: 2 },
      data: (ev.fact != null ? [{ value: [factDay(data, ev), ev.fact], tip: factTip(data, label, ev.fact) }] : []) as never, markArea,
    });
  }
  const withTail = (points: Point[], last: number | null) => (last != null && points.length && points[points.length - 1].value[0] < ev.end
    ? [...points, { value: [ev.end, last] as [string, number], symbolSize: 0 }] : points);
  for (const s of series) {
    if (s.model) {
      const path = ev.models[s.key] ?? [];
      const points: Point[] = path.map((p) => ({
        value: [p.date, p.value],
        tip: `<b>${s.name}</b> · ${t("acc.tipForecast", { period: label })}<br>${t("acc.tipModel", { date: formatShortDate(p.date) })}<br>${formatValue(p.value, 2)}${unit}`,
      }));
      const pick = row?.models[s.key];
      out.push({
        name: s.name, type: "line", step: "end", z: 4, symbol: "circle", symbolSize: 3,
        lineStyle: { width: 2, color: s.color, type: [6, 5] }, itemStyle: { color: s.color },
        data: withTail(points, path.length ? path[path.length - 1].value : null) as never,
        markLine: pick && ev.fact != null ? {
          silent: true, symbol: "none", label: { show: false }, lineStyle: { color: s.color, type: "dashed", width: 1.5 },
          data: [[{ coord: [ev.window.end, pick.value] }, { coord: [ev.window.end, ev.fact] }]] as never,
        } : undefined,
      });
      if (pick) {
        out.push({
          name: s.name, type: "scatter", symbol: "diamond", symbolSize: 13, z: 7,
          itemStyle: { color: "#fff", borderColor: s.color, borderWidth: 2.5 },
          data: [{
            value: [ev.window.end, pick.value],
            tip: `<b>${s.name}</b> · ${t("acc.tipForecast", { period: label })}<br>${t("acc.tipModel", { date: formatShortDate(ev.window.end) })}<br>${formatValue(pick.value, 2)}${unit}`,
          }] as never,
        });
      }
      continue;
    }
    const track: EvalForecast[] = ev.tracks[s.key] ?? [];
    const points: Point[] = track.map((f) => ({
      value: [f.vintage_date, f.value],
      tip: `<b>${s.name}</b> · ${t("acc.tipForecast", { period: label })}<br>${f.title} · ${issued(f)}<br>${formatValue(f.value, 2)}${unit}`,
    }));
    const pick = row?.picks[s.key];
    out.push({
      name: s.name, type: "line", step: "end", z: 4, symbol: "circle", symbolSize: 6,
      lineStyle: { width: 2.5, color: s.color }, itemStyle: { color: s.color },
      data: withTail(points, track.length ? track[track.length - 1].value : null) as never,
      markLine: pick && ev.fact != null ? {
        silent: true, symbol: "none", label: { show: false }, lineStyle: { color: s.color, type: "dashed", width: 1.5 },
        data: [[{ coord: [pick.vintage_date, pick.value] }, { coord: [pick.vintage_date, ev.fact] }]] as never,
      } : undefined,
    });
    if (pick) {
      out.push({
        name: s.name, type: "scatter", symbolSize: 14, z: 7, itemStyle: { color: s.color, borderColor: "#fff", borderWidth: 3 },
        data: [{ value: [pick.vintage_date, pick.value], tip: points.find((p) => p.value[0] === pick.vintage_date)?.tip }] as never,
      });
    }
  }
  return {
    ...base,
    grid: { left: 54, right: 24, top: 74, bottom: 96 },
    legend,
    dataZoom: zoom(),
    xAxis: timeAxis(min, max, t("acc.xAxis")),
    yAxis: valueAxis,
    series: out,
  };
}
