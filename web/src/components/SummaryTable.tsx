import { useMemo, useState } from "react";
import { api } from "../api";
import { formatPeriod, formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { ChartLine } from "../lines";
import type { SeriesResponse } from "../types";

type Mode = "values" | "devActual" | "devBase";

interface Props {
  lines: ChartLine[];
  periods: string[];
  data: SeriesResponse;
  precision: number;
  exportName: string;
}

/** Revision of the forecast for `period` against the previous release of the same source. */
function revisions(data: SeriesResponse, period: string): Map<string, number> {
  const result = new Map<string, number>();
  for (const source of data.sources) {
    source.releases.forEach((release, i) => {
      if (i === 0) return;
      const now = release.points.find((p) => p.period === period)?.value;
      const before = source.releases[i - 1].points.find((p) => p.period === period)?.value;
      if (now != null && before != null) result.set(`r:${release.release_id}`, now - before);
    });
  }
  return result;
}

export function SummaryTable({ lines, periods, data, precision, exportName }: Props) {
  const [mode, setMode] = useState<Mode>("values");
  const [base, setBase] = useState("");
  const [error, setError] = useState("");

  const values = useMemo(() => new Map(lines.map((l) => [l.key, new Map(l.points.map((p) => [p.period, p]))])), [lines]);
  const fact = values.get("actual");
  const lastFact = lines.find((l) => l.kind === "actual")?.points.at(-1)?.period ?? null;
  // Columns: two actual periods before the forecasts and every period with a forecast.
  const columns = periods.filter((p) => {
    if (!lastFact) return true;
    if (p > lastFact) return lines.some((l) => l.kind !== "actual" && values.get(l.key)?.has(p));
    return p >= periods[Math.max(0, periods.indexOf(lastFact) - 2)];
  });
  const focus = columns.find((p) => !lastFact || p > lastFact) ?? null;
  const revision = useMemo(() => (focus ? revisions(data, focus) : new Map<string, number>()), [data, focus]);
  const reference = mode === "devActual" ? fact : mode === "devBase" ? values.get(base) : undefined;

  const cell = (key: string, period: string): number | null => {
    const v = values.get(key)?.get(period)?.value;
    if (v == null) return null;
    if (mode === "values") return v;
    const ref = reference?.get(period)?.value;
    return ref == null ? null : v - ref;
  };

  const ordered = [...lines].sort((a, b) => {
    const rank = (l: ChartLine) => (l.kind === "actual" ? 0 : l.kind === "release" ? 1 : 2);
    return rank(a) - rank(b) || (b.vintage ?? "").localeCompare(a.vintage ?? "");
  });

  async function exportAs(format: "csv" | "xlsx") {
    setError("");
    try {
      await api.export(
        exportName,
        [t("table.series"), t("table.vintage"), ...columns.map(formatPeriod)],
        ordered.map((l) => [l.label, l.vintage ?? "", ...columns.map((p) => {
          const v = cell(l.key, p);
          return v == null ? null : Number(v.toFixed(Math.max(precision, 2)));
        })]),
        format,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="comparison-table-section">
      <div className="section-heading section-heading--compact">
        <div>
          <p className="eyebrow">{t("table.summaryEyebrow")}</p>
          <h2>{t("table.summaryTitle")}</h2>
        </div>
        <p>{t("table.summaryHint")}</p>
      </div>
      <div className="table-toolbar">
        <div className="segmented">
          {(["values", "devActual", "devBase"] as Mode[]).map((m) => (
            <button key={m} type="button" className={mode === m ? "is-active" : ""} onClick={() => setMode(m)}>
              {t(`table.${m}`)}
            </button>
          ))}
        </div>
        {mode === "devBase" && (
          <select className="select" value={base} onChange={(e) => setBase(e.target.value)}>
            <option value="">{t("table.base")}</option>
            {ordered.map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
          </select>
        )}
        <span className="table-toolbar__spacer" />
        <button type="button" className="icon-button" onClick={() => void exportAs("csv")}>↓ CSV</button>
        <button type="button" className="icon-button" onClick={() => void exportAs("xlsx")}>↓ XLSX</button>
      </div>
      {error && <div className="inline-error">{error}</div>}
      <div className="table-scroll">
        <table className="data-table summary-table">
          <thead>
            <tr>
              <th>{t("table.series")}</th>
              {columns.map((p) => <th key={p} className={lastFact && p > lastFact ? "is-forecast" : ""}>{formatPeriod(p)}</th>)}
              {focus && <th title={t("table.revisionHint")}>{t("table.revision", { period: formatPeriod(focus) })}</th>}
            </tr>
          </thead>
          <tbody>
            {ordered.map((l) => (
              <tr key={l.key} className={l.kind === "actual" ? "is-actual" : ""}>
                <td>
                  <span className="row-swatch" style={{ background: l.color, borderTop: l.kind === "model" ? "2px dashed" : undefined }} />
                  <b>{l.label}</b>
                  {l.vintage && <small>{formatShortDate(l.vintage)}</small>}
                </td>
                {columns.map((p) => {
                  const v = cell(l.key, p);
                  const point = values.get(l.key)?.get(p);
                  const range = mode === "values" && point?.lower != null && point?.upper != null
                    ? `${formatValue(point.lower, precision)}–${formatValue(point.upper, precision)}` : null;
                  const sign = mode !== "values" && v != null && v > 0 ? "+" : "";
                  const tone = mode !== "values" && v != null ? (v > 0 ? "is-up" : v < 0 ? "is-down" : "") : "";
                  return (
                    <td key={p} className={tone}>
                      {v == null ? "" : `${sign}${formatValue(v, precision)}`}
                      {range && <small>{range}</small>}
                    </td>
                  );
                })}
                {focus && (
                  <td className={revision.get(l.key) ? (revision.get(l.key)! > 0 ? "is-up" : "is-down") : ""}>
                    {revision.has(l.key) ? `${revision.get(l.key)! > 0 ? "▲ +" : revision.get(l.key)! < 0 ? "▼ " : ""}${formatValue(revision.get(l.key)!, precision)}` : ""}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
