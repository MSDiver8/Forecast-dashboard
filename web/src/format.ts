const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

export function formatPeriod(period: string): string {
  let m = /^(\d{4})-(\d{2})$/.exec(period);
  if (m) return `${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  m = /^(\d{4})-Q([1-4])$/.exec(period);
  if (m) return `${["I", "II", "III", "IV"][Number(m[2]) - 1]} кв. ${m[1]}`;
  return period;
}

export function formatNumber(value: number | null | undefined, precision = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: precision, maximumFractionDigits: precision }).format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(`${value.slice(0, 10)}T00:00:00`);
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}
