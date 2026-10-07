import { t } from "../i18n";

// Links of the NCSED platform header (data.iep.ru); the dashboard lives under "Аналитика".
const NAV = [
  { key: "nav.about", href: "https://nsedc.ru/about/" },
  { key: "nav.lake", href: "https://repository.econdata.tech/" },
  { key: "nav.stats", href: "https://data.iep.ru/ru/analytic_sets" },
  { key: "nav.tools", href: "https://data.iep.ru/ru/platform" },
  { key: "nav.analytics", href: "#", active: true },
] as const;

export function Header() {
  return (
    <header className="portal-header">
      <div className="portal-header__inner">
        <a className="portal-logo" href="https://data.iep.ru/" aria-label="НЦСЭД">
          <span className="portal-logo__mark">НЦ</span>
          <span>НЦСЭД</span>
        </a>
        <nav className="portal-nav">
          {NAV.map((item) => (
            <a key={item.key} href={item.href} className={"active" in item ? "is-active" : ""}>
              {t(item.key)}
            </a>
          ))}
        </nav>
        <a className="portal-account" href="https://data.iep.ru/">{t("nav.account")}</a>
      </div>
    </header>
  );
}
