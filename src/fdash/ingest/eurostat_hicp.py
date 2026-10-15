"""Eurostat HICP, euro area, reference actuals: annual average rate and the monthly annual rate.

Since February 2026 Eurostat publishes HICP under ECOICOP ver. 2 (`prc_hicp_ainr`, `prc_hicp_minr`);
the older sets (`prc_hicp_aind`, `prc_hicp_manr`) stop at 2025. Saved releases of the older annual
set are still read.
"""

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

DATA = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ANNUAL = DATA + "prc_hicp_ainr?geo=EA&coicop18=TOTAL&unit=RCH_A_AVG&format=JSON&lang=en"
MONTHLY = DATA + "prc_hicp_minr?geo=EA&coicop18=TOTAL&unit=RCH_A&format=JSON&lang=en"
# File names inside a release folder: the current annual and monthly sets, then the older annual one.
ANNUAL_FILE, MONTHLY_FILE, OLD_ANNUAL_FILE = (
    "prc_hicp_ainr_EA.json",
    "prc_hicp_minr_EA.json",
    "prc_hicp_aind_EA.json",
)


def read_series(data: dict, unit: str = "RCH_A_AVG") -> dict[str, float]:
    """Values by period of a JSON-stat answer filtered to one series (every other dimension of size 1)."""
    try:
        if data["dimension"]["unit"]["category"]["index"].keys() != {unit}:
            raise SourceStructureError(f"Eurostat: expected unit {unit}")
        if any(size != 1 for dim, size in zip(data["id"], data["size"], strict=True) if dim != "time"):
            raise SourceStructureError("Eurostat: the answer holds more than one series")
        time_index = data["dimension"]["time"]["category"]["index"]
    except KeyError as exc:
        raise SourceStructureError(f"Eurostat: missing {exc}") from exc
    by_position = {position: period for period, position in time_index.items()}
    return {by_position[int(k)]: float(v) for k, v in data["value"].items()}


class EurostatHicp(Connector):
    source_id = "eurostat_hicp"
    name = "HICP, annual average and monthly annual rate of change"
    organization = "Евростат"
    url = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table"
    license = "Eurostat, reuse with attribution"
    access = "JSON-stat API без ключа"
    role = "actual"
    dedupe = True

    def list_releases(self) -> list[Release]:
        updated = []
        for url in (ANNUAL, MONTHLY):
            response = http_get(url)
            response.raise_for_status()
            updated.append(date.fromisoformat(response.json()["updated"][:10]))
        vintage = max(updated)
        return [
            Release(
                release_id=f"eurostat_hicp_{vintage:%Y_%m_%d}",
                source_id=self.source_id,
                title=f"Евростат {vintage:%d.%m.%Y}",
                vintage_date=vintage,
                url=ANNUAL,
                filename=ANNUAL_FILE,
                extra={"monthly_url": MONTHLY},
            )
        ]

    def fetch(self, release: Release) -> Path:
        download(release.extra.get("monthly_url", MONTHLY), release.raw_path.parent / MONTHLY_FILE)
        return download(release.url, release.raw_path)

    def parse(self, raw: Path, release: Release) -> Parsed:
        folder = raw.parent
        annual_file = folder / ANNUAL_FILE if (folder / ANNUAL_FILE).exists() else folder / OLD_ANNUAL_FILE
        annual = read_series(json.loads(annual_file.read_text(encoding="utf-8")))
        observations = [
            Observation("cpi_avg", "EA", year, "A", value, "actual") for year, value in annual.items()
        ]
        monthly = {}
        if (folder / MONTHLY_FILE).exists():
            monthly = read_series(json.loads((folder / MONTHLY_FILE).read_text(encoding="utf-8")), "RCH_A")
            observations += [
                Observation("cpi_yoy_m", "EA", month, "M", value, "actual")
                for month, value in monthly.items()
            ]
        return Parsed(observations, data_cutoff=max(monthly) if monthly else max(annual))


register(EurostatHicp())
