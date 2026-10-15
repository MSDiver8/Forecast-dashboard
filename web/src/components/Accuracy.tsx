import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { MODEL_COLORS } from "../colors";
import { formatPeriod, formatShortDate, formatValue } from "../format";
import { t } from "../i18n";
import type { EvalMetric, EvalModel, Evaluation, EvaluationRequest, FactMode, Frequency } from "../types";
import { AccuracyChart, type AccuracyChartHandle, asOf, type ChartSeries, monthLabel, signed } from "./AccuracyChart";

const LEVEL_DIGITS = 2;
const ERROR_DIGITS = 1;
const METRIC_DIGITS = 2;
const RECENT_ROWS = 12;
const MAX_CHIPS = 8;
const WINDOW_MODELS = ["ts", "rwd", "rwds"];

type ModelParams = { window?: number; q?: number };

function plural(n: number, words: string): string {
  const [one, few, many] = words.split("|");
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function issuedLabel(pick: { vintage_date: string; approx: boolean }): string {
  return pick.approx
    ? t("acc.issuedApprox", { month: monthLabel(pick.vintage_date) })
    : t("acc.issued", { date: formatShortDate(pick.vintage_date) });
}

function InfoTip({ text }: { text: string }) {
  return <span className="info-tip" tabIndex={0} data-tip={text} aria-label={text}>i</span>;
}

function reasonText(model: EvalModel): string {
  const u = model.unavailable;
  if (!u) return "";
  if (u.reason === "seasonal") return t("acc.reasonSeasonal");
  if (u.reason === "fact") return t("acc.reasonFact");
  return t("acc.reasonShort", { need: u.need ?? 0, have: u.have ?? 0 });
}

/** Retrospective check: forecasts published in a window against the actuals that became known later. */
export function Accuracy({ id, frequency, name }: { id: string; frequency: Frequency; name: string }) {
  const [windowIndex, setWindowIndex] = useState<number | null>(null);
  const [factMode, setFactMode] = useState<FactMode>("latest");
  const [period, setPeriod] = useState<string | null>(null);
  const [sources, setSources] = useState<string[] | null>(null);
  const [models, setModels] = useState<Record<string, ModelParams>>({ rw: {} });
  const [modelFrequency, setModelFrequency] = useState<Frequency | null>(null);
  const [view, setView] = useState<"periods" | "evolution">("periods");
  const [showAll, setShowAll] = useState(false);
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<AccuracyChartHandle>(null);

  const body = useMemo<EvaluationRequest>(() => ({
    featured: id, frequency, window: windowIndex, fact: factMode, sources,
    models: Object.entries(models).map(([code, params]) => ({ code, params })),
    model_frequency: modelFrequency, period: view === "evolution" ? period : null, evolution: view === "evolution",
  }), [id, frequency, windowIndex, factMode, sources, models, modelFrequency, period, view]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const timer = window.setTimeout(() => {
      api.evaluation(body)
        .then((d) => { if (active) { setData(d); setLoading(false); } })
        .catch((e: Error) => { if (active) { setError(e.message); setLoading(false); } });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [body]);

  const periodLabel = useCallback(
    (p: string) => (frequency === "A" ? t("acc.yearLabel", { period: p }) : formatPeriod(p)), [frequency],
  );
  const shortPeriod = (p: string) => (frequency === "A" ? p : formatPeriod(p));

  const chartSeries = useMemo<ChartSeries[]>(() => (data ? [
    ...data.sources.filter((s) => s.selected).map((s) => ({ key: s.source_id, name: s.short, color: s.color, model: false })),
    ...data.models.filter((m) => m.selected && !m.unavailable)
      .map((m) => ({ key: m.code, name: m.name, color: MODEL_COLORS[m.code] ?? "#172f4f", model: true })),
  ] : []), [data]);

  if (error && !data) return <div className="inline-error">{error}</div>;
  if (!data) return <div className="loading-panel loading-panel--small"><span className="loading-spinner" />{t("common.loading")}</div>;
  if (!data.actual) return <div className="empty-evaluation"><span>◷</span><p>{t("acc.noFact")}</p></div>;

  const checked = data.periods.filter((p) => p.fact != null);
  const pending = data.periods.find((p) => p.fact == null);
  const withRows = data.rows.filter((r) => r.fact != null).map((r) => r.period);
  const selected = checked.find((p) => p.period === period)
    ?? checked.find((p) => p.period === withRows[withRows.length - 1]) ?? checked[checked.length - 1];
  const selectedLabel = selected ? periodLabel(selected.period) : "";
  const words = t(`acc.unitWords${frequency}`);
  const sourceIds = data.sources.map((s) => s.source_id);
  const chosen = sources ?? sourceIds;
  const sourceOf = new Map(data.sources.map((s) => [s.source_id, s]));
  const modelOf = new Map(data.models.map((m) => [m.code, m]));
  const seriesName = (kind: string, key: string) => (kind === "source" ? sourceOf.get(key)?.short : modelOf.get(key)?.name) ?? key;
  const windowParam = data.models.find((m) => m.selected && WINDOW_MODELS.includes(m.code))?.params.window;
  const maParam = modelOf.get("ma")?.selected ? modelOf.get("ma")?.params.q : undefined;

  const toggleSource = (sid: string) => setSources(chosen.includes(sid) ? chosen.filter((x) => x !== sid) : [...chosen, sid]);
  const toggleModel = (code: string) => setModels((m) => {
    const next = { ...m };
    if (code in next) delete next[code]; else next[code] = {};
    return next;
  });
  const setParam = (codes: string[], key: keyof ModelParams, value: number) => setModels((m) => {
    const next = { ...m };
    for (const code of codes) if (code in next) next[code] = { ...next[code], [key]: value };
    return next;
  });

  const estimationLabel = (o: Evaluation["estimation"]["options"][number]) => {
    const freq = t(`freq.${o.frequency}`);
    if (o.convert === "mean") return t("acc.estMean", { freq, target: t(`acc.target${frequency}`) });
    if (o.convert === "december") return t("acc.estDecember", { freq });
    return t("acc.estSame", { freq });
  };

  // Table: errors are tinted by size with one colour; the darker, the larger the error.
  const rows = showAll ? data.rows : data.rows.slice(-RECENT_ROWS);
  const errorsShown = rows.flatMap((r) => chartSeries.map((s) => (s.model ? r.models[s.key] : r.picks[s.key])?.error))
    .filter((e): e is number => e != null);
  const maxError = Math.max(1e-9, ...errorsShown.map(Math.abs));
  const tint = (e: number | null | undefined) => (e == null ? undefined : { background: `rgba(204, 122, 0, ${(0.04 + 0.26 * Math.abs(e) / maxError).toFixed(3)})` });

  // Metrics: the common periods named as a range, a short list, or a count with bounds.
  const { metrics } = data;
  const common = metrics.periods;
  const commonCount = `${common.length} ${plural(common.length, words)}`;
  let range = "";
  if (common.length) {
    const [from, to] = [shortPeriod(common[0]), shortPeriod(common[common.length - 1])];
    if (metrics.contiguous) range = frequency === "A" ? t("acc.rangeA", { from, to }) : t("acc.range", { from, to });
    else if (common.length <= 4) range = frequency === "A" ? t("acc.listA", { list: common.map(shortPeriod).join(", ") }) : t("acc.list", { list: common.map(shortPeriod).join(", ") });
    else range = t("acc.spread", { count: commonCount, from, to });
  }
  const metricRows = [...metrics.rows].sort((a, b) => a.mae - b.mae);
  const best = (pick: (m: EvalMetric) => number | null) => {
    const values = metricRows.map(pick).filter((v): v is number => v != null);
    return values.length ? Math.min(...values) : null;
  };
  const bestMae = best((m) => m.mae);
  const bestRmse = best((m) => m.rmse);
  const bestMape = best((m) => m.mape);
  const bestRatio = best((m) => m.ratio_rw);
  const strong = (value: number | null, target: number | null, digits = METRIC_DIGITS) => (
    value == null ? <span className="na">—</span>
      : value === target ? <b>{formatValue(value, digits)}</b> : <>{formatValue(value, digits)}</>
  );
  const windowText = t(`acc.window${frequency}${data.window}` as Parameters<typeof t>[0]);

  return (
    <section className="evaluation-panel">
      <section className="comparison-layout accuracy-layout">
        <aside className="comparison-controls">
          <div className="control-section">
            <p className="eyebrow">{t("acc.retroEyebrow")}</p>
            <h2>{t("acc.retroTitle")}</h2>
            <h3 className="control-label">{t(`acc.periodPick${frequency}`)}</h3>
            {checked.length <= MAX_CHIPS ? (
              <div className="acc-chips">
                {checked.map((p) => (
                  <button key={p.period} type="button" className={p.period === selected?.period ? "is-active" : ""}
                    onClick={() => setPeriod(p.period)}>{shortPeriod(p.period)}</button>
                ))}
                {pending && <button type="button" className="is-muted" disabled>{t("acc.pendingChip", { period: shortPeriod(pending.period) })}</button>}
              </div>
            ) : (
              <select className="acc-select" value={selected?.period ?? ""} onChange={(e) => setPeriod(e.target.value)}>
                {[...checked].reverse().map((p) => <option key={p.period} value={p.period}>{formatPeriod(p.period)}</option>)}
              </select>
            )}
            <h3 className="control-label">{t("acc.windowPick")}</h3>
            {Array.from({ length: data.window_count }, (_, i) => {
              const w = selected?.windows[i];
              return (
                <label key={i} className={`radio-row ${i === data.window ? "is-active" : ""}`}>
                  <input type="radio" name={`acc-window-${id}`} checked={i === data.window} onChange={() => setWindowIndex(i)} />
                  <span>
                    <b>{t(`acc.window${frequency}${i}` as Parameters<typeof t>[0])}</b>
                    {w && selected && <small>{t("acc.windowFor", { period: shortPeriod(selected.period), start: formatShortDate(w.start), end: formatShortDate(w.end) })}</small>}
                  </span>
                </label>
              );
            })}
            <h3 className="control-label">{t("acc.factPick")}</h3>
            <div className="segmented">
              <button type="button" className={factMode === "latest" ? "is-active" : ""} onClick={() => setFactMode("latest")}>{t("acc.factLatest")}</button>
              <button type="button" className={factMode === "first" ? "is-active" : ""} onClick={() => setFactMode("first")}>{t("acc.factFirst")}</button>
            </div>
            <small className="acc-hint">
              {data.actual.versions === 1 ? t("acc.factOneVersion") : t("acc.factVersions", {
                n: data.actual.versions, word: plural(data.actual.versions, t("acc.versionWords")), date: formatShortDate(data.actual.first_vintage),
              })}
            </small>
          </div>

          <div className="control-section">
            <h2>{t("acc.agencies")}</h2>
            <div className="acc-select-links">
              <button type="button" className="link-button" onClick={() => setSources(null)}>{t("acc.selectAll")}</button>
              <button type="button" className="link-button" onClick={() => setSources([])}>{t("acc.selectNone")}</button>
            </div>
            {data.sources.map((s) => (
              <label className="check-row" key={s.source_id}>
                <input type="checkbox" checked={s.selected} onChange={() => toggleSource(s.source_id)} />
                <i style={{ background: s.color, opacity: s.selected ? 1 : 0.3 }} />
                <span><b>{s.short}</b><small>{s.name} · {t("acc.releasesCount", { n: s.releases, word: plural(s.releases, t("acc.releaseWords")) })}</small></span>
              </label>
            ))}
          </div>

          <div className="control-section acc-models">
            <h2>{t("acc.models")}</h2>
            {data.models.map((m) => (
              <label className={`check-row is-model ${m.unavailable ? "is-disabled" : ""}`} key={m.code} title={m.description}>
                <input type="checkbox" checked={m.selected && !m.unavailable} disabled={!!m.unavailable} onChange={() => toggleModel(m.code)} />
                <i style={{ ["--c" as string]: MODEL_COLORS[m.code] ?? "#172f4f" }} />
                <span><b>{m.name}</b><small>{m.unavailable ? reasonText(m) : m.description}</small></span>
              </label>
            ))}
            {data.estimation.options.length > 1 && (
              <label className="acc-field">{t("acc.estimation")}
                <select value={data.estimation.frequency ?? ""} onChange={(e) => setModelFrequency(e.target.value as Frequency)}>
                  {data.estimation.options.map((o) => <option key={o.frequency} value={o.frequency}>{estimationLabel(o)}</option>)}
                </select>
              </label>
            )}
            {windowParam != null && (
              <label className="acc-field">{t("acc.windowParam")}
                <input type="number" min={3} max={600} value={windowParam}
                  onChange={(e) => setParam(WINDOW_MODELS, "window", Math.max(3, Number(e.target.value) || 3))} />
              </label>
            )}
            {maParam != null && (
              <label className="acc-field">{t("acc.maQ")}
                <input type="number" min={1} max={60} value={maParam} onChange={(e) => setParam(["ma"], "q", Math.max(1, Number(e.target.value) || 1))} />
              </label>
            )}
            <p className="field-help">{t("acc.estNote")}</p>
          </div>
        </aside>

        <div className="chart-panel">
          <div className="chart-panel__heading">
            <div>
              <p className="eyebrow">{t("acc.chartEyebrow")}</p>
              <h2>{view === "evolution" && selected
                ? t("acc.chartTitleEvolution", { name, period: selectedLabel })
                : t(`acc.chartTitle${frequency}`, { name })}</h2>
              <span>{t("acc.chartSub", { unit: data.unit, window: windowText.toLowerCase() })}</span>
            </div>
            <div className="chart-tools">
              {loading && <span className="acc-loading"><span className="loading-spinner" />{t("common.loading")}</span>}
              <button type="button" className="icon-button" onClick={() => chartRef.current?.zoomAll()}>{t("acc.zoomAll")}</button>
              <button type="button" className="icon-button" onClick={() => chartRef.current?.png(`${id}_${frequency}_accuracy`)}>{t("acc.png")}</button>
            </div>
          </div>
          <div className="segmented acc-view">
            <button type="button" className={view === "periods" ? "is-active" : ""} onClick={() => setView("periods")}>{t(`acc.viewPeriods${frequency}`)}</button>
            <button type="button" className={view === "evolution" ? "is-active" : ""} disabled={!selected}
              onClick={() => { if (selected) { setPeriod(selected.period); setView("evolution"); } }}>
              {t("acc.viewEvolution", { period: selectedLabel })}
            </button>
          </div>
          {!chartSeries.length && <p className="acc-note">{t("acc.noSeries")}</p>}
          {data.rows.length || view === "evolution" ? (
            <AccuracyChart ref={chartRef} data={data} mode={view} period={selected?.period ?? null} series={chartSeries}
              periodLabel={periodLabel} onSelect={setPeriod} />
          ) : <div className="empty-evaluation"><span>◷</span><p>{t("acc.empty")}</p></div>}
        </div>
      </section>

      <section className="acc-block">
        <div className="acc-block__head">
          <div>
            <h2>{t(`acc.tableTitle${frequency}`)}</h2>
            <p>{t("acc.tableText", { unit: data.error_unit })}</p>
          </div>
        </div>
        <div className="acc-table-wrap">
          <table className="acc-table">
            <thead>
              <tr>
                <th className="col-period">{t(`acc.colPeriod${frequency}`)}</th>
                <th className="col-window">{t("acc.colWindow")}</th>
                <th className="col-fact">{t("acc.colFact", { unit: data.value_unit })}</th>
                {chartSeries.map((s) => (
                  <th key={`${s.model ? "m" : "s"}:${s.key}`}>
                    <i className={s.model ? "dash" : ""} style={s.model ? { ["--c" as string]: s.color } : { background: s.color }} />{s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isPending = r.fact == null;
                const cls = isPending ? "is-pending" : r.period === selected?.period ? "is-selected" : "is-clickable";
                return (
                  <tr key={r.period} className={cls} onClick={isPending ? undefined : () => setPeriod(r.period)}>
                    <td className="year"><b>{shortPeriod(r.period)}</b></td>
                    <td className="window">
                      {t("acc.windowFrom", { date: formatShortDate(r.window_start) })}<br />
                      {t("acc.windowTo", { date: formatShortDate(r.window_end) })}
                    </td>
                    <td className="fact">{isPending ? t("acc.pending") : formatValue(r.fact, LEVEL_DIGITS)}</td>
                    {chartSeries.map((s) => {
                      const cell = s.model ? r.models[s.key] : r.picks[s.key];
                      if (!cell) return <td key={s.key}><span className="na">—</span></td>;
                      return (
                        <td key={s.key} style={tint(cell.error)}>
                          <span className="v">{formatValue(cell.value, LEVEL_DIGITS)}</span>
                          {cell.error != null && <span className="e">{signed(cell.error, ERROR_DIGITS)}</span>}
                          <small>{s.model ? t("acc.tipModel", { date: formatShortDate(asOf(r.window_end)) }) : issuedLabel(r.picks[s.key])}</small>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {data.rows.length > RECENT_ROWS && (
          <button type="button" className="acc-more" onClick={() => setShowAll(!showAll)}>
            {showAll ? t("acc.showRecent", { n: RECENT_ROWS }) : t("acc.showAll", { n: data.rows.length })}
          </button>
        )}
      </section>

      {(metricRows.length > 0 || metrics.insufficient.length > 0) && (
        <section className="acc-block">
          <div className="acc-block__head">
            <div>
              <h2>{metrics.comparable ? t("acc.metricsTitle", { range }) : t("acc.metricsTitleOwn")}</h2>
              <p>{metrics.comparable ? t("acc.metricsText", { min: metrics.min_periods }) : t("acc.metricsTextOwn", { min: metrics.min_periods })}</p>
            </div>
          </div>
          {metricRows.length > 0 && (
            <div className="acc-table-wrap">
              <table className="acc-table acc-metrics">
                <thead>
                  <tr>
                    <th>{t("acc.colSeries")}</th>
                    <th className="num">{t("acc.colN")} <InfoTip text={t("acc.tipN")} /></th>
                    <th className="num">{t("acc.colMae", { unit: data.error_unit })} <InfoTip text={t("acc.tipMae")} /></th>
                    <th className="num">{t("acc.colRmse", { unit: data.error_unit })} <InfoTip text={t("acc.tipRmse")} /></th>
                    <th className="num">{t("acc.colMape")} <InfoTip text={t("acc.tipMape", { min: formatValue(metrics.mape_min_actual, 0) })} /></th>
                    <th className="num">{t("acc.colMe", { unit: data.error_unit })} <InfoTip text={t("acc.tipMe")} /></th>
                    <th className="num">{t("acc.colRatio")} <InfoTip text={t("acc.tipRatio")} /></th>
                  </tr>
                </thead>
                <tbody>
                  {metricRows.map((m) => {
                    const color = m.kind === "source" ? sourceOf.get(m.key)?.color : MODEL_COLORS[m.key];
                    return (
                      <tr key={`${m.kind}:${m.key}`}>
                        <td>
                          <i className={m.kind === "model" ? "dash" : ""} style={m.kind === "model" ? { ["--c" as string]: color } : { background: color }} />
                          <b>{seriesName(m.kind, m.key)}</b>
                          {m.kind === "model" && <span className="tag">{t("acc.modelTag")}</span>}
                        </td>
                        <td className="num">{m.n}</td>
                        <td className="num">{strong(m.mae, bestMae)}</td>
                        <td className="num">{strong(m.rmse, bestRmse)}</td>
                        <td className="num">{strong(m.mape, bestMape, 1)}</td>
                        <td className="num">{signed(m.me, METRIC_DIGITS)}</td>
                        <td className="num">{strong(m.ratio_rw, bestRatio)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {metrics.insufficient.length > 0 && (
            <p className="acc-footnote">
              {t("acc.insufficient", {
                min: metrics.min_periods,
                list: metrics.insufficient.map((x) => `${seriesName(x.kind, x.key)} — ${x.n}`).join(", "),
              })}
            </p>
          )}
        </section>
      )}
      {error && <div className="inline-error">{error}</div>}
    </section>
  );
}
