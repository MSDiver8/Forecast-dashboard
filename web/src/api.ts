import type { Catalog, Frequency, ModelRun, ModelSpec, StatusData, View } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not JSON */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export interface ViewQuery {
  indicator: string;
  area: string;
  frequency: Frequency;
  mode: "latest" | "asof" | "manual";
  asof?: string;
  sources?: string[];
  releases?: string[];
  lastN?: number;
}

export const api = {
  catalog: () => request<Catalog>("/api/catalog"),
  models: () => request<ModelSpec[]>("/api/models"),
  status: () => request<StatusData>("/api/status"),
  view: (q: ViewQuery) => {
    const params = new URLSearchParams({ indicator: q.indicator, area: q.area, frequency: q.frequency, mode: q.mode });
    if (q.asof) params.set("asof", q.asof);
    if (q.sources) params.set("sources", q.sources.join(","));
    if (q.releases?.length) params.set("releases", q.releases.join(","));
    if (q.lastN) params.set("last_n", String(q.lastN));
    return request<View>(`/api/view?${params}`);
  },
  runModel: (body: {
    indicator: string; area: string; frequency: Frequency; model: string; horizon: number;
    cutoff?: string; asof?: string; params?: Record<string, unknown>;
  }) => request<ModelRun>("/api/models/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  export: async (title: string, columns: string[], rows: (string | number | null)[][], format: "csv" | "xlsx") => {
    const response = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, columns, rows, format }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${title}.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
  },
};
