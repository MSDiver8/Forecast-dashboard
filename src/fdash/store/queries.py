"""Read queries for the API: catalog coverage, comparison views, data status."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import duckdb

from fdash.core import periods
from fdash.core.catalog import Catalog

DERIVABLE = {"A": ("M", "Q"), "Q": ("M",)}
STALE_DAYS = 365


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
    source_id = indicator.actual_source(area_id) if indicator else None
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


def _source_meta(con, catalog: Catalog, source_id: str) -> dict:
    org, name, url = con.execute(
        "SELECT organization, name, url FROM sources WHERE source_id = ?", [source_id]
    ).fetchone()
    info = catalog.source_info.get(source_id)
    return {
        "source_id": source_id,
        "organization": org,
        "name": name,
        "url": url,
        "short": info.short if info else org,
        "color": info.color if info else "#555555",
        "description": info.description if info else None,
        "caveat": info.caveat if info else None,
    }


def _point_dict(p: SeriesPoint) -> dict:
    return {"period": p.period, "value": p.value, "kind": p.kind, "lower": p.lower, "upper": p.upper}


def pair_series(con, catalog: Catalog, indicator_id: str, area_id: str, frequency: str) -> dict:
    """Every release of every forecast source for one indicator, area and frequency, plus actuals."""
    cov = coverage(con)
    usable = frequencies_for(cov, indicator_id, area_id)
    sources = []
    for source_id in sorted(usable.get(frequency, set())):
        rows, derived = releases_of(con, indicator_id, area_id, source_id, frequency)
        releases = []
        for row in rows:
            series = release_series(con, row, indicator_id, area_id, source_id, frequency, derived)
            if series.points:
                releases.append(
                    {
                        "release_id": series.release_id,
                        "title": series.title,
                        "vintage_date": series.vintage_date,
                        "points": [_point_dict(p) for p in series.points],
                    }
                )
        if not releases:
            continue  # e.g. one quarter a year cannot be averaged into an annual value
        note = next(
            (
                s.note
                for s in catalog.series
                if (s.source, s.indicator, s.area) == (source_id, indicator_id, area_id)
            ),
            None,
        )
        sources.append(
            {
                **_source_meta(con, catalog, source_id),
                "note": note,
                "derived_from": derived,
                "releases": releases,
            }
        )
    actual = None
    indicator = catalog.indicator(indicator_id)
    actual_source = indicator.actual_source(area_id) if indicator else None
    if actual_source:
        rows, derived = releases_of(con, indicator_id, area_id, actual_source, frequency)
        actual_releases = []
        for row in rows:
            series = release_series(con, row, indicator_id, area_id, actual_source, frequency, derived)
            actual_releases.append(
                {
                    "release_id": series.release_id,
                    "title": series.title,
                    "vintage_date": series.vintage_date,
                    "points": [
                        {"period": p.period, "value": p.value} for p in series.points if p.kind == "actual"
                    ],
                }
            )
        if actual_releases:
            actual = {
                **_source_meta(con, catalog, actual_source),
                "derived_from": derived,
                "releases": actual_releases,
            }
    freqs = [f for f in ("A", "Q", "M") if usable.get(f)]
    return {"frequencies": freqs, "actual": actual, "sources": sources}


def featured_cards(con, catalog: Catalog) -> list[dict]:
    """Start page cards: latest fact, latest forecasts for the next periods, coverage."""
    cards = []
    for f in catalog.featured:
        indicator = catalog.indicator(f.indicator)
        data = pair_series(con, catalog, f.indicator, f.area, f.frequency)
        fact_points = data["actual"]["releases"][-1]["points"] if data["actual"] else []
        last_fact = fact_points[-1] if fact_points else None
        targets = []
        if last_fact:
            targets = [periods.shift(last_fact["period"], k) for k in (1, 2)]
        newest = max((src["releases"][-1]["vintage_date"] for src in data["sources"]), default=None)
        latest = []
        for source in data["sources"]:
            release = source["releases"][-1]
            if newest and (newest - release["vintage_date"]).days > STALE_DAYS:
                continue  # the source stopped publishing this forecast; shown only on request
            values = {p["period"]: p for p in release["points"]}
            latest.append(
                {
                    "source_id": source["source_id"],
                    "short": source["short"],
                    "color": source["color"],
                    "release_title": release["title"],
                    "vintage_date": release["vintage_date"],
                    "values": {t: values.get(t) for t in targets},
                }
            )
        all_vintages = [r["vintage_date"] for s in data["sources"] for r in s["releases"]]
        cards.append(
            {
                **f.model_dump(),
                "unit": indicator.unit,
                "precision": indicator.precision,
                "fact_source": data["actual"]["short"] if data["actual"] else None,
                "last_fact": last_fact,
                "sparkline": fact_points[-12:],
                "targets": targets,
                "latest": latest,
                "source_count": len(data["sources"]),
                "release_count": len(all_vintages),
                "last_update": max(all_vintages) if all_vintages else None,
                "frequencies": data["frequencies"],
            }
        )
    return cards


def evaluation(con, catalog: Catalog, indicator_id: str, area_id: str, frequency: str) -> dict:
    """Errors of published forecasts against the latest actuals, by release and by horizon."""
    data = pair_series(con, catalog, indicator_id, area_id, frequency)
    if not data["actual"]:
        return {"actual": None, "sources": []}
    fact = {p["period"]: p["value"] for p in data["actual"]["releases"][-1]["points"]}
    out = []
    for source in data["sources"]:
        releases, by_horizon = [], defaultdict(list)
        for release in source["releases"]:
            vintage_period = period_of(release["vintage_date"], frequency)
            errors = []
            for p in release["points"]:
                if p["kind"] != "forecast" or p["period"] not in fact:
                    continue
                error = p["value"] - fact[p["period"]]
                horizon = _steps_between(vintage_period, p["period"])
                errors.append(
                    {
                        "period": p["period"],
                        "forecast": p["value"],
                        "actual": fact[p["period"]],
                        "error": error,
                        "horizon": horizon,
                    }
                )
                by_horizon[horizon].append(error)
            if errors:
                abs_errors = [abs(e["error"]) for e in errors]
                releases.append(
                    {
                        "release_id": release["release_id"],
                        "title": release["title"],
                        "vintage_date": release["vintage_date"],
                        "points": errors,
                        "mae": sum(abs_errors) / len(abs_errors),
                        "rmse": (sum(e["error"] ** 2 for e in errors) / len(errors)) ** 0.5,
                        "bias": sum(e["error"] for e in errors) / len(errors),
                    }
                )
        horizons = [
            {"horizon": h, "n": len(v), "mae": sum(abs(e) for e in v) / len(v), "bias": sum(v) / len(v)}
            for h, v in sorted(by_horizon.items())
        ]
        out.append(
            {
                **{k: source[k] for k in ("source_id", "short", "color", "organization", "name")},
                "releases": releases,
                "horizons": horizons,
            }
        )
    return {"actual": {k: data["actual"][k] for k in ("source_id", "short")}, "sources": out}


def period_of(day: date, frequency: str) -> str:
    if frequency == "M":
        return f"{day.year:04d}-{day.month:02d}"
    if frequency == "Q":
        return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}"
    return f"{day.year:04d}"


def _steps_between(start: str, end: str) -> int:
    for k in range(-5, 400):
        if periods.shift(start, k) == end:
            return k
    return 0


def sources_registry(con, catalog: Catalog) -> list[dict]:
    rows = con.execute(
        """
        SELECT s.source_id, s.role, s.license, s.access, count(r.release_id),
               min(r.vintage_date), max(r.vintage_date)
        FROM sources s LEFT JOIN releases r USING (source_id)
        GROUP BY ALL
        """
    ).fetchall()
    titles = {}
    for f in catalog.featured:
        for s in catalog.series:
            if (s.indicator, s.area) == (f.indicator, f.area):
                titles.setdefault(s.source, []).append(f.title)
    result = []
    for source_id, role, lic, access, count, first, last in rows:
        if source_id not in titles:
            continue  # only sources behind the curated indicators
        result.append(
            {
                **_source_meta(con, catalog, source_id),
                "role": role,
                "license": lic,
                "access": access,
                "releases": count,
                "first_vintage": first,
                "last_vintage": last,
                "indicators": sorted(set(titles[source_id])),
            }
        )
    return sorted(result, key=lambda r: (r["role"] != "forecast", r["short"]))
