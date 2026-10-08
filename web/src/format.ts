const monthFormatter = new Intl.DateTimeFormat("ru-RU", {
  month: "short",
  year: "numeric",
});

const fullDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function formatMonth(value: string): string {
  return monthFormatter.format(new Date(`${value}T00:00:00`)).replace(" г.", "");
}

export function formatDate(value: string): string {
  return fullDateFormatter.format(new Date(`${value}T00:00:00`));
}

export function formatNumber(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits,
  }).format(value);
}

export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, 1)}%`;
}

export function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1000) {
    return new Intl.NumberFormat("ru-RU", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  }
  return formatNumber(value, 1);
}

export async function downloadChartAsPng(
  containerId: string,
  filename: string,
): Promise<void> {
  const container = document.getElementById(containerId);
  const svg = container?.querySelector("svg");
  if (!container || !svg) {
    throw new Error("График ещё не готов к скачиванию");
  }

  const bounds = svg.getBoundingClientRect();
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(bounds.width));
  clone.setAttribute("height", String(bounds.height));

  const source = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const image = new Image();

  await new Promise<void>((resolve, reject) => {
    image.onload = () => {
      const scale = 2;
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bounds.width * scale));
      canvas.height = Math.max(1, Math.round(bounds.height * scale));
      const context = canvas.getContext("2d");
      if (!context) {
        reject(new Error("Не удалось подготовить изображение"));
        return;
      }

      context.scale(scale, scale);
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, bounds.width, bounds.height);
      context.drawImage(image, 0, 0, bounds.width, bounds.height);
      canvas.toBlob((png) => {
        if (!png) {
          reject(new Error("Не удалось сформировать PNG"));
          return;
        }
        const link = document.createElement("a");
        link.href = URL.createObjectURL(png);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        resolve();
      }, "image/png");
    };
    image.onerror = () => reject(new Error("Не удалось прочитать график"));
    image.src = url;
  });

  URL.revokeObjectURL(url);
}

const SHORT_MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

/** 2026 -> "2026"; 2026-Q3 -> "III кв. 2026"; 2026-07 -> "июл 2026". */
export function formatPeriod(period: string): string {
  let m = /^(\d{4})-(\d{2})$/.exec(period);
  if (m) return `${SHORT_MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  m = /^(\d{4})-Q([1-4])$/.exec(period);
  if (m) return `${["I", "II", "III", "IV"][Number(m[2]) - 1]} кв. ${m[1]}`;
  return period;
}

export function formatValue(value: number | null | undefined, precision = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: precision, maximumFractionDigits: precision }).format(value);
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(`${value.slice(0, 10)}T00:00:00`));
}

/** The period that contains a date, at the given frequency. */
export function periodOf(day: string, frequency: "A" | "Q" | "M"): string {
  const [y, m] = [Number(day.slice(0, 4)), Number(day.slice(5, 7))];
  if (frequency === "M") return `${y}-${String(m).padStart(2, "0")}`;
  if (frequency === "Q") return `${y}-Q${Math.floor((m - 1) / 3) + 1}`;
  return String(y);
}

export function shiftPeriod(period: string, steps: number): string {
  let m = /^(\d{4})-(\d{2})$/.exec(period);
  if (m) {
    const index = Number(m[1]) * 12 + Number(m[2]) - 1 + steps;
    return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
  }
  m = /^(\d{4})-Q([1-4])$/.exec(period);
  if (m) {
    const index = Number(m[1]) * 4 + Number(m[2]) - 1 + steps;
    return `${Math.floor(index / 4)}-Q${(index % 4) + 1}`;
  }
  return String(Number(period) + steps);
}
