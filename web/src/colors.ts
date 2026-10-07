// Chart palette from the customer's prototype; a colour is fixed to a source.
export const SOURCE_COLORS = [
  "#168443", "#7062bf", "#ed7b24", "#245285", "#9a4d8d", "#4b7e88",
  "#b44343", "#936728", "#3274a1", "#7b8540", "#b55d91", "#315f53",
];
export const ACTUAL_COLOR = "#62b4dc";
export const MODEL_COLORS: Record<string, string> = {
  rw: "#172f4f", rwd: "#a4482e", rws: "#4c6b35", rwds: "#864c9e", ts: "#cc7a00", ma: "#5b6b7a", arima: "#cf2e5b",
};

export function sourceColor(sourceId: string, allSources: string[]): string {
  const index = [...allSources].sort().indexOf(sourceId);
  return SOURCE_COLORS[(index < 0 ? 0 : index) % SOURCE_COLORS.length];
}

/** Shade of a source colour: old vintages lighter, the newest one full colour. */
export function vintageShade(hex: string, index: number, count: number): string {
  if (count <= 1) return hex;
  const share = 0.25 + 0.75 * (index / (count - 1));
  const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const mixed = rgb.map((c) => Math.round(255 - (255 - c) * share));
  return `#${mixed.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}
