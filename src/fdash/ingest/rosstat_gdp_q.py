"""Rosstat quarterly GDP: volume index to the same quarter of the previous year, as actuals."""

from __future__ import annotations

import re
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

from openpyxl import load_workbook

from fdash.ingest.base import (
    Connector,
    Observation,
    Parsed,
    Release,
    SourceStructureError,
    client,
    download,
    http_get,
    russian_trust,
)
from fdash.ingest.registry import register

SITE = "https://rosstat.gov.ru"
PAGE = f"{SITE}/statistics/accounts"
FILE_LINK = re.compile(r'href="(/storage/mediabank/VVP_kvartal_s[^"]*\.xlsx)"')
TITLE = "Индексы физического объема валового внутреннего продукта"
BASE = "к соответствующему кварталу предыдущего года"
QUARTERS = {"I квартал": 1, "II квартал": 2, "III квартал": 3, "IV квартал": 4}
YEAR = re.compile(r"^(\d{4})")


def file_url(html: str) -> str:
    match = FILE_LINK.search(html)
    if not match:
        raise SourceStructureError("Rosstat: no link to the quarterly GDP file on the page")
    return SITE + match.group(1)


def read_growth(path: Path) -> dict[str, float]:
    """Growth, %, by quarter: the index to the same quarter of the previous year minus 100.

    Two sheets carry the index (1996–2011 and from 2012); a later sheet wins where they overlap.
    """
    workbook = load_workbook(path, read_only=True, data_only=True)
    result: dict[str, float] = {}
    sheets = 0
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        title = next((i for i, row in enumerate(rows[:5]) if row and TITLE in str(row[0] or "")), None)
        if title is None or BASE not in str(rows[title][0]):
            continue
        years, quarters, values = rows[title + 1], rows[title + 2], rows[title + 3]
        year = None
        for cell_year, cell_quarter, value in zip(years, quarters, values, strict=False):
            if cell_year is not None and (match := YEAR.match(str(cell_year))):
                year = int(match.group(1))
            quarter = QUARTERS.get(str(cell_quarter or "").strip())
            if year and quarter and isinstance(value, int | float):
                result[f"{year:04d}-Q{quarter}"] = float(value) - 100
        sheets += 1
    if not sheets or not result:
        raise SourceStructureError(f"{path.name}: no sheet «{TITLE} … {BASE}»")
    return dict(sorted(result.items()))


class RosstatGdpQ(Connector):
    source_id = "rosstat_gdp_q"
    name = "ВВП кварталы (с 1995 г.)"
    organization = "Росстат"
    url = PAGE
    license = "Официальная статистика Росстата, со ссылкой на источник"
    access = "XLSX со страницы национальных счетов; TLS с сертификатом Минцифры"
    role = "actual"
    dedupe = True

    def list_releases(self) -> list[Release]:
        trust = russian_trust()
        page = http_get(PAGE, verify=trust)
        page.raise_for_status()
        url = file_url(page.text)
        with client(trust) as http:
            head = http.head(url)
            head.raise_for_status()
        modified = head.headers.get("last-modified")
        vintage = parsedate_to_datetime(modified).date() if modified else date.today()
        return [
            Release(
                release_id=f"rosstat_gdp_q_{vintage:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"Росстат, ВВП кварталы, {vintage:%d.%m.%Y}",
                vintage_date=vintage,
                url=url,
                filename="VVP_kvartal.xlsx",
            )
        ]

    def fetch(self, release: Release) -> Path:
        return download(release.url, release.raw_path, verify=russian_trust())

    def parse(self, raw: Path, release: Release) -> Parsed:
        growth = read_growth(raw)
        observations = [
            Observation("gdp_yoy_q", "RU", quarter, "Q", value, "actual") for quarter, value in growth.items()
        ]
        return Parsed(observations, data_cutoff=max(growth))


register(RosstatGdpQ())
