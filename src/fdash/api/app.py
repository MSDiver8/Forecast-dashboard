"""HTTP API for the dashboard and static hosting of the built frontend."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal

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
from fdash.store import accuracy, db, model_runs, queries

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
        "news": queries.news_block(con, cat),
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


class EvaluationModel(BaseModel):
    code: str
    params: dict = Field(default_factory=dict)


class EvaluationRequest(BaseModel):
    featured: str
    frequency: Literal["A", "Q", "M"] | None = None
    window: int | None = Field(None, ge=0, le=3)
    fact: Literal["latest", "first"] = "latest"
    sources: list[str] | None = None  # None — every agency
    models: list[EvaluationModel] = Field(default_factory=list)
    model_frequency: Literal["A", "Q", "M"] | None = None
    period: str | None = None
    evolution: bool = False  # the path of forecasts for `period` by publication date
    metrics_from: str | None = None  # range of target periods for the metrics
    metrics_to: str | None = None
    metrics_include: list[str] = Field(default_factory=list)  # partial series to show anyway


@app.post("/api/evaluation")
def evaluation(req: EvaluationRequest) -> dict:
    cat = catalog_mod.load()
    item = _featured(cat, req.featured)
    return accuracy.evaluation(
        _con(),
        cat,
        item,
        req.frequency or item.frequency,
        req.window,
        req.fact,
        req.sources,
        [(m.code, m.params) for m in req.models],
        req.model_frequency,
        req.period,
        evolution=req.evolution,
        metrics_from=req.metrics_from,
        metrics_to=req.metrics_to,
        metrics_include=tuple(req.metrics_include),
    )


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
    try:
        result = model_runs.run(
            _con(),
            req.model,
            req.params,
            item.indicator,
            item.area,
            req.frequency,
            points,
            actual_release,
            req.horizon,
        )
    except benchmarks.ModelUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    spec = benchmarks.MODELS[req.model]
    return {
        "run_id": result.run_id,
        "model": req.model,
        "name": spec.name,
        "description": spec.description,
        "origin": result.origin,
        "anchor": points[-1][1],
        "actual_release": actual_release,
        "info": result.info,
        "points": [
            {"period": p, "value": v, "lower80": l8, "upper80": u8, "lower95": l9, "upper95": u9}
            for p, v, l8, u8, l9, u9 in result.rows
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
