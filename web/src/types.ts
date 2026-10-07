export type Frequency = "A" | "Q" | "M" | "MY";

export interface Indicator {
  id: string;
  name: string;
  unit: string;
  transform: string;
  base?: string | null;
  groups: string[];
  description?: string | null;
  precision: number;
  actual_source?: string | null;
}

export interface Area { id: string; name: string; kind: string }
export interface Group { id: string; name: string }

export interface Pair {
  indicator_id: string;
  area_id: string;
  frequencies: Record<string, string[]>;
  source_count: number;
  has_actual: boolean;
}

export interface Catalog {
  groups: Group[];
  areas: Area[];
  indicators: Indicator[];
  pairs: Pair[];
  sources: Record<string, { organization: string; name: string; role: string }>;
  notes: Record<string, string>;
}

export interface Point {
  period: string;
  value: number;
  kind: "forecast" | "estimate" | "actual";
  lower?: number | null;
  upper?: number | null;
}

export interface ReleaseRef { release_id: string; title: string; vintage_date: string }
export interface ReleaseData extends ReleaseRef { points: Point[] }

export interface SourceView {
  source_id: string;
  organization: string;
  name: string;
  note?: string | null;
  derived_from?: string | null;
  available_releases: ReleaseRef[];
  releases: ReleaseData[];
}

export interface View {
  indicator: Indicator;
  area: Area;
  frequency: Frequency;
  actual: (ReleaseData & { source_id: string; derived_from?: string | null }) | null;
  sources: SourceView[];
}

export interface ModelSpec { code: string; name: string; description: string; params: Record<string, unknown> }

export interface ModelPoint {
  period: string;
  value: number;
  lower80: number;
  upper80: number;
  lower95: number;
  upper95: number;
}

export interface ModelRun {
  run_id: string;
  model: string;
  name: string;
  description: string;
  origin: string;
  info: Record<string, unknown>;
  points: ModelPoint[];
}

export interface StatusData {
  sources: {
    source_id: string; organization: string; name: string; role: string; url: string; license: string;
    releases: number; first_vintage: string | null; last_vintage: string | null;
  }[];
  log: {
    source_id: string; started_at: string; finished_at: string | null; status: string;
    releases: number | null; rows_added: number | null; error: string | null;
  }[];
}
