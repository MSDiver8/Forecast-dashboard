"""World Bank WDI: real GDP growth of Russia (national statistics) as reference actuals."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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

API = "https://api.worldbank.org/v2/country/RUS/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=100&date=1990:2030"


def read_series(data: list) -> dict[str, float]:
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        raise SourceStructureError("WDI: unexpected response")
    if data[1][0]["indicator"]["id"] != "NY.GDP.MKTP.KD.ZG":
        raise SourceStructureError("WDI: unexpected indicator")
    return {r["date"]: float(r["value"]) for r in data[1] if r["value"] is not None}


class WbWdi(Connector):
    source_id = "wb_wdi"
    name = "World Development Indicators: GDP growth"
    organization = "Всемирный банк (данные Росстата)"
    url = "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=RU"
    license = "CC BY 4.0"
    access = "REST API без ключа"
    role = "actual"
    dedupe = True

    def list_releases(self) -> list[Release]:
        response = http_get(API)
        response.raise_for_status()
        updated = date.fromisoformat(response.json()[0]["lastupdated"])
        return [
            Release(
                release_id=f"wb_wdi_{updated:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"WDI {updated:%d.%m.%Y}",
                vintage_date=updated,
                url=API,
                filename="RUS_NY.GDP.MKTP.KD.ZG.json",
            )
        ]

    def fetch(self, release: Release) -> Path:
        return download(release.url, release.raw_path)

    def parse(self, raw: Path, release: Release) -> Parsed:
        series = read_series(json.loads(raw.read_text(encoding="utf-8")))
        observations = [
            Observation("gdp_growth", "RU", year, "A", value, "actual") for year, value in series.items()
        ]
        return Parsed(observations, data_cutoff=max(series))


register(WbWdi())
