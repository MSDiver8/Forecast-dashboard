import { useState } from "react";
import { t } from "../i18n";
import type { AppView } from "../types";

interface Props {
  activeView: AppView;
  online: boolean;
  hasIndicator: boolean;
  onNavigate: (view: AppView) => void;
}

const GLOBAL = [
  { key: "nav.about", href: "https://nsedc.ru/about/" },
  { key: "nav.lake", href: "https://repository.econdata.tech/" },
  { key: "nav.stats", href: "https://data.iep.ru/ru/analytic_sets" },
] as const;

export function PortalHeader({ activeView, online, hasIndicator, onNavigate }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = (view: AppView) => { setMenuOpen(false); onNavigate(view); };
  const tabs: { view: AppView; label: string }[] = [
    { view: "overview", label: t("tab.overview") },
    ...(hasIndicator ? [{ view: "indicator" as AppView, label: t("tab.compare") }] : []),
    { view: "sources", label: t("tab.sources") },
    { view: "about", label: t("tab.about") },
  ];
  return (
    <>
      <header className="portal-header"><div className="portal-header__inner">
        <button className="portal-brand" type="button" onClick={() => navigate("overview")}>
          <span className="portal-brand__mark">Р</span><span className="portal-brand__name">НЦСЭД</span>
        </button>
        <nav className="portal-global-nav">
          {GLOBAL.map((item) => <a key={item.key} href={item.href}>{t(item.key)}</a>)}
          <span className="portal-global-nav__active">{t("nav.analytics")}</span>
        </nav>
        <div className="portal-header__actions">
          <span className={`service-indicator ${online ? "is-online" : "is-offline"}`} title={online ? t("status.online") : t("status.offline")} />
          <button className="menu-toggle" type="button" onClick={() => setMenuOpen((v) => !v)} aria-label="Меню"><span /><span /><span /></button>
        </div>
      </div></header>
      <div className={`product-bar ${menuOpen ? "is-open" : ""}`}><div className="product-bar__inner">
        <button type="button" className="product-title" onClick={() => navigate("overview")}>
          <span>{t("app.title")}</span><small>{t("app.subtitle")}</small>
        </button>
        <nav className="product-nav">
          {tabs.map((tab) => (
            <button type="button" key={tab.view} className={activeView === tab.view ? "is-active" : ""} onClick={() => navigate(tab.view)}>{tab.label}</button>
          ))}
        </nav>
      </div></div>
    </>
  );
}
