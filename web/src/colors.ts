export const ACTUAL_COLOR = "#1f8ac0";
export const MODEL_COLORS: Record<string, string> = {
  rw: "#172f4f", rwd: "#a4482e", rws: "#4c6b35", rwds: "#864c9e", ts: "#cc7a00", ma: "#5b6b7a", arima: "#cf2e5b",
};

// Older releases get their own saturated tones, not light shades of the source colour (variant A, 13.10.2026).
const VINTAGE_PALETTE = [
  "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#c99a00",
  "#a6761d", "#cc79a7", "#5f6b2f", "#d62728", "#4d4d4d", "#8c564b",
];

function rgb(hex: string): number[] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function distance(a: string, b: string): number {
  const [x, y] = [rgb(a), rgb(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

/** `count` distinct colours, skipping tones close to colours already on the chart. */
export function distinctColors(count: number, avoid: string[]): string[] {
  const free = VINTAGE_PALETTE.filter((c) => avoid.every((a) => distance(c, a) > 60));
  const pool = free.length ? free : VINTAGE_PALETTE;
  return Array.from({ length: count }, (_, i) => pool[i % pool.length]);
}

export function withAlpha(hex: string, alpha: number): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
