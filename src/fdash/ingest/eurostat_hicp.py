"""Eurostat HICP, annual average rate of change, euro area: reference actuals."""

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

API = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_aind"
    "?geo=EA&coicop=CP00&unit=RCH_A_AVG&format=JSON&lang=en"
)


def read_series(data: dict) -> dict[str, float]:
    try:
        if data["dimension"]["unit"]["category"]["index"].keys() != {"RCH_A_AVG"}:
            raise SourceStructureError("Eurostat: unexpected unit")
        time_index = data["dimension"]["time"]["category"]["index"]
    except KeyError as exc:
        raise SourceStructureError(f"Eurostat: missing {exc}") from exc
    by_position = {position: period for period, position in time_index.items()}
    return {by_position[int(k)]: float(v) for k, v in data["value"].items()}


class EurostatHicp(Connector):
    source_id = "eurostat_hicp"
    name = "HICP, annual average rate of change"
    organization = "Евростат"
    url = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_aind/default/table"
    license = "Eurostat, reuse with attribution"
    access = "JSON-stat API без ключа"
    role = "actual"
    dedupe = True

    def list_releases(self) -> list[Release]:
        response = http_get(API)
        response.raise_for_status()
        updated = date.fromisoformat(response.json()["updated"][:10])
        return [
            Release(
                release_id=f"eurostat_hicp_{updated:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"Евростат {updated:%d.%m.%Y}",
                vintage_date=updated,
                url=API,
                filename="prc_hicp_aind_EA.json",
            )
        ]

    def fetch(self, release: Release) -> Path:
        return download(release.url, release.raw_path)

    def parse(self, raw: Path, release: Release) -> Parsed:
        series = read_series(json.loads(raw.read_text(encoding="utf-8")))
        observations = [
            Observation("cpi_avg", "EA", year, "A", value, "actual") for year, value in series.items()
        ]
        return Parsed(observations, data_cutoff=max(series))


register(EurostatHicp())
