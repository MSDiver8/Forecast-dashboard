import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDate } from "../format";
import { t } from "../i18n";
import type { StatusData } from "../types";

export function StatusView() {
  const [data, setData] = useState<StatusData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.status().then(setData).catch((e: Error) => setError(e.message)); }, []);
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">{t("common.loading")}</p>;
  return (
    <section>
      <h2 className="panel-title">{t("status.sources")}</h2>
      <div className="table-scroll" style={{ marginBottom: 32 }}>
        <table className="plain">
          <thead>
            <tr>
              <th>{t("filters.sources")}</th><th>{t("status.role")}</th><th>{t("status.releases")}</th>
              <th>{t("status.first")}</th><th>{t("status.last")}</th>
            </tr>
          </thead>
          <tbody>
            {data.sources.map((s) => (
              <tr key={s.source_id}>
                <td><b>{s.organization}</b> · <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a><br />
                  <span className="muted">{s.source_id} · {s.license}</span></td>
                <td>{s.role === "actual" ? t("status.roleActual") : t("status.roleForecast")}</td>
                <td>{s.releases}</td>
                <td>{formatDate(s.first_vintage)}</td>
                <td>{formatDate(s.last_vintage)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2 className="panel-title">{t("status.log")}</h2>
      <div className="table-scroll">
        <table className="plain">
          <thead>
            <tr><th>{t("status.started")}</th><th>{t("filters.sources")}</th><th>{t("status.result")}</th>
              <th>{t("status.releases")}</th><th>{t("status.rows")}</th><th>{t("status.error")}</th></tr>
          </thead>
          <tbody>
            {data.log.map((l, i) => (
              <tr key={i}>
                <td>{l.started_at.replace("T", " ").slice(0, 19)}</td>
                <td>{l.source_id}</td>
                <td className={l.status === "ok" ? "status-ok" : "status-error"}>{l.status}</td>
                <td>{l.releases ?? ""}</td>
                <td>{l.rows_added ?? ""}</td>
                <td style={{ maxWidth: 520, whiteSpace: "normal" }}>{l.error ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
