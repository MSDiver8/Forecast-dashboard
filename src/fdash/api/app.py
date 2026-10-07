"""HTTP API for the dashboard and static hosting of the built frontend."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from pydantic import BaseModel, Field

from fdash import settings
from fdash.core import catalog as catalog_mod
from fdash.core import periods
from fdash.core.models import benchmarks
from fdash.store import db, queries

app = FastAPI(title="Forecast dashboard API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_shared = None


def _con():
    """A cursor on the process-wide connection (DuckDB allows one writer process)."""
    global _shared
    if not settings.DB_PATH.exists():
        raise HTTPException(503, "База не создана: запустите `fdash ingest --all`")
    if _shared is None:
        _shared = db.connect()
    return _shared.cursor()


def _point(p: queries.SeriesPoint) -> dict:
    return {"period": p.period, "value": p.value, "kind": p.kind, "lower": p.lower, "upper": p.upper}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "database": settings.DB_PATH.exists()}


@app.get("/api/catalog")
def catalog() -> dict:
    cat = catalog_mod.load()
    con = _con()
    try:
        cov = queries.coverage(con)
        sources = {
            r[0]: {"organization": r[1], "name": r[2], "role": r[3]}
            for r in con.execute("SELECT source_id, organization, name, role FROM sources").fetchall()
        }
    finally:
        con.close()
    pairs = []
    for ind in cat.indicators:
        for area in cat.areas:
            freqs = queries.frequencies_for(cov, ind.id, area.id)
            if not freqs:
                continue
            has_actual = any(
                r["indicator_id"] == ind.id and r["area_id"] == area.id and r["role"] == "actual" for r in cov
            )
            pairs.append(
                {
                    "indicator_id": ind.id,
                    "area_id": area.id,
                    "frequencies": {f: sorted(s) for f, s in sorted(freqs.items())},
                    "source_count": len(set().union(*freqs.values())),
                    "has_actual": has_actual,
                }
            )
    return {
        "groups": [g.model_dump() for g in cat.groups],
        "areas": [a.model_dump() for a in cat.areas],
        "indicators": [i.model_dump() for i in cat.indicators],
        "pairs": pairs,
        "sources": sources,
        "notes": {f"{s.source}|{s.indicator}|{s.area}": s.note for s in cat.series if s.note},
    }


@app.get("/api/view")
def view(
    indicator: str,
    area: str,
    frequency: Literal["A", "Q", "M", "MY"],
    mode: Literal["latest", "asof", "manual"] = "latest",
    asof: date | None = None,
    sources: str | None = Query(None, description="comma-separated source ids; default — all"),
    releases: str | None = Query(None, description="comma-separated release ids for mode=manual"),
    last_n: int = Query(1, ge=1, le=60, description="releases per source in latest/asof mode"),
) -> dict:
    cat = catalog_mod.load()
    ind = cat.indicator(indicator)
    if ind is None:
        raise HTTPException(404, "Показатель не найден")
    con = _con()
    try:
        cov = queries.coverage(con)
        available = queries.frequencies_for(cov, indicator, area).get(frequency, set())
        wanted = set(sources.split(",")) if sources else available
        manual = set(releases.split(",")) if releases else set()
        meta = {r[0]: r for r in con.execute("SELECT source_id, organization, name FROM sources").fetchall()}
        out_sources = []
        for source_id in sorted(available):
            rows, derived = queries.releases_of(con, indicator, area, source_id, frequency)
            chosen = queries.select_releases(rows, mode, asof, manual, last_n) if source_id in wanted else []
            series = [
                queries.release_series(con, r, indicator, area, source_id, frequency, derived) for r in chosen
            ]
            if derived and source_id in wanted and not any(s.points for s in series):
                continue  # e.g. one quarter per year cannot be averaged into an annual value
            out_sources.append(
                {
                    "source_id": source_id,
                    "organization": meta[source_id][1],
                    "name": meta[source_id][2],
                    "note": next(
                        (
                            s.note
                            for s in cat.series
                            if s.source == source_id and s.indicator == indicator and s.area == area
                        ),
                        None,
                    ),
                    "derived_from": derived,
                    "available_releases": [
                        {"release_id": r[0], "title": r[1], "vintage_date": r[2]} for r in rows
                    ],
                    "releases": [
                        {
                            "release_id": s.release_id,
                            "title": s.title,
                            "vintage_date": s.vintage_date,
                            "points": [_point(p) for p in s.points],
                        }
                        for s in series
                    ],
                }
            )
        actual = queries.actual_series(con, cat, indicator, area, frequency, asof if mode == "asof" else None)
    finally:
        con.close()
    area_obj = next((a for a in cat.areas if a.id == area), None)
    return {
        "indicator": ind.model_dump(),
        "area": area_obj.model_dump() if area_obj else {"id": area, "name": area},
        "frequency": frequency,
        "mode": mode,
        "asof": asof,
        "actual": None
        if actual is None
        else {
            "source_id": actual.source_id,
            "release_id": actual.release_id,
            "title": actual.title,
            "vintage_date": actual.vintage_date,
            "derived_from": actual.derived_from,
            "points": [_point(p) for p in actual.points],
        },
        "sources": out_sources,
    }


class ModelRequest(BaseModel):
    indicator: str
    area: str
    frequency: Literal["A", "Q", "M"]
    model: str
    horizon: int = Field(8, ge=1, le=60)
    cutoff: str | None = None
    asof: date | None = None
    params: dict = Field(default_factory=dict)


@app.get("/api/models")
def models() -> list[dict]:
    return [
        {"code": m.code, "name": m.name, "description": m.description, "params": m.params}
        for m in benchmarks.MODELS.values()
    ]


def _cache_key(req: ModelRequest, actual_release: str, origin: str) -> str:
    payload = json.dumps(
        [req.model, req.params, req.indicator, req.area, req.frequency, origin, actual_release, req.horizon],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


@app.post("/api/models/run")
def run_model(req: ModelRequest) -> dict:
    if req.model not in benchmarks.MODELS:
        raise HTTPException(404, "Неизвестная модель")
    cat = catalog_mod.load()
    con = _con()
    try:
        actual = queries.actual_series(con, cat, req.indicator, req.area, req.frequency, req.asof)
    finally:
        con.close()
    if actual is None or not actual.points:
        raise HTTPException(422, "Для показателя нет фактического ряда — модель не на чем обучать")
    points = [p for p in actual.points if not req.cutoff or p.period <= req.cutoff]
    if not points:
        raise HTTPException(422, "До точки отсечения нет наблюдений")
    origin = points[-1].period
    run_id = _cache_key(req, actual.release_id, origin)
    rw = _con()
    try:
        cached = rw.execute(
            "SELECT target_period, value, lower80, upper80, lower95, upper95 FROM benchmark_forecasts "
            "WHERE run_id = ? ORDER BY target_period",
            [run_id],
        ).fetchall()
        info = {}
        if not cached:
            y = np.array([p.value for p in points])
            m = periods.SEASON[req.frequency]
            future = [periods.shift(origin, k) for k in range(1, req.horizon + 1)]
            seasons = np.array(
                [periods.season_index(p.period) for p in points] + [periods.season_index(p) for p in future]
            )
            try:
                fc = benchmarks.run(req.model, y, req.horizon, m, req.params, seasons)
            except benchmarks.ModelUnavailable as exc:
                raise HTTPException(422, str(exc)) from exc
            info = fc.info
            rw.execute(
                "INSERT OR IGNORE INTO benchmark_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    run_id,
                    req.model,
                    json.dumps({**req.params, "horizon": req.horizon, "info": info}, default=str),
                    req.indicator,
                    req.area,
                    req.frequency,
                    origin,
                    actual.release_id,
                    datetime.now(),
                ],
            )
            cached = [
                (
                    future[k],
                    float(fc.mean[k]),
                    float(fc.lo80[k]),
                    float(fc.hi80[k]),
                    float(fc.lo95[k]),
                    float(fc.hi95[k]),
                )
                for k in range(req.horizon)
            ]
            rw.executemany(
                "INSERT OR IGNORE INTO benchmark_forecasts VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(run_id, *row) for row in cached],
            )
        else:
            params = rw.execute("SELECT params FROM benchmark_runs WHERE run_id = ?", [run_id]).fetchone()
            info = json.loads(params[0]).get("info", {}) if params else {}
    finally:
        rw.close()
    spec = benchmarks.MODELS[req.model]
    return {
        "run_id": run_id,
        "model": req.model,
        "name": spec.name,
        "description": spec.description,
        "origin": origin,
        "actual_release": actual.release_id,
        "info": info,
        "points": [
            {"period": p, "value": v, "lower80": l8, "upper80": u8, "lower95": l9, "upper95": u9}
            for p, v, l8, u8, l9, u9 in cached
        ],
    }


class ExportRequest(BaseModel):
    title: str
    columns: list[str]
    rows: list[list]
    format: Literal["csv", "xlsx"] = "csv"


@app.post("/api/export")
def export(req: ExportRequest) -> Response:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in req.title)[:60] or "export"
    if req.format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(req.columns)
        writer.writerows(req.rows)
        return Response(
            "﻿" + buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'},
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "Данные"
    ws.append(req.columns)
    for row in req.rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}.xlsx"'},
    )


@app.get("/api/status")
def status() -> dict:
    con = _con()
    try:
        return queries.status(con)
    finally:
        con.close()


if settings.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=settings.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        target = settings.WEB_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(settings.WEB_DIST / "index.html")
