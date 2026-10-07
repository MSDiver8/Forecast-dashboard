import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { sourceColor } from "../colors";
import { formatDate, formatPeriod } from "../format";
import { t } from "../i18n";
import { allPeriods, buildSeries } from "../series";
import type { Catalog, Frequency, ModelRun, ModelSpec, View } from "../types";
import { DataTable } from "./DataTable";
import { ForecastChart } from "./ForecastChart";

export interface Selection { indicator: string; area: string; frequency: Frequency }

interface Props {
  catalog: Catalog;
  selection: Selection;
  onSelect: (s: Selection) => void;
}

type Mode = "latest" | "asof" | "manual";
const FREQS: Frequency[] = ["A", "Q", "M"];
const DEFAULT_HORIZON: Record<string, number> = { A: 4, Q: 8, M: 24 };
const DEFAULT_SPAN: Record<string, number> = { A: 12, Q: 24, M: 60 };

export function Comparison({ catalog, selection, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("latest");
  const [asof, setAsof] = useState("");
  const [lastN, setLastN] = useState(1);
  const [manual, setManual] = useState<Set<string>>(new Set());
  const [sources, setSources] = useState<Set<string> | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [intervals, setIntervals] = useState(true);
  const [models, setModels] = useState<ModelSpec[]>([]);
  const [chosenModels, setChosenModels] = useState<Set<string>>(new Set(["rw"]));
  const [maQ, setMaQ] = useState(3);
  const [horizon, setHorizon] = useState(DEFAULT_HORIZON[selection.frequency]);
  const [cutoff, setCutoff] = useState("");
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [modelErrors, setModelErrors] = useState<string[]>([]);
  const [building, setBuilding] = useState(false);
  const [range, setRange] = useState<{ from: string; to: string }>({ from: "", to: "" });

  const indicator = catalog.indicators.find((i) => i.id === selection.indicator)!;
  const pair = catalog.pairs.find((p) => p.indicator_id === selection.indicator && p.area_id === selection.area);
  const allSourceIds = Object.keys(catalog.sources);
  const catalogSources = pair?.frequencies[selection.frequency] ?? [];

  useEffect(() => { void api.models().then(setModels); }, []);

  // Models listed in the address (#...&models=rw,arima) are built once the view is loaded.
  const [hashModels, setHashModels] = useState<string[]>(() =>
    (new URLSearchParams(window.location.hash.slice(1)).get("models") ?? "").split(",").filter(Boolean));
  useEffect(() => {
    if (!hashModels.length || !view?.actual) return;
    setChosenModels(new Set(hashModels));
    setHashModels([]);
    void buildModels(new Set(hashModels));
  }, [view, hashModels]);

  // A new indicator, area or frequency resets everything that depends on the series.
  useEffect(() => {
    setSources(null); setManual(new Set()); setRuns([]); setModelErrors([]); setHidden(new Set());
    setCutoff(""); setRange({ from: "", to: "" }); setHorizon(DEFAULT_HORIZON[selection.frequency]);
  }, [selection.indicator, selection.area, selection.frequency]);

  useEffect(() => {
    if (mode === "asof" && !asof) return;
    let active = true;
    setError("");
    api.view({
      ...selection, mode, asof: mode === "asof" ? asof : undefined,
      sources: sources ? [...sources] : undefined, releases: mode === "manual" ? [...manual] : undefined,
      lastN: mode === "manual" ? undefined : lastN,
    })
      .then((v) => { if (active) setView(v); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [selection, mode, asof, lastN, manual, sources]);

  const series = useMemo(() => (view ? buildSeries(view, runs, allSourceIds) : []), [view, runs, allSourceIds]);
  // Sources that can really be shown at this frequency (the view drops, e.g., one quarter a year at annual step).
  const freqSources = view ? view.sources.map((s) => s.source_id) : catalogSources;
  const periods = useMemo(() => allPeriods(series), [series]);
  const actualPeriods = view?.actual?.points.map((p) => p.period) ?? [];

  const visiblePeriods = useMemo(() => {
    if (!periods.length) return [];
    const lastActual = actualPeriods[actualPeriods.length - 1];
    const defaultFrom = lastActual
      ? periods[Math.max(0, periods.indexOf(lastActual) - DEFAULT_SPAN[selection.frequency])] ?? periods[0]
      : periods[0];
    const from = range.from || defaultFrom;
    const to = range.to || periods[periods.length - 1];
    return periods.filter((p) => p >= from && p <= to);
  }, [periods, range, actualPeriods, selection.frequency]);

  const pairsOf = (indicatorId: string) => catalog.pairs.filter((p) => p.indicator_id === indicatorId);
  const filteredIndicators = catalog.indicators.filter((i) =>
    i.name.toLowerCase().includes(query.trim().toLowerCase()) && pairsOf(i.id).length > 0);

  function selectIndicator(id: string) {
    const options = pairsOf(id);
    const keep = options.find((p) => p.area_id === selection.area) ?? options.sort((a, b) => b.source_count - a.source_count)[0];
    const freqs = Object.keys(keep.frequencies) as Frequency[];
    onSelect({ indicator: id, area: keep.area_id, frequency: freqs.includes(selection.frequency) ? selection.frequency : freqs[0] });
  }

  function selectArea(area: string) {
    const p = catalog.pairs.find((x) => x.indicator_id === selection.indicator && x.area_id === area)!;
    const freqs = Object.keys(p.frequencies) as Frequency[];
    onSelect({ ...selection, area, frequency: freqs.includes(selection.frequency) ? selection.frequency : freqs[0] });
  }

  function toggleSource(id: string) {
    const current = new Set(sources ?? freqSources);
    if (current.has(id)) current.delete(id); else current.add(id);
    setSources(current);
  }

  async function buildModels(codes: Set<string> = chosenModels) {
    setBuilding(true); setModelErrors([]);
    const results: ModelRun[] = [];
    const errors: string[] = [];
    for (const code of codes) {
      try {
        results.push(await api.runModel({
          indicator: selection.indicator, area: selection.area, frequency: selection.frequency, model: code,
          horizon, cutoff: cutoff || undefined, asof: mode === "asof" ? asof : undefined,
          params: code === "ma" ? { q: maQ } : {},
        }));
      } catch (e) {
        errors.push((e as Error).message);
      }
    }
    setRuns(results); setModelErrors(errors); setBuilding(false);
  }

  const areaName = (id: string) => catalog.areas.find((a) => a.id === id)?.name ?? id;
  const derivedNote = view?.sources.filter((s) => s.derived_from && s.releases.length).map((s) => s.organization).join(", ");

  return (
    <div className="layout">
      <aside className="filters">
        <div className="filter-block">
          <h3>{t("filters.indicator")}</h3>
          <input className="input" placeholder={t("filters.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="indicator-list" style={{ marginTop: 8 }}>
            {catalog.groups.map((g) => {
              const items = filteredIndicators.filter((i) => i.groups.includes(g.id));
              if (!items.length) return null;
              return (
                <div key={g.id}>
                  <div className="indicator-list__group">{g.id}. {g.name}</div>
                  {items.map((i) => (
                    <button key={`${g.id}-${i.id}`} type="button" className={i.id === selection.indicator ? "is-active" : ""}
                      onClick={() => selectIndicator(i.id)}>
                      <span>{i.name}</span>
                      <span className="badge" title={t("filters.sourcesCount")}>
                        {Math.max(...pairsOf(i.id).map((p) => p.source_count))}
                      </span>
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        </div>

        <div className="filter-block">
          <label className="field">{t("filters.area")}
            <select className="select" value={selection.area} onChange={(e) => selectArea(e.target.value)}>
              {pairsOf(selection.indicator).map((p) => (
                <option key={p.area_id} value={p.area_id}>{areaName(p.area_id)} — {p.source_count} {t("filters.sourcesCount")}</option>
              ))}
            </select>
          </label>
          <div className="field">{t("filters.frequency")}
            <div className="segmented">
              {FREQS.map((f) => (
                <button key={f} type="button" disabled={!pair?.frequencies[f]} className={selection.frequency === f ? "is-active" : ""}
                  onClick={() => onSelect({ ...selection, frequency: f })}>{t(`freq.${f}`)}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="filter-block">
          <h3>{t("filters.sources")}</h3>
          {freqSources.map((id) => (
            <label className="check" key={id}>
              <input type="checkbox" checked={sources ? sources.has(id) : true} onChange={() => toggleSource(id)} />
              <span className="swatch" style={{ background: sourceColor(id, allSourceIds) }} />
              <span>
                {catalog.sources[id]?.organization}
                <small>{catalog.sources[id]?.name}</small>
                {catalog.notes[`${id}|${selection.indicator}|${selection.area}`] && (
                  <small>{catalog.notes[`${id}|${selection.indicator}|${selection.area}`]}</small>
                )}
              </span>
            </label>
          ))}
        </div>

        <div className="filter-block">
          <h3>{t("filters.vintages")}</h3>
          {(["latest", "asof", "manual"] as Mode[]).map((m) => (
            <label className="check" key={m}>
              <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
              <span>{t(`filters.${m}`)}</span>
            </label>
          ))}
          {mode !== "manual" && (
            <label className="field">{t("filters.lastN")}
              <input className="input" type="number" min={1} max={24} value={lastN}
                onChange={(e) => setLastN(Math.max(1, Math.min(24, Number(e.target.value) || 1)))} />
            </label>
          )}
          {mode === "asof" && (
            <input className="input" type="date" value={asof} onChange={(e) => setAsof(e.target.value)} />
          )}
          {mode === "manual" && view && (
            <div className="manual-releases">
              {view.sources.map((s) => (
                <div key={s.source_id}>
                  <div className="muted" style={{ marginTop: 6 }}>{s.organization}</div>
                  {[...s.available_releases].reverse().map((r) => (
                    <label className="check" key={r.release_id}>
                      <input type="checkbox" checked={manual.has(r.release_id)} onChange={() => {
                        const next = new Set(manual);
                        if (next.has(r.release_id)) next.delete(r.release_id); else next.add(r.release_id);
                        setManual(next);
                      }} />
                      <span>{r.title}<small>{formatDate(r.vintage_date)}</small></span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="filter-block">
          <h3>{t("filters.models")}</h3>
          {models.map((m) => (
            <label className="check" key={m.code} title={m.description}>
              <input type="checkbox" checked={chosenModels.has(m.code)} onChange={() => {
                const next = new Set(chosenModels);
                if (next.has(m.code)) next.delete(m.code); else next.add(m.code);
                setChosenModels(next);
              }} />
              <span>{m.name}<small>{m.description}</small></span>
            </label>
          ))}
          {chosenModels.has("ma") && (
            <label className="field">MA: q
              <input className="input" type="number" min={1} max={36} value={maQ} onChange={(e) => setMaQ(Number(e.target.value) || 1)} />
            </label>
          )}
          <div className="row">
            <label className="field">{t("filters.cutoff")}
              <select className="select" value={cutoff} onChange={(e) => setCutoff(e.target.value)}>
                <option value="">{actualPeriods.length ? formatPeriod(actualPeriods[actualPeriods.length - 1]) : "—"}</option>
                {[...actualPeriods].reverse().slice(1).map((p) => <option key={p} value={p}>{formatPeriod(p)}</option>)}
              </select>
            </label>
            <label className="field">{t("filters.horizon")}
              <input className="input" type="number" min={1} max={60} value={horizon} onChange={(e) => setHorizon(Number(e.target.value) || 1)} />
            </label>
          </div>
          <div className="row">
            <button type="button" className="btn btn--primary" disabled={building || !view?.actual || !chosenModels.size}
              onClick={() => void buildModels()}>{building ? t("filters.building") : t("filters.build")}</button>
            {runs.length > 0 && <button type="button" className="btn" onClick={() => setRuns([])}>{t("filters.clearModels")}</button>}
          </div>
          {modelErrors.map((e) => <p key={e} className="note">{e}</p>)}
        </div>

        <div className="filter-block">
          <h3>{t("filters.period")}</h3>
          <div className="row">
            <select className="select" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })}>
              <option value="">{t("filters.from")} {visiblePeriods[0] ? formatPeriod(visiblePeriods[0]) : ""}</option>
              {periods.map((p) => <option key={p} value={p}>{formatPeriod(p)}</option>)}
            </select>
            <select className="select" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })}>
              <option value="">{t("filters.to")} {periods.length ? formatPeriod(periods[periods.length - 1]) : ""}</option>
              {periods.map((p) => <option key={p} value={p}>{formatPeriod(p)}</option>)}
            </select>
          </div>
          <label className="check">
            <input type="checkbox" checked={intervals} onChange={(e) => setIntervals(e.target.checked)} />
            <span>{t("filters.intervals")}</span>
          </label>
        </div>
      </aside>

      <section>
        <div className="card chart-card">
          <div className="chart-head">
            <div>
              <h2>{indicator.name} — {areaName(selection.area)}</h2>
              <p>{indicator.unit}{indicator.base ? ` · ${indicator.base}` : ""} · {t(`freq.${selection.frequency}`)}</p>
            </div>
          </div>
          {error && <p className="error">{error}</p>}
          {view && (
            <ForecastChart series={series} periods={visiblePeriods} hidden={hidden} showIntervals={intervals}
              unit={indicator.unit} precision={indicator.precision}
              onToggle={(key) => {
                const next = new Set(hidden);
                if (next.has(key)) next.delete(key); else next.add(key);
                setHidden(next);
              }} />
          )}
          {view && !view.actual && <p className="note">{t("chart.noActual")}</p>}
          {derivedNote && <p className="note">{derivedNote}: {t("chart.derived")}.</p>}
        </div>
        {view && <DataTable series={series.filter((s) => !hidden.has(s.key))} periods={visiblePeriods}
          precision={indicator.precision} title={`${indicator.id}_${selection.area}_${selection.frequency}`} />}
      </section>
    </div>
  );
}
