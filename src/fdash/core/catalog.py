"""Indicator catalog from config/indicators.yaml."""

from __future__ import annotations

from datetime import date
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
    actual_sources: dict[str, str] = {}
    # False for growth rates: an annual value is not the mean of quarterly rates, so coarser
    # frequencies are never derived from finer ones.
    averageable: bool = True

    def actual_source(self, area_id: str) -> str | None:
        return self.actual_sources.get(area_id) or self.actual_sources.get("*")


class Series(BaseModel):
    source: str
    code: str
    indicator: str
    area: str
    note: str | None = None
    caveat: str | None = None  # shown under the chart for this indicator only, instead of the source caveat


class Context(BaseModel):
    """A finer actual series drawn under the target-period actuals on the accuracy tab."""

    indicator: str
    frequency: str
    label: str


class Featured(BaseModel):
    id: str
    indicator: str
    area: str
    frequency: str = "A"
    category: str
    title: str
    short: str
    subtitle: str | None = None
    description: str
    added: date | None = None  # when the indicator appeared in the dashboard ("Новое" on the start page)
    context: Context | None = None


class SourceInfo(BaseModel):
    short: str
    color: str
    description: str
    caveat: str | None = None


class News(BaseModel):
    """Start page announcement: a featured indicator, a short text and the releases to draw."""

    featured: str
    published: date
    text: str
    sources: list[str]
    start: str  # first period on the chart
    end: str | None = None


class Catalog(BaseModel):
    featured: list[Featured] = []
    news: News | None = None
    source_info: dict[str, SourceInfo] = {}
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
    for f in catalog.featured:
        if f.indicator not in ids or f.area not in areas:
            raise ValueError(f"Unknown indicator or area in featured: {f.id}")
        if f.context and f.context.indicator not in ids:
            raise ValueError(f"Unknown context indicator in featured: {f.id}")
    if catalog.news and catalog.news.featured not in {f.id for f in catalog.featured}:
        raise ValueError(f"Unknown featured indicator in news: {catalog.news.featured}")
    return catalog


@lru_cache(maxsize=1)
def cached() -> Catalog:
    return load()
