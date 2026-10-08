import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { MODEL_COLORS } from "../colors";
import { formatPeriod, formatShortDate, formatValue, periodOf } from "../format";
import { t } from "../i18n";
import { actualPoints, buildLines, categories, defaultSelection, effectiveSelection, staleSources } from "../lines";
import type { Featured, Frequency, ModelRun, ModelSpec, SeriesResponse } from "../types";
import { Accuracy } from "./Accuracy";
import { type ChartHandle, ForecastChart } from "./ForecastChart";
import { IndicatorPicker } from "./IndicatorPicker";
import { PeriodTable } from "./PeriodTable";
import { SummaryTable } from "./SummaryTable";

interface Props {
  id: string;
  featured: Featured[];
  onSelect: (id: string) => void;
  onBack: () => void;
}

const HORIZON: Record<Frequency, number> = { A: 4, Q: 8, M: 18 };
const VISIBLE_HISTORY: Record<Frequency, number> = { A: 10, Q: 16, M: 48 };
const RELEASES_SHOWN = 3;
const MIN_OBS: Record<string, (m: number) => number> = {
  rw: () => 2, rwd: () => 3, rws: (m) => (m > 1 ? 2 * m : Infinity), rwds: (m) => (m > 1 ? 2 * m : Infinity),
  ts: (m) => Math.max(4, m > 1 ? 2 * m : 4), ma: () => 5, arima: () => 30,
};

