export type Frequency = "A" | "Q" | "M";
export type AppView = "overview" | "indicator" | "sources";

export interface Featured {
  id: string;
  indicator: string;
  area: string;
  frequency: Frequency;
  category: string;
  title: string;
  short: string;
  subtitle?: string | null;
  description: string;
  added?: string | null;
}

export interface Indicator {
  id: string;
  name: string;
  unit: string;
  base?: string | null;
  description?: string | null;
  precision: number;
}

export interface Point {
  period: string;
  value: number;
  kind?: "forecast" | "estimate" | "actual";
  lower?: number | null;
  upper?: number | null;
}

export interface Release {
  release_id: string;
  title: string;
  vintage_date: string;
  points: Point[];
}

export interface SourceMeta {
  source_id: string;
  organization: string;
  name: string;
  url: string;
  short: string;
  color: string;
  description?: string | null;
  caveat?: string | null;
}

export interface SourceSeries extends SourceMeta {
  note?: string | null;
  derived_from?: string | null;
  releases: Release[];
}

export interface SeriesResponse {
  featured: Featured;
  indicator: Indicator;
  frequency: Frequency;
  frequencies: Frequency[];
  actual: (SourceMeta & { derived_from?: string | null; releases: Release[] }) | null;
  sources: SourceSeries[];
}

export interface Card extends Featured {
  unit: string;
  precision: number;
  fact_source: string | null;
  last_fact: { period: string; value: number } | null;
  sparkline: { period: string; value: number }[];
  targets: string[];
  latest: {
    source_id: string;
    short: string;
    color: string;
    release_title: string;
    vintage_date: string;
    values: Record<string, Point | null>;
  }[];
  source_count: number;
  release_count: number;
  last_update: string | null;
  frequencies: Frequency[];
}

export interface NewsBlock {
  featured: string;
  title: string;
  published: string;
  text: string;
  unit: string;
  precision: number;
  frequency: Frequency;
  fact: { short: string; points: { period: string; value: number }[] } | null;
  lines: {
    source_id: string;
    short: string;
    color: string;
    release_title: string;
    vintage_date: string;
    points: { period: string; value: number }[];
  }[];
}

export interface Overview {
  cards: Card[];
  news: NewsBlock | null;
  totals: { indicators: number; sources: number; releases: number; last_update: string | null };
  latest_releases: { title: string; vintage_date: string; short: string; color: string }[];
}

export interface ModelSpec { code: string; name: string; description: string; params: Record<string, unknown> }

export interface ModelRun {
  run_id: string;
  model: string;
  name: string;
  description: string;
  origin: string;
  anchor: number;
  info: Record<string, unknown>;
  points: { period: string; value: number; lower80: number; upper80: number; lower95: number; upper95: number }[];
}

export interface EvalForecast { vintage_date: string; value: number; title: string; approx: boolean }

export interface EvalPick extends EvalForecast { error: number | null }

export interface EvalModelValue { value: number; error: number | null }

export interface EvalSource {
  source_id: string;
  short: string;
  name: string;
  organization: string;
  color: string;
  description: string | null;
  caveat: string | null;
  releases: number;
  first_vintage: string;
  last_vintage: string;
  selected: boolean;
}

export interface EvalModel {
  code: string;
  name: string;
  description: string;
  selected: boolean;
  params: { window?: number; q?: number };
  unavailable: { reason: "seasonal" | "short" | "fact"; need?: number; have?: number } | null;
}

export interface EvalRow {
  period: string;
  window_start: string;
  window_end: string;
  fact: number | null;
  picks: Record<string, EvalPick>;
  models: Record<string, EvalModelValue>;
  rw_error: number | null;
}

export interface EvalMetric {
  kind: "source" | "model";
  key: string;
  partial: boolean;
  missing: string[];
  n: number;
  mae: number;
  rmse: number;
  me: number;
  mape: number | null;
  ratio_rw: number | null;
  errors: number[];
}

export interface EvalPeriod {
  period: string;
  start: string;
  end: string;
  fact: number | null;
  windows: { start: string; end: string }[];
}

export interface EvalEvolution {
  period: string;
  start: string;
  end: string;
  fact: number | null;
  window: { start: string; end: string };
  tracks: Record<string, EvalForecast[]>;
  models: Record<string, { date: string; value: number }[]>;
}

export type FactMode = "latest" | "first";

export interface Evaluation {
  featured: string;
  frequency: Frequency;
  unit: string;
  value_unit: string;
  error_unit: string;
  transform: string;
  fact_shape: "point" | "segment";
  actual: {
    source_id: string; short: string; name: string; organization: string;
    versions: number; first_vintage: string; last_vintage: string;
  } | null;
  fact_mode: FactMode;
  window: number;
  window_count: number;
  sources: EvalSource[];
  models: EvalModel[];
  estimation: {
    frequency: Frequency | null;
    convert: "same" | "mean" | "december" | null;
    options: { frequency: Frequency; convert: "same" | "mean" | "december" }[];
  };
  periods: EvalPeriod[];
  context: { label: string; frequency: Frequency; points: { period: string; date: string; value: number }[] } | null;
  rows: EvalRow[];
  metrics: {
    start: string | null;
    end: string | null;
    available: string[];
    periods: string[];
    contiguous: boolean;
    mape_min_actual: number;
    rows: EvalMetric[];
    partial: { kind: "source" | "model"; key: string; n: number; total: number; missing: string[]; included: boolean }[];
    empty: { kind: "source" | "model"; key: string }[];
  };
  evolution: EvalEvolution | null;
}

export interface EvaluationRequest {
  featured: string;
  frequency: Frequency;
  window: number | null;
  fact: FactMode;
  sources: string[] | null;
  models: { code: string; params: { window?: number; q?: number } }[];
  model_frequency: Frequency | null;
  period: string | null;
  evolution: boolean;
  metrics_from: string | null;
  metrics_to: string | null;
  metrics_include: string[];
}

export interface RegistrySource extends SourceMeta {
  role: "forecast" | "actual";
  license: string;
  access: string;
  releases: number;
  first_vintage: string | null;
  last_vintage: string | null;
  checked_at: string | null;
  check_error: string | null;
  check_error_at: string | null;
  indicators: string[];
}
