"""IMF World Economic Outlook via SDMX: current release and *_VINTAGE dataflows."""

from __future__ import annotations

import csv
import io
import re
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

API = "https://api.imf.org/external/sdmx/2.1"
CSV = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}
VINTAGE = re.compile(r'<str:Dataflow [^>]*id="(WEO_(\d{4})_([A-Z]{3})_VINTAGE)"')
COUNTRIES = {
    "RUS": "RU",
    "USA": "US",
    "DEU": "DE",
    "FRA": "FR",
    "ITA": "IT",
    "ESP": "ES",
    "GBR": "GB",
    "JPN": "JP",
    "CHN": "CN",
    "G001": "WORLD",
    "G163": "EA",
}
INDICATORS = {
    "NGDP_RPCH": "gdp_growth",
    "PCPIPCH": "cpi_avg",
    "PCPIEPCH": "cpi_dec",
    "LUR": "unemployment_avg",
}
MONTH_NAMES = {"APR": "апрель", "OCT": "октябрь", "JAN": "январь", "JUL": "июль"}


def query(dataflow: str, start: int = 2015) -> str:
    key = f"{'+'.join(COUNTRIES)}.{'+'.join(INDICATORS)}.A"
    return f"{API}/data/IMF.RES,{dataflow}/{key}?startPeriod={start}"


def publication_date(dataflow: str) -> date:
    response = http_get(
        f"{API}/data/IMF.RES,{dataflow}/G001.NGDP_RPCH.A?startPeriod=2024&endPeriod=2024", headers=CSV
    )
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows or not rows[0].get("PUBLICATION_DATE"):
        raise SourceStructureError(f"{dataflow}: PUBLICATION_DATE not found")
    return date.fromisoformat(rows[0]["PUBLICATION_DATE"][:10])


class ImfWeo(Connector):
    source_id = "imf_weo"
    name = "World Economic Outlook"
    organization = "МВФ"
    url = "https://data.imf.org/en/datasets/IMF.RES:WEO"
    license = "IMF Copyright and Usage, с указанием источника"
    access = "SDMX REST API без ключа"

    def list_releases(self) -> list[Release]:
        flows = http_get(f"{API}/dataflow")
        flows.raise_for_status()
        dataflows = ["WEO"] + sorted({m.group(1) for m in VINTAGE.finditer(flows.text)})
        releases = {}
        for dataflow in dataflows:
            published = publication_date(dataflow)
            release_id = f"imf_weo_{published:%Y_%m}"
            label = MONTH_NAMES.get(published.strftime("%b").upper(), published.strftime("%m"))
            releases.setdefault(
                release_id,
                Release(
                    release_id=release_id,
                    source_id=self.source_id,
                    title=f"WEO {label} {published.year}",
                    vintage_date=published,
                    url=query(dataflow),
                    filename=f"{dataflow}.csv",
                    extra={"dataflow": dataflow},
                ),
            )
        return sorted(releases.values(), key=lambda r: r.vintage_date)

    def fetch(self, release: Release) -> Path:
        return download(release.url, release.raw_path, headers=CSV)

    def parse(self, raw: Path, release: Release) -> Parsed:
        rows = list(csv.DictReader(io.StringIO(raw.read_text(encoding="utf-8"))))
        if not rows or not {"COUNTRY", "INDICATOR", "TIME_PERIOD", "OBS_VALUE"} <= rows[0].keys():
            raise SourceStructureError(f"{raw.name}: unexpected CSV")
        default_actual = release.vintage_date.year - 1
        observations = []
        for r in rows:
            if r["COUNTRY"] not in COUNTRIES or r["INDICATOR"] not in INDICATORS or not r["OBS_VALUE"]:
                continue
            latest = r.get("LATEST_ACTUAL_ANNUAL_DATA") or ""
            latest_year = int(latest) if latest.isdigit() else default_actual
            year = int(r["TIME_PERIOD"])
            observations.append(
                Observation(
                    INDICATORS[r["INDICATOR"]],
                    COUNTRIES[r["COUNTRY"]],
                    r["TIME_PERIOD"],
                    "A",
                    float(r["OBS_VALUE"]),
                    "estimate" if year <= latest_year else "forecast",
                )
            )
        return Parsed(observations, data_cutoff=str(default_actual))


register(ImfWeo())
