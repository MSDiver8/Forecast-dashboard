"""ONS time series: CPI annual rate D7G7 (quarterly values) and GDP growth on a year earlier IHYR."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fdash.ingest.base import (
    Connector,
    Observation,
    Parsed,
    Release,
    SourceStructureError,
    copy_into,
    download_temp,
)
from fdash.ingest.registry import register

BASE = "https://www.ons.gov.uk"
LONDON = ZoneInfo("Europe/London")
QUARTER = re.compile(r"^(\d{4}) Q([1-4])$")


def release_date(payload: dict) -> date:
    """`releaseDate` is midnight London time written in UTC, e.g. 2026-09-15T23:00:00.000Z = 16 Sep."""
    raw = payload["description"]["releaseDate"]
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(LONDON).date()


def read_quarters(payload: dict, cdid: str) -> list[tuple[str, float]]:
    if payload.get("description", {}).get("cdid", "").upper() != cdid:
        raise SourceStructureError(
            f"ONS: expected series {cdid}, got {payload.get('description', {}).get('cdid')!r}"
        )
    points = []
    for row in payload.get("quarters", []):
        match = QUARTER.match(row.get("date", ""))
        if match and row.get("value") not in (None, ""):
            points.append((f"{match.group(1)}-Q{match.group(2)}", float(row["value"])))
    if not points:
        raise SourceStructureError(f"ONS {cdid}: no quarterly values")
    return points


class OnsSeries(Connector):
    role = "actual"
    dedupe = True
    organization = "ONS"
    license = "Open Government Licence v3.0"
    access = "JSON временного ряда на сайте ONS, без ключа"
    cdid: str
    path: str
    datasets: tuple[str, ...]
    indicator_id: str

    def __init__(self) -> None:
        self._latest: tuple[Path, str] | None = None

    def _download_latest(self) -> tuple[Path, str]:
        """The newest of the datasets that carry the series (for GDP: first estimate PN2 or QNA)."""
        if self._latest is None or not self._latest[0].exists():
            found = []
            for dataset in self.datasets:
                url = f"{BASE}/{self.path}/{self.cdid.lower()}/{dataset.lower()}/data"
                path = download_temp(url, f"{self.cdid.lower()}_{dataset.lower()}.json")
                found.append((release_date(json.loads(path.read_text(encoding="utf-8"))), path, url))
            _, path, url = max(found, key=lambda item: item[0])
            self._latest = (path, url)
        return self._latest

    def list_releases(self) -> list[Release]:
        path, url = self._download_latest()
        published = release_date(json.loads(path.read_text(encoding="utf-8")))
        return [
            Release(
                release_id=f"{self.source_id}_{published:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"{self.cdid} {published:%d.%m.%Y}",
                vintage_date=published,
                url=url,
                filename=path.name,
            )
        ]

    def fetch(self, release: Release) -> Path:
        return copy_into(self._download_latest()[0], release)

    def parse(self, raw: Path, release: Release) -> Parsed:
        points = read_quarters(json.loads(raw.read_text(encoding="utf-8")), self.cdid)
        observations = [Observation(self.indicator_id, "GB", p, "Q", v, "actual") for p, v in points]
        return Parsed(observations, data_cutoff=points[-1][0])


class OnsCpi(OnsSeries):
    source_id = "ons_cpi"
    name = "CPI annual rate 00: all items (D7G7)"
    url = f"{BASE}/economy/inflationandpriceindices/timeseries/d7g7/mm23"
    cdid = "D7G7"
    path = "economy/inflationandpriceindices/timeseries"
    datasets = ("MM23",)
    indicator_id = "cpi_yoy_q"


class OnsGdp(OnsSeries):
    source_id = "ons_gdp"
    name = "Gross Domestic Product: q-on-q4 growth rate CVM SA % (IHYR)"
    url = f"{BASE}/economy/grossdomesticproductgdp/timeseries/ihyr/qna"
    cdid = "IHYR"
    path = "economy/grossdomesticproductgdp/timeseries"
    datasets = ("QNA", "PN2")
    indicator_id = "gdp_yoy_q"


register(OnsCpi())
register(OnsGdp())
