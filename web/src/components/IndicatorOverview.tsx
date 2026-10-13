import { formatPeriod, formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { Card, Overview } from "../types";
import { NewsPanel } from "./NewsPanel";
import { Sparkline } from "./Sparkline";

interface Props {
  overview: Overview;
  onOpenIndicator: (id: string) => void;
  onOpenSources: () => void;
}

const NEW_DAYS = 90;

/** "Новое" stays on a card for three months after the indicator was added. */
function isNew(card: Card): boolean {
  if (!card.added) return false;
  const days = (Date.now() - new Date(`${card.added}T00:00:00`).getTime()) / 86_400_000;
  return days >= 0 && days <= NEW_DAYS;
}

export function IndicatorOverview({ overview, onOpenIndicator, onOpenSources }: Props) {
  const { cards, totals, news } = overview;
  const toList = () => document.getElementById("indicator-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <main className="page-shell overview-page">
      <section className="overview-hero">
        <div className="overview-hero__copy">
          <p className="eyebrow">{t("overview.eyebrow")}</p>
          <h1>{t("app.title")}</h1>
          <p className="overview-hero__tagline">{t("app.subtitle")}</p>
          <p>{t("overview.lead")}</p>
          <div className="overview-hero__actions">
            <button className="button button--primary" type="button" onClick={toList}>{t("overview.pick")} <span aria-hidden="true">↓</span></button>
            <button className="button button--outline" type="button" onClick={onOpenSources}>{t("overview.registry")}</button>
          </div>
        </div>
        {news && <NewsPanel news={news} onOpen={() => onOpenIndicator(news.featured)} />}
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

      <section className="indicator-grid indicator-grid--four">
        {cards.map((card) => {
          const target = card.targets[0];
          const values = card.latest
            .map((l) => ({ ...l, point: target ? l.values[target] : null }))
            .filter((l) => l.point)
            .sort((a, b) => b.point!.value - a.point!.value);
          return (
            <button className="indicator-card" type="button" key={card.id} onClick={() => onOpenIndicator(card.id)}>
              {isNew(card) && <span className="new-badge">{t("overview.new")}</span>}
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
      </section>
    </main>
  );
}
