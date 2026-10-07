import { useEffect, useState } from "react";
import { api } from "./api";
import { CatalogView } from "./components/CatalogView";
import { Comparison, type Selection } from "./components/Comparison";
import { Header } from "./components/Header";
import { StatusView } from "./components/StatusView";
import { t } from "./i18n";
import type { Catalog } from "./types";

type Tab = "compare" | "catalog" | "status";

function selectionFromHash(catalog: Catalog): Selection | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const pair = catalog.pairs.find((p) => p.indicator_id === params.get("indicator") && p.area_id === params.get("area"));
  if (!pair) return null;
  const freq = params.get("freq") ?? "";
  const freqs = Object.keys(pair.frequencies);
  return { indicator: pair.indicator_id, area: pair.area_id, frequency: (freqs.includes(freq) ? freq : freqs[0]) as Selection["frequency"] };
}

function initialSelection(catalog: Catalog): Selection {
  const fromHash = selectionFromHash(catalog);
  if (fromHash) return fromHash;
  const brent = catalog.pairs.find((p) => p.indicator_id === "brent_price");
  const pair = brent ?? catalog.pairs[0];
  const freqs = Object.keys(pair.frequencies);
  return { indicator: pair.indicator_id, area: pair.area_id, frequency: (freqs.includes("A") ? "A" : freqs[0]) as Selection["frequency"] };
}

export default function App() {
  const [tab, setTab] = useState<Tab>("compare");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (selection) {
      window.history.replaceState(null, "", `#indicator=${selection.indicator}&area=${selection.area}&freq=${selection.frequency}`);
    }
  }, [selection]);

  useEffect(() => {
    api.catalog()
      .then((c) => { setCatalog(c); setSelection(initialSelection(c)); })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <Header />
      <div className="product-bar">
        <div className="product-bar__inner">
          <div className="product-title">
            <h1>{t("app.title")}</h1>
            <p>{t("app.subtitle")}</p>
          </div>
          <nav className="product-tabs">
            {(["compare", "catalog", "status"] as Tab[]).map((key) => (
              <button key={key} type="button" className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>
                {t(`tab.${key}`)}
              </button>
            ))}
          </nav>
        </div>
      </div>
      <main className="page">
        {error && <p className="error">{t("common.error")}: {error}</p>}
        {!catalog && !error && <p className="muted">{t("common.loading")}</p>}
        {catalog && selection && tab === "compare" && (
          <Comparison catalog={catalog} selection={selection} onSelect={setSelection} />
        )}
        {catalog && tab === "catalog" && (
          <CatalogView catalog={catalog} onOpen={(s) => { setSelection(s); setTab("compare"); }} />
        )}
        {tab === "status" && <StatusView />}
      </main>
    </>
  );
}
