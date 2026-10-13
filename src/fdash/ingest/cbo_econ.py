"""CBO economic projections (official open data repository on GitHub): US real GDP growth, quarterly."""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from fdash.ingest.base import (
    Connector,
    Observation,
    Parsed,
    Release,
    SourceStructureError,
    archive_start,
    http_get,
    projection_kind,
)
from fdash.ingest.registry import register

REPO = "https://raw.githubusercontent.com/US-CBO/cbo-data/main/"
CATALOG = REPO + "catalog.json"
DATASET = "economic_projections"
VARIABLE = "real_gdp_pct_change"  # schema.json: "Real GDP, percentage change (annual rate)"
PERIOD = re.compile(r"^(\d{4})q([1-4])$")


def quarterly_files(catalog: dict) -> list[tuple[str, str]]:
    """(vintage YYYY-MM, path in the repository) of the quarterly projection files."""
    dataset = next((d for d in catalog.get("datasets", []) if d.get("identifier") == DATASET), None)
    if dataset is None:
        raise SourceStructureError(f"catalog.json: dataset {DATASET} not found")
    files = [
        (d["vintage"], d["downloadURL"])
        for d in dataset.get("distribution", [])
        if d.get("file_type") == "quarterly"
    ]
    if not files:
        raise SourceStructureError(f"catalog.json: no quarterly files in {DATASET}")
    return sorted(files)


def read_csv(path: Path) -> list[tuple[str, float, bool]]:
    """(YYYY-Qn, value, projected) of real GDP growth."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"date", "variable", "value", "estimate_type"} <= set(reader.fieldnames or []):
            raise SourceStructureError(f"{path.name}: columns date, variable, value, estimate_type expected")
        points = []
        for row in reader:
            if row["variable"] != VARIABLE:
                continue
            match = PERIOD.match(row["date"])
            if not match or row["estimate_type"] not in ("actual", "projected"):
                raise SourceStructureError(f"{path.name}: unexpected row {row}")
            points.append(
                (
                    f"{match.group(1)}-Q{match.group(2)}",
                    float(row["value"]),
                    row["estimate_type"] == "projected",
                )
            )
    if not points:
        raise SourceStructureError(f"{path.name}: {VARIABLE} not found")
    return points


class CboEcon(Connector):
    source_id = "cbo_econ"
    name = "Economic Projections (10-year)"
    organization = "CBO"
    url = "https://github.com/US-CBO/cbo-data"
    license = "Public domain (U.S. Government)"
    access = "CSV в открытом репозитории CBO на GitHub (cbo.gov отвечает 403 автоматическим клиентам)"

    def list_releases(self) -> list[Release]:
        response = http_get(CATALOG)
        response.raise_for_status()
        start = archive_start(2)
        releases = []
        for vintage, path in quarterly_files(response.json()):
            year, month = int(vintage[:4]), int(vintage[5:7])
            published = date(year, month, 1)  # the repository gives only the month of the report
            if published < date(start.year, start.month, 1):
                continue
            releases.append(
                Release(
                    release_id=f"{self.source_id}_{year}_{month:02d}",
                    source_id=self.source_id,
                    title=f"CBO {month:02d}.{year} (дата ≈)",
                    vintage_date=published,
                    url=REPO + path,
                    filename=Path(path).name,
                    extra={"vintage": vintage, "approximate_date": True},
                )
            )
        return releases

    def parse(self, raw: Path, release: Release) -> Parsed:
        points = read_csv(raw)
        observations = [
            Observation("gdp_qoq_saar", "US", p, "Q", v, projection_kind(p, release.vintage_date, projected))
            for p, v, projected in points
        ]
        actual = [p for p, _, projected in points if not projected]
        return Parsed(observations, data_cutoff=max(actual) if actual else None)


register(CboEcon())
