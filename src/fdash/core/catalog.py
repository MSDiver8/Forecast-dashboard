"""Indicator catalog from config/indicators.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from fdash import settings


class Group(BaseModel):
    id: str
    name: str


class Area(BaseModel):
    id: str
    name: str
    kind: str


class Indicator(BaseModel):
    id: str
    name: str
    unit: str
    transform: str
    base: str | None = None
    groups: list[str]
    description: str | None = None
    precision: int = 1
    actual_source: str | None = None


class Series(BaseModel):
    source: str
    code: str
    indicator: str
    area: str
    note: str | None = None


class Catalog(BaseModel):
    groups: list[Group]
    areas: list[Area]
    indicators: list[Indicator]
    series: list[Series]

    def indicator(self, indicator_id: str) -> Indicator | None:
        return next((i for i in self.indicators if i.id == indicator_id), None)

    def series_for(self, source_id: str) -> list[Series]:
        return [s for s in self.series if s.source == source_id]


def load(path: Path | None = None) -> Catalog:
    data = yaml.safe_load((path or settings.CONFIG_PATH).read_text(encoding="utf-8"))
    catalog = Catalog.model_validate(data)
    ids = {i.id for i in catalog.indicators}
    areas = {a.id for a in catalog.areas}
    for s in catalog.series:
        if s.indicator not in ids or s.area not in areas:
            raise ValueError(f"Unknown indicator or area in series: {s}")
    return catalog


@lru_cache(maxsize=1)
def cached() -> Catalog:
    return load()
