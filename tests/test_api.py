import pytest
from fastapi.testclient import TestClient

from fdash import settings
from fdash.api import app as app_module
from fdash.core import catalog as catalog_mod


@pytest.fixture
def client(con, catalog, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "q.duckdb")
    monkeypatch.setattr(app_module, "_shared", con)
    monkeypatch.setattr(catalog_mod, "load", lambda path=None: catalog)
    return TestClient(app_module.app)


def test_featured_and_series(client):
    overview = client.get("/api/featured").json()
    assert overview["totals"]["indicators"] == 1
    assert overview["cards"][0]["id"] == "x"
    series = client.get("/api/series/x").json()
    assert series["frequencies"] == ["A"]
    assert len(series["sources"]) == 2
    assert client.get("/api/series/unknown").status_code == 404


def test_model_run_and_refusal(client):
    ok = client.post("/api/models/run", json={"featured": "x", "frequency": "A", "model": "rw", "horizon": 2})
    assert ok.status_code == 200
    body = ok.json()
    assert body["origin"] == "2025" and [p["period"] for p in body["points"]] == ["2026", "2027"]
    assert body["points"][0]["value"] == pytest.approx(5.6)
    refused = client.post(
        "/api/models/run", json={"featured": "x", "frequency": "A", "model": "arima", "horizon": 2}
    )
    assert refused.status_code == 422 and "30" in refused.json()["detail"]


def test_as_of_training_cuts_actuals(client):
    body = client.post(
        "/api/models/run",
        json={"featured": "x", "frequency": "A", "model": "rw", "horizon": 1, "asof": "2025-02-01"},
    ).json()
    assert body["origin"] == "2024"


def test_export_csv(client):
    response = client.post(
        "/api/export", json={"title": "t", "columns": ["a", "b"], "rows": [[1, 2]], "format": "csv"}
    )
    assert response.status_code == 200 and response.text.startswith("﻿a;b")
