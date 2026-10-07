import { useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDate, formatNumber, formatPeriod } from "../format";
import { t } from "../i18n";
import type { SeriesDef } from "../series";

interface Props {
  series: SeriesDef[];
  periods: string[];
  hidden: Set<string>;
  onToggle: (key: string) => void;
  showIntervals: boolean;
  unit: string;
  precision: number;
}

type Row = Record<string, string | number | [number, number] | null>;

function ChartTooltip({ active, label, rows, series, unit, precision }: {
  active?: boolean; label?: string | number; rows: Map<string, Row>; series: SeriesDef[]; unit: string; precision: number;
}) {
  if (!active || label == null) return null;
  const row = rows.get(String(label));
  if (!row) return null;
  const entries = series.filter((s) => typeof row[s.key] === "number");
  if (!entries.length) return null;
  return (
    <div className="tooltip">
      <strong>{t("chart.period")}: {formatPeriod(String(label))}</strong>
      {entries.map((s) => (
        <div className="tooltip__row" key={s.key}>
          <i style={{ background: s.color }} />
          <span>
            {s.label}
            {s.vintage && <small>{t("chart.vintage")}: {formatDate(s.vintage)}</small>}
          </span>
          <b>{formatNumber(row[s.key] as number, precision)} <small>{unit}</small></b>
        </div>
      ))}
    </div>
  );
}

export function ForecastChart({ series, periods, hidden, onToggle, showIntervals, unit, precision }: Props) {
  const rows = useMemo(() => {
    const map = new Map<string, Row>(periods.map((p) => [p, { period: p }]));
    for (const s of series) {
      for (const p of s.points) {
        const row = map.get(p.period);
        if (!row) continue;
        row[s.key] = p.value;
        if (p.lower != null && p.upper != null) row[`${s.key}__band`] = [p.lower, p.upper];
      }
    }
    return map;
  }, [series, periods]);
  const data = useMemo(() => periods.map((p) => rows.get(p)!), [periods, rows]);
  const visible = series.filter((s) => !hidden.has(s.key));
  const values = visible.flatMap((s) => s.points.filter((p) => rows.has(p.period)).map((p) => p.value));
  const span = values.length ? Math.max(...values) - Math.min(...values) : 0;
  const tickDigits = span >= 20 ? 0 : span >= 2 ? 1 : 2;

  if (!periods.length) return <p className="muted">{t("chart.noData")}</p>;

  return (
    <>
      <div className="legend">
        {series.map((s) => (
          <button key={s.key} type="button" className={hidden.has(s.key) ? "is-hidden" : ""} onClick={() => onToggle(s.key)}
            title={s.sublabel}>
            <i className={s.dashed ? "dashed" : ""} style={{ borderColor: hidden.has(s.key) ? "#d0d0d2" : s.color }} />
            {s.label}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={480}>
        <ComposedChart data={data} margin={{ top: 12, right: 16, left: 4, bottom: 4 }}>
          <CartesianGrid stroke="#e5e5e6" vertical={false} />
          <XAxis dataKey="period" tickFormatter={(v) => formatPeriod(String(v))} minTickGap={40}
            tick={{ fill: "#68686e", fontSize: 12 }} />
          <YAxis width={56} tick={{ fill: "#68686e", fontSize: 12 }} domain={["auto", "auto"]}
            tickFormatter={(v) => formatNumber(Number(v), tickDigits)} />
          <Tooltip content={(props) => (
            <ChartTooltip active={props.active} label={props.label as string} rows={rows} series={visible}
              unit={unit} precision={precision} />
          )} />
          {showIntervals && visible.filter((s) => s.kind !== "actual").map((s) => (
            <Area key={`${s.key}__band`} dataKey={`${s.key}__band`} stroke="none" fill={s.color}
              fillOpacity={s.kind === "model" ? 0.08 : 0.12} connectNulls isAnimationActive={false} legendType="none" />
          ))}
          {visible.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color} isAnimationActive={false}
              strokeWidth={s.kind === "actual" ? 3.5 : s.kind === "model" ? 2 : 2.25}
              strokeDasharray={s.dashed ? "6 4" : undefined}
              dot={s.points.length <= 2 ? { r: 3 } : false} connectNulls={s.kind !== "actual"} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
