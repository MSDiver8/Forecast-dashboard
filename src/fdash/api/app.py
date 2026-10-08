"""HTTP API for the dashboard and static hosting of the built frontend."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException
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

app = FastAPI(title="Forecast dashboard API", version="0.2.0")
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


def _featured(cat: catalog_mod.Catalog, featured_id: str) -> catalog_mod.Featured:
    item = next((f for f in cat.featured if f.id == featured_id), None)
    if item is None:
        raise HTTPException(404, "Показатель не найден")
    return item


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "database": settings.DB_PATH.exists()}


@app.get("/api/featured")
def featured() -> dict:
    cat = catalog_mod.load()
    con = _con()
    cards = queries.featured_cards(con, cat)
    sources = queries.sources_registry(con, cat)
    last = con.execute(
        """
        SELECT r.title, r.vintage_date, r.source_id FROM releases r JOIN sources s USING (source_id)
        WHERE s.role = 'forecast' ORDER BY r.vintage_date DESC, r.source_id LIMIT 30
        """
    ).fetchall()
    feed, seen = [], set()
    for title, vintage, source_id in last:
        short = cat.source_info[source_id].short if source_id in cat.source_info else source_id
        if (short, title) in seen:
            continue
        seen.add((short, title))
        feed.append((title, vintage, source_id))
    return {
        "cards": cards,
        "totals": {
            "indicators": len(cards),
            "sources": sum(1 for s in sources if s["role"] == "forecast"),
            "releases": sum(s["releases"] for s in sources if s["role"] == "forecast"),
            "last_update": max((c["last_update"] for c in cards if c["last_update"]), default=None),
        },
        "latest_releases": [
            {
                "title": title,
                "vintage_date": vintage,
                "short": cat.source_info[s].short if s in cat.source_info else s,
                "color": cat.source_info[s].color if s in cat.source_info else "#555",
            }
            for title, vintage, s in feed[:8]
        ],
    }


@app.get("/api/series/{featured_id}")
def series(featured_id: str, frequency: Literal["A", "Q", "M"] | None = None) -> dict:
    cat = catalog_mod.load()
    item = _featured(cat, featured_id)
    freq = frequency or item.frequency
    data = queries.pair_series(_con(), cat, item.indicator, item.area, freq)
    if freq not in data["frequencies"]:
        raise HTTPException(404, "Для этой частоты нет данных")
    indicator = cat.indicator(item.indicator)
    return {"featured": item.model_dump(), "indicator": indicator.model_dump(), "frequency": freq, **data}


@app.get("/api/evaluation/{featured_id}")
def evaluation(featured_id: str, frequency: Literal["A", "Q", "M"] | None = None) -> dict:
    cat = catalog_mod.load()
    item = _featured(cat, featured_id)
    return queries.evaluation(_con(), cat, item.indicator, item.area, frequency or item.frequency)


@app.get("/api/sources")
def sources() -> list[dict]:
    return queries.sources_registry(_con(), catalog_mod.load())


@app.get("/api/models")
def models() -> list[dict]:
    return [
        {"code": m.code, "name": m.name, "description": m.description, "params": m.params}
        for m in benchmarks.MODELS.values()
    ]


class ModelRequest(BaseModel):
    featured: str
    frequency: Literal["A", "Q", "M"]
    model: str
    horizon: int = Field(4, ge=1, le=60)
    cutoff: str | None = None
    asof: date | None = None
    params: dict = Field(default_factory=dict)


def _training_series(cat, item, frequency: str, asof: date | None) -> tuple[str, list[tuple[str, float]]]:
    """Actuals known at `asof`: the latest actual release published by then, else today's series cut."""
    data = queries.pair_series(_con(), cat, item.indicator, item.area, frequency)
    if not data["actual"]:
        raise HTTPException(422, "Для показателя нет фактического ряда — модель не на чем обучать")
    releases = data["actual"]["releases"]
    known = [r for r in releases if asof is None or r["vintage_date"] <= asof]
    release = known[-1] if known else releases[-1]
    points = [(p["period"], p["value"]) for p in release["points"]]
    if asof is not None:
        last_known = periods.shift(queries.period_of(asof, frequency), -1)
        points = [p for p in points if p[0] <= last_known]
    return release["release_id"], points


@app.post("/api/models/run")
def run_model(req: ModelRequest) -> dict:
    if req.model not in benchmarks.MODELS:
        raise HTTPException(404, "Неизвестная модель")
    cat = catalog_mod.load()
    item = _featured(cat, req.featured)
    actual_release, points = _training_series(cat, item, req.frequency, req.asof)
    points = [p for p in points if not req.cutoff or p[0] <= req.cutoff]
    if not points:
        raise HTTPException(422, "До точки отсечения нет наблюдений")
    origin = points[-1][0]
    key = json.dumps(
        [
            req.model,
            req.params,
            item.indicator,
            item.area,
            req.frequency,
            origin,
            actual_release,
            req.horizon,
        ],
        sort_keys=True,
        default=str,
    )
    run_id = hashlib.sha1(key.encode()).hexdigest()[:16]
    con = _con()
    cached = con.execute(
        "SELECT target_period, value, lower80, upper80, lower95, upper95 FROM benchmark_forecasts "
        "WHERE run_id = ? ORDER BY target_period",
        [run_id],
    ).fetchall()
    if cached:
        params = con.execute("SELECT params FROM benchmark_runs WHERE run_id = ?", [run_id]).fetchone()
        info = json.loads(params[0]).get("info", {}) if params else {}
    else:
        y = np.array([v for _, v in points])
        m = periods.SEASON[req.frequency]
        future = [periods.shift(origin, k) for k in range(1, req.horizon + 1)]
        seasons = np.array(
            [periods.season_index(p) for p, _ in points] + [periods.season_index(p) for p in future]
        )
        try:
            fc = benchmarks.run(req.model, y, req.horizon, m, req.params, seasons)
        except benchmarks.ModelUnavailable as exc:
            raise HTTPException(422, str(exc)) from exc
        info = fc.info
        con.execute(
            "INSERT OR IGNORE INTO benchmark_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                req.model,
                json.dumps({**req.params, "horizon": req.horizon, "info": info}, default=str),
                item.indicator,
                item.area,
                req.frequency,
                origin,
                actual_release,
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
        con.executemany(
            "INSERT OR IGNORE INTO benchmark_forecasts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(run_id, *row) for row in cached],
        )
    spec = benchmarks.MODELS[req.model]
    return {
        "run_id": run_id,
        "model": req.model,
        "name": spec.name,
        "description": spec.description,
        "origin": origin,
        "anchor": points[-1][1],
        "actual_release": actual_release,
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
    return queries.status(_con())


if settings.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=settings.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        target = settings.WEB_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(settings.WEB_DIST / "index.html")
