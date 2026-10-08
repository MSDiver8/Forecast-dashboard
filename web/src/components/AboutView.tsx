import { t } from "../i18n";

const PRINCIPLES = [
  ["about.p1", "about.p1Text"], ["about.p2", "about.p2Text"], ["about.p3", "about.p3Text"],
  ["about.p4", "about.p4Text"], ["about.p5", "about.p5Text"], ["about.p6", "about.p6Text"],
] as const;

export function AboutView() {
  return (
    <main className="page-shell about-page">
      <section className="page-heading">
        <p className="eyebrow">{t("about.eyebrow")}</p>
        <h1>{t("about.title")}</h1>
        <p className="page-heading__description">{t("about.lead")}</p>
      </section>
      <section className="about-grid">
        {PRINCIPLES.map(([title, text], i) => (
          <article key={title}><span>{String(i + 1).padStart(2, "0")}</span><h2>{t(title)}</h2><p>{t(text)}</p></article>
        ))}
      </section>
      <section className="methodology-principles">
        <div><p className="eyebrow">{t("about.legendEyebrow")}</p><h2>{t("about.legendTitle")}</h2></div>
        <dl>
          <div><dt><i className="legend-line legend-line--actual" />{t("about.lFact")}</dt><dd>{t("about.lFactText")}</dd></div>
          <div><dt><i className="legend-line legend-line--source" />{t("about.lSource")}</dt><dd>{t("about.lSourceText")}</dd></div>
          <div><dt><i className="legend-line legend-line--model" />{t("about.lModel")}</dt><dd>{t("about.lModelText")}</dd></div>
          <div><dt><i className="legend-area" />{t("about.lBand")}</dt><dd>{t("about.lBandText")}</dd></div>
        </dl>
      </section>
    </main>
  );
}
