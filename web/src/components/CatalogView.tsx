import { t } from "../i18n";
import type { Catalog, Frequency } from "../types";
import type { Selection } from "./Comparison";

interface Props { catalog: Catalog; onOpen: (s: Selection) => void }

export function CatalogView({ catalog, onOpen }: Props) {
  const areaName = (id: string) => catalog.areas.find((a) => a.id === id)?.name ?? id;
  return (
    <section>
      <h2 className="panel-title">{t("catalog.title")}</h2>
      <p className="muted">{t("catalog.hint")}</p>
      <div className="table-scroll">
        <table className="plain">
          <thead>
            <tr>
              <th>{t("catalog.group")}</th>
              <th>{t("filters.indicator")}</th>
              <th>{t("filters.area")}</th>
              <th>{t("catalog.frequencies")}</th>
              <th>{t("catalog.sources")}</th>
              <th>{t("catalog.actual")}</th>
            </tr>
          </thead>
          <tbody>
            {catalog.indicators.flatMap((ind) =>
              catalog.pairs.filter((p) => p.indicator_id === ind.id).map((p) => {
                const freqs = Object.keys(p.frequencies) as Frequency[];
                const sources = [...new Set(Object.values(p.frequencies).flat())];
                return (
                  <tr key={`${ind.id}-${p.area_id}`} className="clickable"
                    onClick={() => onOpen({ indicator: ind.id, area: p.area_id, frequency: freqs.includes("A") ? "A" : freqs[0] })}>
                    <td>{ind.groups.join(", ")}</td>
                    <td>{ind.name}<br /><span className="muted">{ind.unit}</span></td>
                    <td>{areaName(p.area_id)}</td>
                    <td>{freqs.map((f) => t(`freq.${f}`)).join(", ")}</td>
                    <td><b>{sources.length}</b> — {sources.map((s) => catalog.sources[s]?.organization ?? s).join(", ")}</td>
                    <td>{p.has_actual ? t("common.yes") : t("common.no")}</td>
                  </tr>
                );
              }))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
