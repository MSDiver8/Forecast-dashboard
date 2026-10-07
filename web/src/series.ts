import { ACTUAL_COLOR, MODEL_COLORS, sourceColor, vintageShade } from "./colors";
import { t } from "./i18n";
import type { ModelRun, View } from "./types";

export interface SeriesPoint { period: string; value: number; lower?: number | null; upper?: number | null }

export interface SeriesDef {
  key: string;
  kind: "actual" | "release" | "model";
  label: string;
  sublabel: string;
  color: string;
  dashed: boolean;
  sourceId?: string;
  vintage?: string;
  points: SeriesPoint[];
}

/** Forecast part of a release plus the last known point before it, so the line starts at its vintage. */
function forecastPath(points: View["sources"][number]["releases"][number]["points"]): SeriesPoint[] {
  const first = points.findIndex((p) => p.kind === "forecast");
  if (first < 0) return points.map((p) => ({ period: p.period, value: p.value, lower: p.lower, upper: p.upper }));
  const from = Math.max(0, first - 1);
  return points.slice(from).map((p, i) => ({
    period: p.period,
    value: p.value,
    lower: i === 0 && from < first ? null : p.lower,
    upper: i === 0 && from < first ? null : p.upper,
  }));
}

export function buildSeries(view: View, runs: ModelRun[], allSources: string[]): SeriesDef[] {
  const result: SeriesDef[] = [];
  if (view.actual) {
    result.push({
      key: "actual",
      kind: "actual",
      label: t("chart.actual"),
      sublabel: view.actual.title,
      color: ACTUAL_COLOR,
      dashed: false,
      vintage: view.actual.vintage_date,
      points: view.actual.points.map((p) => ({ period: p.period, value: p.value })),
    });
  }
  for (const source of view.sources) {
    const base = sourceColor(source.source_id, allSources);
    const releases = [...source.releases].sort((a, b) => a.vintage_date.localeCompare(b.vintage_date));
    releases.forEach((release, index) => {
      result.push({
        key: `r:${release.release_id}`,
        kind: "release",
        label: `${source.organization} · ${release.title}`,
        sublabel: source.derived_from ? t("chart.derived") : source.name,
        color: vintageShade(base, index, releases.length),
        dashed: false,
        sourceId: source.source_id,
        vintage: release.vintage_date,
        points: forecastPath(release.points),
      });
    });
  }
  const anchorValue = (period: string) => view.actual?.points.find((p) => p.period === period)?.value;
  for (const run of runs) {
    const anchor = anchorValue(run.origin);
    result.push({
      key: `m:${run.model}`,
      kind: "model",
      label: `${run.name} · ${t("chart.model")}`,
      sublabel: run.description,
      color: MODEL_COLORS[run.model] ?? "#555",
      dashed: true,
      points: [
        ...(anchor != null ? [{ period: run.origin, value: anchor }] : []),
        ...run.points.map((p) => ({ period: p.period, value: p.value, lower: p.lower95, upper: p.upper95 })),
      ],
    });
  }
  return result;
}

export function allPeriods(series: SeriesDef[]): string[] {
  return [...new Set(series.flatMap((s) => s.points.map((p) => p.period)))].sort();
}
