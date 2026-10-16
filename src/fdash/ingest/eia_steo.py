"""EIA Short-Term Energy Outlook: monthly Brent spot price, one XLSX per release."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from fdash.ingest.base import Connector, Observation, Parsed, Release, SourceStructureError, http_get
from fdash.ingest.registry import register

PAGE = "https://www.eia.gov/outlooks/steo/outlook.php"
ARCHIVE = "https://www.eia.gov/outlooks/steo/archives/"
MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
    )
}
ROW_DATE = re.compile(r"<td>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>")
ROW_FILE = re.compile(r"archives/([a-z]{3}\d{2})_base\.xlsx")
CURRENT_DATE = re.compile(r"Release Date:</strong>\s*([A-Z][a-z]+ \d{1,2}, \d{4})")
SERIES = {"BREPUUS": ("brent_price", "WORLD")}


def parse_release_page(html: str, today: date) -> list[tuple[str, date]]:
    """(file stem, publication date) for the current release and the archive."""
    found: dict[str, date] = {}
    for row in html.split("<tr")[1:]:
        published, stem = ROW_DATE.search(row), ROW_FILE.search(row)
        if published and stem:
            found[stem.group(1)] = datetime.strptime(published.group(1), "%m/%d/%Y").date()
    current = CURRENT_DATE.search(html)
    if current:
        published = datetime.strptime(current.group(1), "%B %d, %Y").date()
        stem = published.strftime("%b%y").lower()
        found.setdefault(stem, published)
    return sorted(((s, d) for s, d in found.items() if d <= today), key=lambda item: item[1])


class EiaSteo(Connector):
    source_id = "eia_steo"
    name = "Short-Term Energy Outlook"
    organization = "EIA"
    url = PAGE
    license = "Public domain (U.S. Government)"
    access = "XLSX по стабильной ссылке"

    def list_releases(self) -> list[Release]:
        response = http_get(PAGE)
        response.raise_for_status()
        return [
            Release(
                release_id=f"eia_steo_{published:%Y_%m}",
                source_id=self.source_id,
                title=f"STEO {published:%m.%Y}",
                vintage_date=published,
                url=f"{ARCHIVE}{stem}_base.xlsx",
                filename=f"{stem}_base.xlsx",
            )
            for stem, published in parse_release_page(response.text, date.today())
        ]

    def parse(self, raw: Path, release: Release) -> Parsed:
        wb = load_workbook(raw, read_only=True, data_only=True)
        if "Dates" not in wb.sheetnames or "2tab" not in wb.sheetnames:
            raise SourceStructureError(f"{raw.name}: sheets Dates/2tab not found")
        sheet = wb["2tab"]
        rows = {sheet.cell(r, 1).value: r for r in range(1, min(sheet.max_row, 200) + 1)}
        series = {}
        for code in SERIES:
            if code not in rows:
                raise SourceStructureError(f"{raw.name}: series {code} not found on 2tab")
            series[code] = read_months(sheet, rows[code])
        cutoff_code = wb["Dates"].cell(7, 4).value
        if isinstance(cutoff_code, int):
            cutoff = f"{cutoff_code // 100:04d}-{cutoff_code % 100:02d}"
        elif cutoff_code is None:
            cutoff = styled_cutoff(raw.name, series["BREPUUS"])
        else:
            raise SourceStructureError(f"{raw.name}: Dates!D7 is not YYYYMM: {cutoff_code!r}")
        observations = [
            Observation(
                indicator_id, area_id, period, "M", value, "actual" if period <= cutoff else "forecast"
            )
            for code, (indicator_id, area_id) in SERIES.items()
            for period, value, _ in series[code]
        ]
        return Parsed(observations, data_cutoff=cutoff)


def read_months(sheet, row: int) -> list[tuple[str, float, bool]]:
    """(YYYY-MM, value, set in italics) for each month of a series row on 2tab."""
    found = []
    year = None
    for col in range(3, sheet.max_column + 1):
        header_year = sheet.cell(3, col).value
        if isinstance(header_year, int | float) and 1990 < header_year < 2100:
            year = int(header_year)
        month = MONTHS.get(str(sheet.cell(4, col).value).strip())
        cell = sheet.cell(row, col)
        if year is None or month is None or not isinstance(cell.value, int | float):
            continue
        found.append((f"{year:04d}-{month:02d}", float(cell.value), bool(cell.font and cell.font.i)))
    return found


def styled_cutoff(name: str, months: list[tuple[str, float, bool]]) -> str:
    """Last historical month of files before July 2017, which have no Dates!D7.

    There historical months are set in bold and forecast months in italics; in the files that
    have both (07.2017-05.2024) this boundary matches D7 in 79 of 80 releases.
    """
    italic = [flag for _, _, flag in months]
    first = italic.index(True) if True in italic else 0
    if first == 0 or not all(italic[first:]):
        raise SourceStructureError(f"{name}: no Dates!D7 and no bold/italic boundary on 2tab")
    return months[first - 1][0]


register(EiaSteo())
