import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { formatShortDate } from "../format";
import { t } from "../i18n";
import type { RegistrySource } from "../types";

export function SourcesView() {
  const [sources, setSources] = useState<RegistrySource[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "forecast" | "actual">("all");
  const [query, setQuery] = useState("");
  useEffect(() => { api.sources().then(setSources).catch((e: Error) => setError(e.message)); }, []);

  const filtered = useMemo(() => (sources ?? []).filter((s) => {
    const text = [s.organization, s.short, s.name, ...s.indicators].join(" ").toLocaleLowerCase("ru-RU");
    return (filter === "all" || s.role === filter) && text.includes(query.trim().toLocaleLowerCase("ru-RU"));
  }), [sources, filter, query]);

  if (error) return <main className="page-shell"><div className="inline-error">{error}</div></main>;
  if (!sources) return <main className="page-shell"><div className="loading-panel"><span className="loading-spinner" />{t("common.loading")}</div></main>;
  const forecasts = sources.filter((s) => s.role === "forecast");

  return (
    <main className="page-shell sources-page">
      <section className="sources-hero">
        <div><p className="eyebrow">{t("src.eyebrow")}</p><h1>{t("src.title")}</h1><p>{t("src.lead")}</p></div>
        <div className="sources-hero__numbers">
          <div><strong>{forecasts.length}</strong><span>{t("src.forecasts")}</span></div>
          <div><strong>{sources.length - forecasts.length}</strong><span>{t("src.facts")}</span></div>
          <div><strong>{forecasts.reduce((n, s) => n + s.releases, 0)}</strong><span>{t("common.releases")}</span></div>
        </div>
      </section>

      <section className="source-toolbar">
        <label className="search-field"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("src.search")} /></label>
        <div className="source-filter-tabs">
          {(["all", "forecast", "actual"] as const).map((f) => (
            <button type="button" key={f} className={filter === f ? "is-active" : ""} onClick={() => setFilter(f)}>
              {{ all: t("src.all"), forecast: t("src.forecasts"), actual: t("src.facts") }[f]}
            </button>
          ))}
        </div>
      </section>

      <section className="source-directory">
        {filtered.map((s) => (
          <article className="source-record" key={s.source_id}>
            <div className="source-record__identity">
              <span className={`source-status source-status--${s.role === "forecast" ? "connected" : "ready"}`}>
                {s.role === "forecast" ? t("src.forecast") : t("src.actual")}
              </span>
              <h2><i className="source-dot" style={{ background: s.color }} />{s.short}</h2>
              <strong>{s.organization} · {s.name}</strong>
              <p>{s.description}</p>
              {s.caveat && <p className="source-record__caveat">{s.caveat}</p>}
            </div>
            <dl className="source-record__facts">
              <div><dt>{t("src.indicators")}</dt><dd>{s.indicators.join(", ")}</dd></div>
              <div><dt>{t("src.releases")}</dt><dd>{s.releases}</dd></div>
              <div><dt>{t("src.period")}</dt><dd>{formatShortDate(s.first_vintage)} — {formatShortDate(s.last_vintage)}</dd></div>
              <div><dt>{t("src.access")}</dt><dd>{s.access}</dd></div>
              <div><dt>{t("src.license")}</dt><dd>{s.license}</dd></div>
            </dl>
            <div className="source-record__action">
              <span className="source-status source-status--connected">{t("src.connected")}</span>
              <a href={s.url} target="_blank" rel="noreferrer">{t("src.official")}</a>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
