import type { Evaluation, Frequency, ModelRun, ModelSpec, Overview, RegistrySource, SeriesResponse } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not JSON */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  overview: () => request<Overview>("/api/featured"),
  series: (id: string, frequency?: Frequency) =>
    request<SeriesResponse>(`/api/series/${id}${frequency ? `?frequency=${frequency}` : ""}`),
  evaluation: (id: string, frequency: Frequency) => request<Evaluation>(`/api/evaluation/${id}?frequency=${frequency}`),
  sources: () => request<RegistrySource[]>("/api/sources"),
  models: () => request<ModelSpec[]>("/api/models"),
  runModel: (body: {
    featured: string; frequency: Frequency; model: string; horizon: number;
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
