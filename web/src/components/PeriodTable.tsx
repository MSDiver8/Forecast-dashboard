import { formatPeriod, formatValue } from "../format";
import { t } from "../i18n";
import type { ChartLine } from "../lines";

export function PeriodTable({ lines, periods, precision }: { lines: ChartLine[]; periods: string[]; precision: number }) {
  const values = new Map(lines.map((l) => [l.key, new Map(l.points.map((p) => [p.period, p.value]))]));
  const rows = [...periods].reverse();
  return (
    <details className="period-table">
      <summary>{t("table.periodsTitle")}</summary>
      <div className="table-scroll table-scroll--tall">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("table.period")}</th>
              {lines.map((l) => (
                <th key={l.key}>
                  <span className="row-swatch" style={{ background: l.color }} />{l.group}
                  {l.vintage && <small>{l.label.split(" · ").slice(1).join(" · ")}</small>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p}>
                <td>{formatPeriod(p)}</td>
                {lines.map((l) => {
                  const v = values.get(l.key)?.get(p);
                  return <td key={l.key}>{v == null ? "—" : formatValue(v, precision)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
