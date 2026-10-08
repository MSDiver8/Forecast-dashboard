export const ACTUAL_COLOR = "#1f8ac0";
export const MODEL_COLORS: Record<string, string> = {
  rw: "#172f4f", rwd: "#a4482e", rws: "#4c6b35", rwds: "#864c9e", ts: "#cc7a00", ma: "#5b6b7a", arima: "#cf2e5b",
};

/** Older vintages of a source are lighter shades of its colour; the newest one is the full colour. */
export function vintageShade(hex: string, index: number, count: number): string {
  if (count <= 1 || index >= count - 1) return hex;
  const share = 0.3 + 0.5 * (index / Math.max(1, count - 2));
  const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `#${rgb.map((c) => Math.round(255 - (255 - c) * share).toString(16).padStart(2, "0")).join("")}`;
}

export function withAlpha(hex: string, alpha: number): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
