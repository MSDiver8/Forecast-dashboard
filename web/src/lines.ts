import { ACTUAL_COLOR, MODEL_COLORS, vintageShade } from "./colors";
import { periodOf, shiftPeriod } from "./format";
import { t } from "./i18n";
import type { Frequency, ModelRun, Point, Release, SeriesResponse, SourceSeries } from "./types";

export interface LinePoint {
  period: string;
  value: number;
  lower?: number | null;   // published range, or the 95% interval of a model
  upper?: number | null;
  lower80?: number | null; // models only
  upper80?: number | null;
}

export interface ChartLine {
  key: string;
  group: string;          // legend entry: the source, "Факт" or the model
  kind: "actual" | "release" | "model";
  label: string;          // full name in tooltips and tables
  vintage?: string;
  color: string;
  latest: boolean;        // the newest selected release of its source: thicker line and end label
  connect: boolean;       // false when the source publishes isolated periods (e.g. only Q4 of each year)
  points: LinePoint[];
}

function consecutive(points: LinePoint[]): boolean {
  return points.every((p, i) => i === 0 || shiftPeriod(points[i - 1].period, 1) === p.period);
}

const STALE_DAYS = 365;

/** Sources whose newest release is a year older than the newest release overall are hidden by default. */
export function staleSources(data: SeriesResponse): Set<string> {
  const newest = (s: SourceSeries) => s.releases[s.releases.length - 1]?.vintage_date ?? "";
  const overall = data.sources.map(newest).sort().pop() ?? "";
  const limit = new Date(`${overall}T00:00:00`);
  limit.setDate(limit.getDate() - STALE_DAYS);
  const cut = limit.toISOString().slice(0, 10);
  return new Set(data.sources.filter((s) => newest(s) < cut).map((s) => s.source_id));
}

export function defaultSelection(data: SeriesResponse): Set<string> {
  const stale = staleSources(data);
  return new Set(
    data.sources.filter((s) => !stale.has(s.source_id)).map((s) => s.releases[s.releases.length - 1].release_id),
  );
}

/** Releases shown: the manual selection, or in "as of" mode the newest release of each source by that date. */
export function effectiveSelection(data: SeriesResponse, selected: Set<string>, asof: string): Set<string> {
  if (!asof) return selected;
  const chosen = new Set<string>();
  for (const s of data.sources) {
    const known = s.releases.filter((r) => r.vintage_date <= asof);
    if (known.length) chosen.add(known[known.length - 1].release_id);
  }
  return chosen;
}

/** Actual series known at `asof`: the newest actual release by then (else today's), cut before that date. */
export function actualPoints(data: SeriesResponse, asof: string, frequency: Frequency): Point[] {
  if (!data.actual) return [];
  const releases = data.actual.releases;
  const known = asof ? releases.filter((r) => r.vintage_date <= asof) : releases;
  const release = (known.length ? known : releases)[known.length ? known.length - 1 : releases.length - 1];
  if (!asof) return release.points;
  const lastKnown = shiftPeriod(periodOf(asof, frequency), -1);
  return release.points.filter((p) => p.period <= lastKnown);
}

/** Forecast part of a release plus the last known value before it, so the line starts at its vintage. */
function forecastPath(release: Release): LinePoint[] {
  const first = release.points.findIndex((p) => p.kind === "forecast");
  const from = first < 0 ? 0 : Math.max(0, first - 1);
  return release.points.slice(from).map((p, i) => ({
    period: p.period,
    value: p.value,
    lower: first > 0 && i === 0 ? null : p.lower,
    upper: first > 0 && i === 0 ? null : p.upper,
  }));
}

export function buildLines(
  data: SeriesResponse, shown: Set<string>, asof: string, runs: ModelRun[], frequency: Frequency,
): ChartLine[] {
  const lines: ChartLine[] = [];
  const fact = actualPoints(data, asof, frequency);
  if (data.actual && fact.length) {
    lines.push({
      key: "actual", kind: "actual", group: t("chart.fact"), label: `${t("chart.fact")} · ${data.actual.short}`,
      color: ACTUAL_COLOR, latest: true, connect: false, points: fact.map((p) => ({ period: p.period, value: p.value })),
    });
  }
  for (const source of data.sources) {
    const releases = source.releases.filter((r) => shown.has(r.release_id));
    // Newest first, so that the legend takes the full colour of the source.
    [...releases].reverse().forEach((release, reversedIndex) => {
      const index = releases.length - 1 - reversedIndex;
      const points = forecastPath(release);
      lines.push({
        key: `r:${release.release_id}`,
        kind: "release",
        group: source.short,
        label: `${source.short} · ${release.title}`,
        vintage: release.vintage_date,
        color: vintageShade(source.color, index, releases.length),
        latest: index === releases.length - 1,
        connect: consecutive(points),
        points,
      });
    });
  }
  for (const run of runs) {
    lines.push({
      key: `m:${run.model}`,
      kind: "model",
      group: `${run.name} · ${t("chart.model")}`,
      label: `${run.name} · ${t("chart.model")}`,
      color: MODEL_COLORS[run.model] ?? "#555",
      latest: true,
      connect: true,
      points: [
        { period: run.origin, value: run.anchor },
        ...run.points.map((p) => ({
          period: p.period, value: p.value, lower: p.lower95, upper: p.upper95, lower80: p.lower80, upper80: p.upper80,
        })),
      ],
    });
  }
  return lines;
}

export function categories(lines: ChartLine[]): string[] {
  return [...new Set(lines.flatMap((l) => l.points.map((p) => p.period)))].sort();
}
