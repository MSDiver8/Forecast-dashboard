import { formatPeriod, formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { Overview } from "../types";
import { IndicatorPicker } from "./IndicatorPicker";
import { Sparkline } from "./Sparkline";

interface Props {
  overview: Overview;
  onOpenIndicator: (id: string) => void;
  onOpenSources: () => void;
}

export function IndicatorOverview({ overview, onOpenIndicator, onOpenSources }: Props) {
  const { cards, totals } = overview;
  return (
    <main className="page-shell overview-page">
      <section className="overview-hero">
        <div className="overview-hero__copy">
          <p className="eyebrow">{t("overview.eyebrow")}</p>
          <h1>{t("app.title")}</h1>
          <p>{t("overview.lead")}</p>
          <div className="overview-hero__actions">
            <IndicatorPicker items={cards} onSelect={onOpenIndicator} variant="primary" />
            <button className="button button--outline" type="button" onClick={onOpenSources}>{t("overview.registry")}</button>
          </div>
        </div>
        <aside className="forecast-preview" aria-label={t("preview.title")}>
          <div className="forecast-preview__head"><span>{t("preview.eyebrow")}</span><b>{t("preview.title")}</b></div>
          <svg viewBox="0 0 620 300" role="img" aria-label={t("preview.title")}>
            <g className="forecast-preview__grid"><line x1="46" y1="55" x2="596" y2="55" /><line x1="46" y1="128" x2="596" y2="128" /><line x1="46" y1="201" x2="596" y2="201" /><line x1="46" y1="264" x2="596" y2="264" /></g>
            <path className="forecast-preview__zone" d="M310 35 H596 V270 H310 Z" />
            <line className="forecast-preview__cutoff" x1="310" y1="35" x2="310" y2="270" />
            <path className="forecast-preview__actual" d="M46 184 C82 166 101 202 132 173 S188 112 216 145 S260 217 310 153" />
            <path className="forecast-preview__forecast forecast-preview__forecast--one" d="M310 153 C366 132 430 111 596 85" />
            <path className="forecast-preview__forecast forecast-preview__forecast--two" d="M310 153 C372 174 466 187 596 215" />
            <path className="forecast-preview__band" d="M310 153 C380 150 482 140 596 120 L596 196 C482 182 380 165 310 153 Z" />
            <path className="forecast-preview__model" d="M310 153 C380 149 482 160 596 158" />
            <text x="318" y="52" className="forecast-preview__label">{t("chart.forecasts")}</text>
          </svg>
          <div className="forecast-preview__legend">
            <span><i className="is-actual" />{t("preview.actual")}</span>
            <span><i className="is-source" />{t("preview.source")}</span>
            <span><i className="is-model" />{t("preview.model")}</span>
          </div>
          <p className="forecast-preview__note">{t("preview.note")}</p>
        </aside>
      </section>

      <section className="overview-index" aria-label={t("overview.sectionTitle")}>
        <div><strong>{totals.indicators}</strong><span>{t("overview.indicators")}</span></div>
        <div><strong>{totals.sources}</strong><span>{t("overview.forecastSources")}</span></div>
        <div><strong>{totals.releases}</strong><span>{t("overview.releases")}</span></div>
        <div><strong>{formatShortDate(totals.last_update)}</strong><span>{t("overview.updated")}</span></div>
        <button type="button" onClick={onOpenSources}><span>{t("src.eyebrow")}</span><b>{t("overview.registry")} →</b></button>
      </section>

      <section className="section-heading" id="indicator-list">
        <div><p className="eyebrow">{t("overview.sectionEyebrow")}</p><h2>{t("overview.sectionTitle")}</h2></div>
        <p>{t("overview.sectionText")}</p>
      </section>

      <section className="indicator-grid">
        {cards.map((card, index) => {
          const target = card.targets[0];
          const values = card.latest
            .map((l) => ({ ...l, point: target ? l.values[target] : null }))
            .filter((l) => l.point)
            .sort((a, b) => b.point!.value - a.point!.value);
          return (
            <button className="indicator-card" type="button" key={card.id} onClick={() => onOpenIndicator(card.id)}>
              <span className="indicator-card__number">{String(index + 1).padStart(2, "0")}</span>
              <span className="indicator-card__category">{card.category}</span>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <div className="indicator-card__fact">
                <div>
                  <small>{t("overview.fact")} {card.last_fact ? formatPeriod(card.last_fact.period) : ""}</small>
                  <strong>{card.last_fact ? formatValue(card.last_fact.value, card.precision) : "—"}</strong>
                  <em>{card.unit}</em>
                </div>
                <Sparkline values={card.sparkline.map((p) => p.value)} />
              </div>
              {target && (
                <div className="indicator-card__forecasts">
                  <small>{t("overview.forecastsFor", { period: formatPeriod(target) })}</small>
                  <ul>
                    {values.map((v) => (
                      <li key={v.source_id}>
                        <i style={{ background: v.color }} />
                        <span>{v.short}</span>
                        <b>{formatValue(v.point!.value, card.precision)}</b>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <dl>
                <div><dt>{t("tab.sources")}</dt><dd>{card.source_count}</dd></div>
                <div><dt>{t("overview.releases")}</dt><dd>{card.release_count}</dd></div>
              </dl>
              <span className="indicator-card__link">{t("common.open")} <b>→</b></span>
            </button>
          );
        })}
        <aside className="indicator-card indicator-card--news">
          <span className="indicator-card__category">{t("overview.latestReleases")}</span>
          <ul className="release-feed">
            {overview.latest_releases.map((r) => (
              <li key={`${r.short}-${r.title}`}>
                <i style={{ background: r.color }} />
                <span><b>{r.short}</b>{r.title}</span>
                <time>{formatShortDate(r.vintage_date)}</time>
              </li>
            ))}
          </ul>
        </aside>
      </section>

      <section className="workflow-strip" aria-label={t("app.title")}>
        <div><span>01</span><strong>{t("overview.step1")}</strong><small>{t("overview.step1Text")}</small></div>
        <div><span>02</span><strong>{t("overview.step2")}</strong><small>{t("overview.step2Text")}</small></div>
        <div><span>03</span><strong>{t("overview.step3")}</strong><small>{t("overview.step3Text")}</small></div>
        <div><span>04</span><strong>{t("overview.step4")}</strong><small>{t("overview.step4Text")}</small></div>
      </section>
    </main>
  );
}
