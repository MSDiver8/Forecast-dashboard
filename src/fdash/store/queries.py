"""Read queries for the API: catalog coverage, comparison views, data status."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import duckdb

from fdash.core import periods
from fdash.core.catalog import Catalog

DERIVABLE = {"A": ("M", "Q"), "Q": ("M",)}


@dataclass
class SeriesPoint:
    period: str
    value: float
    kind: str
    lower: float | None = None
    upper: float | None = None


@dataclass
class ReleaseSeries:
    release_id: str
    source_id: str
    title: str
    vintage_date: date
    derived_from: str | None = None
    points: list[SeriesPoint] = field(default_factory=list)


def coverage(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Native coverage per (indicator, area, frequency): sources and release counts."""
    rows = con.execute(
        """
        SELECT o.indicator_id, o.area_id, o.frequency, r.source_id, s.role,
               count(DISTINCT r.release_id) AS releases, max(r.vintage_date) AS last_vintage
        FROM observations o
        JOIN releases r USING (release_id)
        JOIN sources s ON s.source_id = r.source_id
        GROUP BY ALL
        """
    ).fetchall()
    return [
        dict(indicator_id=i, area_id=a, frequency=f, source_id=s, role=role, releases=n, last_vintage=v)
        for i, a, f, s, role, n, v in rows
    ]


def frequencies_for(cov: list[dict], indicator_id: str, area_id: str) -> dict[str, set[str]]:
    """frequency -> forecast sources usable at that frequency (natively or by averaging)."""
    native: dict[str, set[str]] = defaultdict(set)
    for row in cov:
        if row["indicator_id"] == indicator_id and row["area_id"] == area_id and row["role"] == "forecast":
            native[row["frequency"]].add(row["source_id"])
    result = {f: set(s) for f, s in native.items()}
    for target, lower in DERIVABLE.items():
        for freq in lower:
            if freq in native:
                result.setdefault(target, set()).update(native[freq])
    return result


def _release_rows(con, indicator_id: str, area_id: str, source_id: str, frequency: str):
    return con.execute(
        """
        SELECT r.release_id, r.title, r.vintage_date
        FROM releases r
        WHERE r.source_id = ? AND EXISTS (
            SELECT 1 FROM observations o
            WHERE o.release_id = r.release_id AND o.indicator_id = ? AND o.area_id = ? AND o.frequency = ?)
        ORDER BY r.vintage_date
        """,
        [source_id, indicator_id, area_id, frequency],
    ).fetchall()


def releases_of(
    con, indicator_id: str, area_id: str, source_id: str, frequency: str
) -> tuple[list, str | None]:
    """Releases with data at the requested frequency, natively or derivable from a higher one."""
    rows = _release_rows(con, indicator_id, area_id, source_id, frequency)
    if rows:
        return rows, None
    for lower in DERIVABLE.get(frequency, ()):
        rows = _release_rows(con, indicator_id, area_id, source_id, lower)
        if rows:
            return rows, lower
    return [], None


def _points(con, release_id: str, indicator_id: str, area_id: str, frequency: str) -> list[SeriesPoint]:
    rows = con.execute(
        """
        SELECT target_period, value, kind, lower, upper FROM observations
        WHERE release_id = ? AND indicator_id = ? AND area_id = ? AND frequency = ?
        ORDER BY target_period
        """,
        [release_id, indicator_id, area_id, frequency],
    ).fetchall()
    return [SeriesPoint(p, v, k, lo, up) for p, v, k, lo, up in rows]


def _aggregate(points: list[SeriesPoint], target: str) -> list[SeriesPoint]:
    means = periods.aggregate_mean([(p.period, p.value) for p in points], target)
    kinds: dict[str, set[str]] = defaultdict(set)
    for p in points:
        parent = periods.parent(p.period, target)
        if parent:
            kinds[parent].add(p.kind)
    return [
        SeriesPoint(period, value, "forecast" if "forecast" in kinds[period] else min(kinds[period]))
        for period, value in sorted(means.items())
    ]


def release_series(
    con,
    release_row,
    indicator_id: str,
    area_id: str,
    source_id: str,
    frequency: str,
    derived_from: str | None,
) -> ReleaseSeries:
    release_id, title, vintage = release_row
    if derived_from:
        points = _aggregate(_points(con, release_id, indicator_id, area_id, derived_from), frequency)
    else:
        points = _points(con, release_id, indicator_id, area_id, frequency)
    return ReleaseSeries(release_id, source_id, title, vintage, derived_from, points)


def select_releases(rows: list, mode: str, asof: date | None, manual: set[str], last_n: int = 1) -> list:
    if mode == "manual":
        return [r for r in rows if r[0] in manual]
    if mode == "asof" and asof:
        rows = [r for r in rows if r[2] <= asof]
    return rows[-last_n:] if rows else []


def actual_series(
    con, catalog: Catalog, indicator_id: str, area_id: str, frequency: str, asof: date | None
) -> ReleaseSeries | None:
    """Reference actuals: the latest release of the actual source known at `asof`."""
    indicator = catalog.indicator(indicator_id)
    source_id = indicator.actual_source if indicator else None
    if not source_id:
        return None
    rows, derived = releases_of(con, indicator_id, area_id, source_id, frequency)
    chosen = select_releases(rows, "asof" if asof else "latest", asof, set())
    if not chosen:
        return None
    series = release_series(con, chosen[-1], indicator_id, area_id, source_id, frequency, derived)
    series.points = [p for p in series.points if p.kind == "actual"]
    return series


def status(con) -> dict:
    sources = con.execute(
        """
        SELECT s.source_id, s.organization, s.name, s.role, s.url, s.license,
               count(r.release_id), min(r.vintage_date), max(r.vintage_date)
        FROM sources s LEFT JOIN releases r USING (source_id)
        GROUP BY ALL ORDER BY s.role DESC, s.organization
        """
    ).fetchall()
    log = con.execute(
        """
        SELECT source_id, started_at, finished_at, status, releases, rows_added, error
        FROM ingestion_log ORDER BY started_at DESC LIMIT 100
        """
    ).fetchall()
    return {
        "sources": [
            dict(
                source_id=s,
                organization=o,
                name=n,
                role=role,
                url=u,
                license=lic,
                releases=c,
                first_vintage=f,
                last_vintage=last,
            )
            for s, o, n, role, u, lic, c, f, last in sources
        ],
        "log": [
            dict(source_id=s, started_at=st, finished_at=fi, status=stt, releases=r, rows_added=ra, error=e)
            for s, st, fi, stt, r, ra, e in log
        ],
    }
