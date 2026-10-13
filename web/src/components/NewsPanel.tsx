import { useEffect, useRef } from "react";
import { LineChart, type LineSeriesOption } from "echarts/charts";
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import { ACTUAL_COLOR } from "../colors";
import { formatDate, formatMonthLong, formatPeriod, formatValue } from "../format";
import { t } from "../i18n";
import type { NewsBlock } from "../types";

echarts.use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, LabelLayout, CanvasRenderer]);

interface Props {
  news: NewsBlock;
  onOpen: () => void;
}

/** Start page announcement of a new indicator: the newest release of each source against the actuals. */
export function NewsPanel({ news, onOpen }: Props) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!box.current) return;
    const instance = echarts.init(box.current, undefined, { renderer: "canvas" });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(box.current);
    const fact = news.fact?.points ?? [];
    const periods = [...new Set([...fact, ...news.lines.flatMap((l) => l.points)].map((p) => p.period))].sort();
    const at = (points: { period: string; value: number }[]) => {
      const values = new Map(points.map((p) => [p.period, p.value]));
      return periods.map((p) => values.get(p) ?? null);
    };
    const lastFact = fact.length ? fact[fact.length - 1].period : null;
    const percent = news.unit.startsWith("%");
    const series: LineSeriesOption[] = [
      {
        name: news.fact?.short ?? t("chart.fact"), type: "line", data: at(fact), symbol: "none", z: 3,
        lineStyle: { width: 3.5, color: ACTUAL_COLOR }, color: ACTUAL_COLOR,
        ...(lastFact ? {
          markLine: {
            silent: true, symbol: "none", lineStyle: { color: "#9aa8b5", type: "dashed" as const },
            label: { formatter: t("chart.lastFact", { period: formatPeriod(lastFact) }), color: "#697583", fontSize: 11 },
            data: [{ xAxis: lastFact }],
          },
          markArea: periods.indexOf(lastFact) < periods.length - 1 ? {
            silent: true, itemStyle: { color: "rgba(23, 60, 104, 0.04)" },
            data: [[{ xAxis: periods[periods.indexOf(lastFact) + 1] }, { xAxis: periods[periods.length - 1] }]],
          } : undefined,
        } : {}),
      },
      ...news.lines.map((line): LineSeriesOption => ({
        name: line.short, type: "line", data: at(line.points), connectNulls: true, symbol: "none", z: 2,
        lineStyle: { width: 2.6, color: line.color }, color: line.color,
        endLabel: {
          show: true, color: line.color, fontWeight: 650, fontSize: 12,
          formatter: (p) => `${line.short}  ${formatValue(p.value as number, news.precision)}`,
        },
        labelLayout: { moveOverlap: "shiftY" },
      })),
    ];
    instance.setOption({
      animation: false,
      grid: { left: 8, right: 130, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "axis", confine: true, textStyle: { fontSize: 12 },
        valueFormatter: (v: unknown) => (v == null ? "—" : formatValue(v as number, news.precision)),
        axisPointer: { lineStyle: { color: "#9aa8b5" } },
      },
      xAxis: {
        type: "category", data: periods, boundaryGap: false, axisTick: { show: false },
        axisLine: { lineStyle: { color: "#c9d3dc" } },
        axisLabel: { interval: 0, color: "#65717f", formatter: (v: string) => (v.endsWith("Q1") ? v.slice(0, 4) : "") },
      },
      yAxis: {
        type: "value", scale: true, splitLine: { lineStyle: { color: "#e5ebf0" } },
        axisLabel: { color: "#65717f", formatter: (v: number) => `${formatValue(v, 1)}${percent ? "%" : ""}` },
      },
      series,
    });
    return () => { observer.disconnect(); instance.dispose(); };
  }, [news]);

  return (
    <aside className="news-panel" aria-label={news.title}>
      <span className="news-panel__badge"><i />{t("news.badge", { date: formatDate(news.published) })}</span>
      <h2>{news.title}</h2>
      <p>{news.text}</p>
      <div className="news-legend">
        {news.fact && <span><i style={{ background: ACTUAL_COLOR }} />{news.fact.short}</span>}
        {news.lines.map((l) => (
          <span key={l.source_id}><i style={{ background: l.color }} />{t("news.release", { source: l.short, month: formatMonthLong(l.vintage_date) })}</span>
        ))}
      </div>
      <div ref={box} className="news-panel__chart" role="img" aria-label={news.title} />
      <div className="news-panel__foot">
        <small>{news.unit}{news.fact ? ` · ${news.fact.short}` : ""}</small>
        <button className="button button--primary" type="button" onClick={onOpen}>{t("news.open")}</button>
      </div>
    </aside>
  );
}