export function IndicatorWorkspace({ id, featured, onSelect, onBack }: Props) {
  const item = featured.find((f) => f.id === id)!;
  const [frequency, setFrequency] = useState<Frequency>(item.frequency);
  const [data, setData] = useState<SeriesResponse | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"compare" | "accuracy">("compare");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [asof, setAsof] = useState("");
  const [bands, setBands] = useState(true);
  const [models, setModels] = useState<ModelSpec[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set(["rw", "rwd"]));
  const [intervals, setIntervals] = useState(false);
  const [maQ, setMaQ] = useState(3);
  const [horizon, setHorizon] = useState(HORIZON[item.frequency]);
  const [cutoff, setCutoff] = useState("");
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [modelErrors, setModelErrors] = useState<string[]>([]);
  const [building, setBuilding] = useState(false);
  const chartRef = useRef<ChartHandle>(null);

  useEffect(() => { void api.models().then(setModels).catch(() => undefined); }, []);
  useEffect(() => { setFrequency(item.frequency); setTab("compare"); }, [item.id, item.frequency]);

  useEffect(() => {
    let active = true;
    setError(""); setData(null); setRuns([]); setModelErrors([]); setCutoff(""); setAsof(""); setExpanded(new Set());
    setHorizon(HORIZON[frequency]);
    api.series(id, frequency)
      .then((d) => { if (!active) return; setData(d); setSelected(defaultSelection(d)); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [id, frequency]);

  const shown = useMemo(() => (data ? effectiveSelection(data, selected, asof) : new Set<string>()), [data, selected, asof]);
  const lines = useMemo(() => (data ? buildLines(data, shown, asof, runs, frequency) : []), [data, shown, asof, runs, frequency]);
  const periods = useMemo(() => categories(lines), [lines]);
  const fact = useMemo(() => (data ? actualPoints(data, asof, frequency) : []), [data, asof, frequency]);
  const lastFact = fact.length ? fact[fact.length - 1] : null;
  const initialStart = lastFact ? periods[Math.max(0, periods.indexOf(lastFact.period) - VISIBLE_HISTORY[frequency])] : null;
  const stale = useMemo(() => (data ? staleSources(data) : new Set<string>()), [data]);
  const season = frequency === "M" ? 12 : frequency === "Q" ? 4 : 1;
  const available = models.filter((m) => fact.length >= (MIN_OBS[m.code]?.(season) ?? 1));

  if (error) {
    return <main className="page-shell"><div className="error-panel"><p className="eyebrow">{t("common.error")}</p><p>{error}</p>
      <button className="button button--primary" type="button" onClick={onBack}>{t("ws.back")}</button></div></main>;
  }
  if (!data) {
    return <main className="page-shell"><div className="loading-panel"><span className="loading-spinner" />{t("common.loading")}</div></main>;
  }

  const indicator = data.indicator;
  const releaseCount = data.sources.reduce((n, s) => n + s.releases.length, 0);
  const firstVintage = data.sources.flatMap((s) => s.releases.map((r) => r.vintage_date)).sort()[0];

  function toggleRelease(releaseId: string) {
    setAsof("");
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(releaseId)) next.delete(releaseId); else next.add(releaseId);
      return next;
    });
  }

  function setSource(sourceId: string, mode: "latest" | "all" | "none") {
    const source = data!.sources.find((s) => s.source_id === sourceId)!;
    setAsof("");
    setSelected((current) => {
      const next = new Set([...current].filter((r) => !source.releases.some((x) => x.release_id === r)));
      if (mode === "latest") next.add(source.releases[source.releases.length - 1].release_id);
      if (mode === "all") source.releases.forEach((r) => next.add(r.release_id));
      return next;
    });
    if (mode === "all") setExpanded((e) => new Set(e).add(sourceId));
  }

  async function buildModels() {
    setBuilding(true); setModelErrors([]);
    const results: ModelRun[] = [];
    const errors: string[] = [];
    for (const code of [...chosen].filter((c) => available.some((a) => a.code === c))) {
      try {
        results.push(await api.runModel({
          featured: id, frequency, model: code, horizon, cutoff: cutoff || undefined, asof: asof || undefined,
          params: code === "ma" ? { q: maQ } : {},
        }));
      } catch (e) {
        errors.push((e as Error).message);
      }
    }
    setRuns(results); setModelErrors(errors); setBuilding(false);
  }

  const asofPeriod = asof ? periodOf(asof, frequency) : null;
  const caveats = data.sources.filter((s) => s.caveat && s.releases.some((r) => shown.has(r.release_id)));

  return (
    <main className="page-shell workspace-page">
      <header className="workspace-heading">
        <div>
          <button className="text-back" type="button" onClick={onBack}>{t("ws.back")}</button>
          <p className="eyebrow">{t("ws.eyebrow")} · {item.category}</p>
          <h1>{item.title}</h1>
          <p>{indicator.unit}{item.subtitle ? ` · ${item.subtitle}` : indicator.base ? ` · ${indicator.base}` : ""}</p>
        </div>
        <div className="workspace-heading__actions">
          <IndicatorPicker items={featured} current={id} onSelect={onSelect} variant="primary" />
          {data.actual && <a className="button button--outline" href={data.actual.url} target="_blank" rel="noreferrer">{t("ws.factSource")}</a>}
        </div>
      </header>

      <section className="meta-strip">
        <div>
          <span>{t("ws.metaFact")}</span>
          <strong>{lastFact ? `${formatValue(lastFact.value, indicator.precision)}` : "—"}</strong>
          <small>{lastFact ? `${formatPeriod(lastFact.period)} · ${data.actual?.short ?? ""}` : ""}</small>
        </div>
        <div><span>{t("ws.metaSources")}</span><strong>{data.sources.length}</strong><small>{t("ws.metaSourcesHint")}</small></div>
        <div><span>{t("ws.metaReleases")}</span><strong>{releaseCount}</strong><small>{firstVintage ? t("ws.metaReleasesHint", { date: formatShortDate(firstVintage) }) : ""}</small></div>
        <div><span>{t("ws.metaModels")}</span><strong>{t("ws.metaModelsValue", { n: available.length, total: models.length || 7 })}</strong><small>{t("ws.metaModelsHint")}</small></div>
      </section>

      <div className="workspace-tabs" role="tablist">
        <button type="button" className={tab === "compare" ? "is-active" : ""} onClick={() => setTab("compare")}>{t("ws.tabCompare")}</button>
        <button type="button" className={tab === "accuracy" ? "is-active" : ""} onClick={() => setTab("accuracy")}>{t("ws.tabAccuracy")}</button>
        {data.frequencies.length > 1 && (
          <div className="frequency-switch">
            <span>{t("ws.frequency")}</span>
            <div className="segmented">
              {data.frequencies.map((f) => (
                <button key={f} type="button" className={frequency === f ? "is-active" : ""} onClick={() => setFrequency(f)}>{t(`freq.${f}`)}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {tab === "accuracy" ? <Accuracy id={id} frequency={frequency} precision={indicator.precision} /> : (
        <>
          <section className="comparison-layout">
            <aside className="comparison-controls">
              <div className="control-section">
                <p className="eyebrow">{t("ws.sourcesEyebrow")}</p>
                <h2>{t("ws.sourcesTitle")}</h2>
                {data.sources.map((source) => {
                  const releases = [...source.releases].reverse();
                  const open = expanded.has(source.source_id);
                  const visible = open ? releases : releases.slice(0, RELEASES_SHOWN);
                  return (
                    <div className="source-choice" key={source.source_id}>
                      <div className="source-choice__head">
                        <span className="source-choice__name" title={[source.description, source.caveat].filter(Boolean).join(" ")}>
                          <i style={{ background: source.color }} /><strong>{source.short}</strong><span className="info-dot">i</span>
                        </span>
                        <span className="source-choice__actions">
                          <button type="button" onClick={() => setSource(source.source_id, "latest")}>{t("ws.latestOnly")}</button>
                          <button type="button" onClick={() => setSource(source.source_id, "all")}>{t("ws.all")}</button>
                          <button type="button" onClick={() => setSource(source.source_id, "none")}>{t("ws.none")}</button>
                        </span>
                      </div>
                      {asof && (
                        <p className="source-choice__asof">
                          {(() => {
                            const pick = releases.find((r) => shown.has(r.release_id));
                            return pick ? t("ws.asofPick", { title: pick.title, date: formatShortDate(pick.vintage_date) }) : t("ws.asofNone");
                          })()}
                        </p>
                      )}
                      {!asof && stale.has(source.source_id) && !releases.some((r) => shown.has(r.release_id)) && (
                        <p className="source-choice__stale">{t("ws.stale", { date: formatShortDate(releases[0].vintage_date) })}</p>
                      )}
                      {visible.map((r, i) => (
                        <label className="check-row" key={r.release_id}>
                          <input type="checkbox" checked={shown.has(r.release_id)} onChange={() => toggleRelease(r.release_id)} />
                          <i style={{ background: source.color, opacity: i === 0 ? 1 : 0.45 }} />
                          <span><b>{r.title}</b><small>{formatShortDate(r.vintage_date)}</small></span>
                        </label>
                      ))}
                      {releases.length > RELEASES_SHOWN && (
                        <button type="button" className="link-button" onClick={() => setExpanded((e) => {
                          const next = new Set(e);
                          if (open) next.delete(source.source_id); else next.add(source.source_id);
                          return next;
                        })}>{open ? t("ws.showLess") : t("ws.showAll", { count: releases.length })}</button>
                      )}
                    </div>
                  );
                })}
                <div className="asof-box">
                  <label htmlFor="asof">{t("ws.asof")}</label>
                  <div className="asof-box__row">
                    <input id="asof" className="field-input" type="date" value={asof} onChange={(e) => setAsof(e.target.value)} />
                    {asof && <button type="button" className="icon-button" onClick={() => setAsof("")}>{t("ws.asofReset")}</button>}
                  </div>
                  <small>{t("ws.asofHint")}</small>
                </div>
                <label className="compact-toggle"><input type="checkbox" checked={bands} onChange={(e) => setBands(e.target.checked)} /> {t("ws.bands")}</label>
              </div>

              <div className="control-section model-builder">
                <p className="eyebrow">{t("ws.modelsEyebrow")}</p>
                <h2>{t("ws.modelsTitle")}</h2>
                <div className="model-chips">
                  {models.map((m) => {
                    const ok = available.some((a) => a.code === m.code);
                    return (
                      <button key={m.code} type="button" disabled={!ok} title={m.description}
                        className={`model-chip ${chosen.has(m.code) && ok ? "is-active" : ""}`}
                        style={{ ["--chip" as string]: MODEL_COLORS[m.code] }}
                        onClick={() => setChosen((c) => { const n = new Set(c); if (n.has(m.code)) n.delete(m.code); else n.add(m.code); return n; })}>
                        {m.name}
                      </button>
                    );
                  })}
                </div>
                <p className="field-help">{[...chosen].map((c) => models.find((m) => m.code === c)).filter(Boolean).map((m) => `${m!.name} — ${m!.description}`).join(". ")}</p>
                {chosen.has("ma") && (
                  <label>MA: q<input type="number" min={1} max={24} value={maQ} onChange={(e) => setMaQ(Number(e.target.value) || 1)} /></label>
                )}
                <div className="field-pair">
                  <label>{t("ws.cutoff")}
                    <select value={cutoff} onChange={(e) => setCutoff(e.target.value)}>
                      <option value="">{lastFact ? formatPeriod(lastFact.period) : "—"}</option>
                      {[...fact].reverse().slice(1).map((p) => <option key={p.period} value={p.period}>{formatPeriod(p.period)}</option>)}
                    </select>
                  </label>
                  <label>{t("ws.horizon")}
                    <input type="number" min={1} max={60} value={horizon} onChange={(e) => setHorizon(Number(e.target.value) || 1)} />
                  </label>
                </div>
                <button className="button button--primary button--wide" type="button"
                  disabled={building || !fact.length || ![...chosen].some((c) => available.some((a) => a.code === c))}
                  onClick={() => void buildModels()}>{building ? t("ws.building") : t("ws.build")}</button>
                <label className="compact-toggle"><input type="checkbox" checked={intervals} onChange={(e) => setIntervals(e.target.checked)} /> {t("ws.intervals")}</label>
                {runs.length > 0 && (
                  <div className="built-models">
                    {runs.map((r) => (
                      <button type="button" key={r.model} onClick={() => setRuns((x) => x.filter((y) => y.model !== r.model))}>
                        <i style={{ background: MODEL_COLORS[r.model] }} />{r.name}{r.info.order ? ` ${JSON.stringify(r.info.order)}` : ""}<span>×</span>
                      </button>
                    ))}
                  </div>
                )}
                {modelErrors.length > 0 && <div className="inline-error">{modelErrors.map((e) => <div key={e}>{e}</div>)}</div>}
                {models.length > available.length && (
                  <details className="availability-note">
                    <summary>{t("ws.modelUnavailable")}</summary>
                    {models.filter((m) => !available.includes(m)).map((m) => (
                      <p key={m.code}><b>{m.name}:</b> {m.code === "arima" ? t("ws.whyArima") : season === 1 && (m.code === "rws" || m.code === "rwds") ? t("ws.whySeasonal") : t("ws.whyShort")} {t("ws.observations", { n: fact.length })}</p>
                    ))}
                  </details>
                )}
              </div>
            </aside>

            <div className="chart-panel">
              <div className="chart-panel__heading">
                <div>
                  <p className="eyebrow">{t("ws.chartEyebrow")}</p>
                  <h2>{t("ws.chartTitle", { name: item.short })}</h2>
                  <span>{indicator.unit} · {t(`freq.${frequency}`).toLowerCase()} · {t("ws.zoomHint")}</span>
                </div>
                <div className="chart-tools">
                  <button type="button" className="icon-button" onClick={() => chartRef.current?.zoomTo(initialStart, null)}>{t("ws.zoomRecent")}</button>
                  <button type="button" className="icon-button" onClick={() => chartRef.current?.zoomTo(null, null)}>{t("ws.zoomAll")}</button>
                  <button type="button" className="icon-button" onClick={() => chartRef.current?.png(`${id}_${frequency}`)}>{t("ws.png")}</button>
                </div>
              </div>
              {lines.length <= 1 && <div className="inline-error">{t("ws.noSelection")}</div>}
              <ForecastChart ref={chartRef} lines={lines} periods={periods} unit={indicator.unit} precision={indicator.precision}
                showBands={bands} showIntervals={intervals} lastFact={lastFact?.period ?? null} asofPeriod={asofPeriod} asofDate={asof} initialStart={initialStart} />
              {caveats.length > 0 && (
                <div className="chart-note">
                  {caveats.map((s) => <p key={s.source_id}><b style={{ color: s.color }}>{s.short}.</b> {s.caveat}</p>)}
                </div>
              )}
            </div>
          </section>

          <SummaryTable lines={lines} periods={periods} data={data} precision={indicator.precision} exportName={`${id}_${frequency}`} />
          <PeriodTable lines={lines} periods={periods} precision={indicator.precision} />
        </>
      )}
    </main>
  );
}
