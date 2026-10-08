import { useEffect, useState } from "react";
import { api } from "../api";
import { formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { Evaluation, Frequency } from "../types";

export function Accuracy({ id, frequency, precision }: { id: string; frequency: Frequency; precision: number }) {
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(null);
    api.evaluation(id, frequency).then((d) => { if (active) setData(d); }).catch((e: Error) => setError(e.message));
    return () => { active = false; };
  }, [id, frequency]);

  if (error) return <div className="inline-error">{error}</div>;
  if (!data) return <div className="loading-panel loading-panel--small"><span className="loading-spinner" />{t("common.loading")}</div>;
  const withErrors = data.sources.filter((s) => s.releases.length);
  const maxMae = Math.max(0.0001, ...withErrors.flatMap((s) => s.horizons.map((h) => h.mae)));

  return (
    <section className="evaluation-panel">
      <div className="section-heading">
        <div><p className="eyebrow">{t("acc.eyebrow")}</p><h2>{t("acc.title")}</h2></div>
        <p>{t("acc.text")}</p>
      </div>
      {!withErrors.length && <div className="empty-evaluation"><span>◷</span><p>{t("acc.empty")}</p></div>}
      <div className="accuracy-grid">
        {withErrors.map((s) => (
          <article key={s.source_id} className="accuracy-card">
            <header><i style={{ background: s.color }} /><b>{s.short}</b><small>{s.name}</small></header>
            <table className="accuracy-bars">
              <thead><tr><th>{t("acc.horizon")}</th><th>{t("acc.mae")}</th><th>{t("acc.bias")}</th><th>{t("acc.n")}</th></tr></thead>
              <tbody>
                {s.horizons.map((h) => (
                  <tr key={h.horizon}>
                    <td>{horizonLabel(h.horizon, frequency)}</td>
                    <td>
                      <span className="bar"><span style={{ width: `${(h.mae / maxMae) * 100}%`, background: s.color }} /></span>
                      {formatValue(h.mae, precision)}
                    </td>
                    <td className={h.bias > 0 ? "is-up" : h.bias < 0 ? "is-down" : ""}>{h.bias > 0 ? "+" : ""}{formatValue(h.bias, precision)}</td>
                    <td>{h.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <details>
              <summary>{t("acc.releases")} ({s.releases.length})</summary>
              <table className="data-table evaluation-table">
                <thead><tr><th>{t("acc.release")}</th><th>{t("acc.points")}</th><th>MAE</th><th>{t("acc.rmse")}</th><th>{t("acc.bias")}</th></tr></thead>
                <tbody>
                  {[...s.releases].reverse().map((r) => (
                    <tr key={r.release_id}>
                      <td>{r.title}<small>{formatShortDate(r.vintage_date)}</small></td>
                      <td>{r.points.length}</td>
                      <td>{formatValue(r.mae, precision)}</td>
                      <td>{formatValue(r.rmse, precision)}</td>
                      <td>{r.bias > 0 ? "+" : ""}{formatValue(r.bias, precision)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}

const UNITS: Record<Frequency, [string, string, string]> = {
  A: ["год", "года", "лет"], Q: ["квартал", "квартала", "кварталов"], M: ["месяц", "месяца", "месяцев"],
};

function plural(n: number, [one, few, many]: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function horizonLabel(h: number, frequency: Frequency): string {
  if (h <= 0) return t(`acc.current${frequency}`);
  return t("acc.ahead", { n: h, unit: plural(h, UNITS[frequency]) });
}
