import { useEffect, useState } from "react";
import { api } from "./api";
import "./App.css";
import { AboutView } from "./components/AboutView";
import { IndicatorOverview } from "./components/IndicatorOverview";
import { IndicatorWorkspace } from "./components/IndicatorWorkspace";
import { PortalHeader } from "./components/PortalHeader";
import { SourcesView } from "./components/SourcesView";
import { t } from "./i18n";
import type { AppView, Overview } from "./types";

function readHash(): { view: AppView; id: string | null } {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const view = (params.get("view") as AppView) || "overview";
  return { view, id: params.get("id") };
}

export default function App() {
  const initial = readHash();
  const [view, setView] = useState<AppView>(initial.view);
  const [indicatorId, setIndicatorId] = useState<string | null>(initial.id);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [online, setOnline] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [health, data] = await Promise.all([api.health(), api.overview()]);
      setOnline(health.status === "ok");
      setOverview(data);
    } catch (e) {
      setOnline(false);
      setError((e as Error).message);
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    const params = new URLSearchParams({ view });
    if (view === "indicator" && indicatorId) params.set("id", indicatorId);
    window.history.replaceState(null, "", `#${params}`);
  }, [view, indicatorId]);

  function navigate(next: AppView) {
    setView(next === "indicator" && !indicatorId ? "overview" : next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function openIndicator(id: string) {
    setIndicatorId(id);
    setView("indicator");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  let content;
  if (error && !overview) {
    content = <main className="page-shell"><div className="error-panel"><p className="eyebrow">{t("common.error")}</p><p>{error}</p>
      <button className="button button--primary" type="button" onClick={() => void load()}>{t("common.retry")}</button></div></main>;
  } else if (!overview) {
    content = <main className="page-shell"><div className="loading-panel"><span className="loading-spinner" />{t("common.loading")}</div></main>;
  } else if (view === "indicator" && indicatorId && overview.cards.some((c) => c.id === indicatorId)) {
    content = <IndicatorWorkspace key={indicatorId} id={indicatorId} featured={overview.cards} onSelect={openIndicator} onBack={() => navigate("overview")} />;
  } else if (view === "sources") {
    content = <SourcesView />;
  } else if (view === "about") {
    content = <AboutView />;
  } else {
    content = <IndicatorOverview overview={overview} onOpenIndicator={openIndicator} onOpenSources={() => navigate("sources")} />;
  }

  return (
    <div className="app">
      <PortalHeader activeView={view} online={online} hasIndicator={Boolean(indicatorId)} onNavigate={navigate} />
      {content}
      <footer className="app-footer">
        <div><strong>{t("app.org")}</strong><span>{t("app.footer")}</span></div>
        <span>© 2023–2026 НЦСЭД</span>
      </footer>
    </div>
  );
}
