export type Frequency = "A" | "Q" | "M";
export type AppView = "overview" | "indicator" | "sources" | "about";

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

export interface Overview {
  cards: Card[];
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

export interface Evaluation {
  actual: { source_id: string; short: string } | null;
  sources: {
    source_id: string;
    short: string;
    color: string;
    organization: string;
    name: string;
    horizons: { horizon: number; n: number; mae: number; bias: number }[];
    releases: {
      release_id: string;
      title: string;
      vintage_date: string;
      mae: number;
      rmse: number;
      bias: number;
      points: { period: string; forecast: number; actual: number; error: number; horizon: number }[];
    }[];
  }[];
}

export interface RegistrySource extends SourceMeta {
  role: "forecast" | "actual";
  license: string;
  access: string;
  releases: number;
  first_vintage: string | null;
  last_vintage: string | null;
  indicators: string[];
}
