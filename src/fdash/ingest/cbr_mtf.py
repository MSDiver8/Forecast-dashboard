"""Bank of Russia medium-term forecast: the key parameters table of each forecast PDF."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pdfplumber

from fdash.ingest.base import Connector, Observation, Parsed, Release, SourceStructureError, http_get
from fdash.ingest.registry import register

BASE = "https://www.cbr.ru"
LIST_PAGES = [f"{BASE}/dkp/mp_dec/decision_key_rate/", f"{BASE}/about_br/publ/ddkp/"]
LINK = re.compile(r'href="(/[^"]*/forecast_(\d{2})(\d{2})(\d{2})\.pdf)"')
ROWS = {
    "Инфляция, в %, декабрь к декабрю предыдущего года": "cpi_dec",
    "Инфляция, в среднем за год, в % к предыдущему году": "cpi_avg",
    "Ключевая ставка, в среднем за год, в % годовых": "key_rate_avg",
    "Валовой внутренний продукт": "gdp_growth",
}
NUM = r"\(?[+-]?\d+(?:,\d)?\)?"
CELL = re.compile(rf"^({NUM})(?:[-–]({NUM}))?(\d?)$")
NEGATIVE_RANGE = re.compile(rf"^-\(({NUM})[-–]({NUM})\)(\d?)$")  # '-(8,0-10,0)': a fall of 8-10%
YEAR = re.compile(r"\b(20\d{2})\b")
MONTHS_RU = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]


def parse_number(text: str) -> float:
    return float(text.strip("()").replace(",", ".").replace("+", ""))


def parse_cell(token: str) -> tuple[float, float | None, float | None]:
    """'6,0–7,0' -> (6.5, 6.0, 7.0); '4,0' -> (4.0, None, None); a trailing footnote digit is dropped."""
    negative = NEGATIVE_RANGE.match(token)
    if negative:
        a, b = -parse_number(negative.group(1)), -parse_number(negative.group(2))
        return (a + b) / 2, min(a, b), max(a, b)
    match = CELL.match(token)
    if not match:
        raise SourceStructureError(f"unexpected cell {token!r}")
    low = parse_number(match.group(1))
    if match.group(2) is None:
        return low, None, None
    high = parse_number(match.group(2))
    return (low + high) / 2, low, high


def list_links(html: str) -> dict[date, str]:
    found = {}
    for href, yy, mm, dd in LINK.findall(html):
        found.setdefault(date(2000 + int(yy), int(mm), int(dd)), BASE + href)
    return found


def parse_table(text: str) -> tuple[list[str], dict[str, list[tuple[float, float | None, float | None]]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_row = next(
        (i for i, line in enumerate(lines) if any(line.startswith(label) for label in ROWS)), None
    )
    if first_row is None:
        raise SourceStructureError("forecast table rows not found")
    years = YEAR.findall(" ".join(line for line in lines[:first_row] if "заседания" not in line))
    if len(years) < 3:
        raise SourceStructureError(f"header years not found: {years}")
    table: dict[str, list[tuple[float, float | None, float | None]]] = {}
    for line in lines[first_row:]:
        for label, indicator_id in ROWS.items():
            if indicator_id in table or not line.startswith(label + " "):
                continue
            tokens = line[len(label) :].split()
            if len(tokens) != len(years):
                raise SourceStructureError(f"{label}: {len(tokens)} values for {len(years)} years: {tokens}")
            table[indicator_id] = [parse_cell(token) for token in tokens]
    missing = {"cpi_dec", "key_rate_avg", "gdp_growth"} - set(table)
    if missing:
        raise SourceStructureError(f"rows not found: {sorted(missing)}")
    return years, table


class CbrMtf(Connector):
    source_id = "cbr_mtf"
    name = "Среднесрочный прогноз"
    organization = "Банк России"
    url = f"{BASE}/dkp/mp_dec/decision_key_rate/"
    license = "Материалы сайта Банка России, со ссылкой на источник"
    access = "PDF по итогам опорных заседаний (исключение из критерия 1, ТЗ 4.1)"

    def list_releases(self) -> list[Release]:
        links: dict[date, str] = {}
        for page in LIST_PAGES:
            response = http_get(page)
            response.raise_for_status()
            for day, url in list_links(response.text).items():
                links.setdefault(day, url)
        since = date.today() - timedelta(days=365 * 5 + 31)
        return [
            Release(
                release_id=f"cbr_mtf_{day:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"Прогноз ЦБ, {MONTHS_RU[day.month - 1]} {day.year}",
                vintage_date=day,
                url=url,
                filename=url.rsplit("/", 1)[1],
            )
            for day, url in sorted(links.items())
            if day >= since
        ]

    def parse(self, raw: Path, release: Release) -> Parsed:
        with pdfplumber.open(raw) as pdf:
            text = pdf.pages[0].extract_text() or ""
        if "Основные параметры прогноза Банка России" not in text:
            raise SourceStructureError(f"{raw.name}: forecast table title not found")
        years, table = parse_table(text)
        observations = [
            Observation(
                indicator_id, "RU", year, "A", value, "estimate" if i == 0 else "forecast", lower, upper
            )
            for indicator_id, cells in table.items()
            for i, (year, (value, lower, upper)) in enumerate(zip(years, cells, strict=True))
        ]
        return Parsed(observations, data_cutoff=years[0])


register(CbrMtf())
