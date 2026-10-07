import { useMemo, useState } from "react";
import { api } from "../api";
import { formatDate, formatNumber, formatPeriod } from "../format";
import { t } from "../i18n";
import type { SeriesDef } from "../series";

type Mode = "values" | "devActual" | "devSeries";

interface Props {
  series: SeriesDef[];
  periods: string[];
  precision: number;
  title: string;
}

export function DataTable({ series, periods, precision, title }: Props) {
  const [mode, setMode] = useState<Mode>("values");
  const [baseKey, setBaseKey] = useState<string>("");
  const [sort, setSort] = useState<{ period: string; dir: 1 | -1 } | null>(null);
  const [error, setError] = useState("");

  const values = useMemo(() => {
    const map = new Map<string, Map<string, number>>();
    for (const s of series) map.set(s.key, new Map(s.points.map((p) => [p.period, p.value])));
    return map;
  }, [series]);

  const columns = periods.filter((p) => series.some((s) => values.get(s.key)?.has(p)));
  const reference = mode === "devActual" ? values.get("actual") : mode === "devSeries" ? values.get(baseKey) : undefined;

  const cell = (key: string, period: string): number | null => {
    const v = values.get(key)?.get(period);
    if (v == null) return null;
    if (mode === "values") return v;
    const ref = reference?.get(period);
    return ref == null ? null : v - ref;
  };

  const actualRow = series.find((s) => s.kind === "actual");
  let rows = series.filter((s) => s.kind !== "actual");
  if (sort) {
    rows = [...rows].sort((a, b) => {
      const va = cell(a.key, sort.period);
      const vb = cell(b.key, sort.period);
      if (va == null) return 1;
      if (vb == null) return -1;
      return (va - vb) * sort.dir;
    });
  }
  const ordered = actualRow ? [actualRow, ...rows] : rows;

  const toggleSort = (period: string) =>
    setSort((s) => (s?.period === period ? (s.dir === 1 ? { period, dir: -1 } : null) : { period, dir: 1 }));

  async function exportAs(format: "csv" | "xlsx") {
    setError("");
    try {
      await api.export(
        title,
        [t("table.series"), t("chart.vintage"), ...columns.map(formatPeriod)],
        ordered.map((s) => [s.label, s.vintage ?? "", ...columns.map((p) => {
          const v = cell(s.key, p);
          return v == null ? null : Number(v.toFixed(Math.max(precision, 2)));
        })]),
        format,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="card table-card">
      <div className="table-tools">
        <h2 className="panel-title" style={{ margin: 0 }}>{t("table.title")}</h2>
        <div className="row" style={{ flex: "0 1 auto", gap: 12 }}>
          <div className="segmented" style={{ minWidth: 460 }}>
            {(["values", "devActual", "devSeries"] as Mode[]).map((m) => (
              <button key={m} type="button" className={mode === m ? "is-active" : ""} onClick={() => setMode(m)}>
                {t(`table.${m}`)}
              </button>
            ))}
          </div>
          {mode === "devSeries" && (
            <select className="select" style={{ width: 260 }} value={baseKey} onChange={(e) => setBaseKey(e.target.value)}>
              <option value="">{t("table.base")}</option>
              {series.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          )}
          <button type="button" className="btn btn--small" onClick={() => void exportAs("csv")}>{t("table.csv")}</button>
          <button type="button" className="btn btn--small" onClick={() => void exportAs("xlsx")}>{t("table.xlsx")}</button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr>
              <th>{t("table.series")}</th>
              {columns.map((p) => (
                <th key={p} onClick={() => toggleSort(p)}>
                  {formatPeriod(p)}{sort?.period === p ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordered.map((s) => (
              <tr key={s.key} className={s.kind === "actual" ? "is-actual" : ""}>
                <td>
                  <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: s.color, marginRight: 8 }} />
                  {s.label}
                  {s.vintage && <small>{t("chart.vintage")}: {formatDate(s.vintage)}</small>}
                </td>
                {columns.map((p) => {
                  const v = cell(s.key, p);
                  const cls = mode !== "values" && v != null ? (v > 0 ? "pos" : v < 0 ? "neg" : "") : "";
                  return <td key={p} className={cls}>{v == null ? "" : `${mode !== "values" && v > 0 ? "+" : ""}${formatNumber(v, precision)}`}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
