"""EIA Europe Brent Spot Price FOB (RBRTE): reference actuals, monthly and annual."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import xlrd

from fdash.ingest.base import (
    Connector,
    Observation,
    Parsed,
    Release,
    SourceStructureError,
    download,
    http_get,
)
from fdash.ingest.registry import register

PAGE = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=RBRTE&f=M"
FILES = {
    "M": "https://www.eia.gov/dnav/pet/hist_xls/RBRTEm.xls",
    "A": "https://www.eia.gov/dnav/pet/hist_xls/RBRTEa.xls",
}
RELEASE_DATE = re.compile(r"(?<!Next )Release Date:\s*(\d{1,2}/\d{1,2}/\d{4})")


def release_date(html: str) -> date:
    match = RELEASE_DATE.search(html)
    if not match:
        raise SourceStructureError("RBRTE page: 'Release Date' not found")
    return datetime.strptime(match.group(1), "%m/%d/%Y").date()


def read_series(path: Path, frequency: str) -> list[tuple[str, float]]:
    sheet = xlrd.open_workbook(str(path)).sheet_by_name("Data 1")
    if sheet.cell_value(1, 1) != "RBRTE":
        raise SourceStructureError(f"{path.name}: Sourcekey RBRTE not found in B2")
    points = []
    for r in range(3, sheet.nrows):
        raw_date, value = sheet.cell_value(r, 0), sheet.cell_value(r, 1)
        if not isinstance(raw_date, float) or not isinstance(value, float):
            continue
        d = xlrd.xldate_as_datetime(raw_date, 0)
        points.append((f"{d.year:04d}" if frequency == "A" else f"{d.year:04d}-{d.month:02d}", value))
    return points


class EiaBrentSpot(Connector):
    source_id = "eia_brent_spot"
    name = "Europe Brent Spot Price FOB (RBRTE)"
    organization = "EIA"
    url = PAGE
    license = "Public domain (U.S. Government)"
    access = "XLS по стабильной ссылке"
    role = "actual"

    def list_releases(self) -> list[Release]:
        response = http_get(PAGE)
        response.raise_for_status()
        published = release_date(response.text)
        return [
            Release(
                release_id=f"eia_brent_spot_{published:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"RBRTE {published:%d.%m.%Y}",
                vintage_date=published,
                url=FILES["M"],
                filename="RBRTEm.xls",
            )
        ]

    def fetch(self, release: Release) -> Path:
        download(FILES["A"], release.raw_path.parent / "RBRTEa.xls")
        return download(FILES["M"], release.raw_path)

    def parse(self, raw: Path, release: Release) -> Parsed:
        observations = [
            Observation("brent_price", "WORLD", period, frequency, value, "actual")
            for frequency, path in (("M", raw), ("A", raw.parent / "RBRTEa.xls"))
            for period, value in read_series(path, frequency)
        ]
        monthly = [o.target_period for o in observations if o.frequency == "M"]
        return Parsed(observations, data_cutoff=max(monthly) if monthly else None)


register(EiaBrentSpot())
