from datetime import date
from pathlib import Path

import pytest

from fdash import settings
from fdash.ingest import runner
from fdash.ingest.base import Connector, Observation, Parsed, Release
from fdash.store import db, queries


class FakeConnector(Connector):
    source_id = "fake"
    name = "Fake"
    organization = "Test"
    url = "http://example"
    license = "test"
    access = "test"

    def list_releases(self):
        return []

    def parse(self, raw: Path, release: Release) -> Parsed:
        months = [
            Observation("brent_price", "WORLD", f"2025-{m:02d}", "M", float(m), "forecast")
            for m in range(1, 13)
        ]
        return Parsed(months, data_cutoff=None)


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    monkeypatch.setattr(settings, "RAW_DIR", tmp_path / "data" / "raw")
    connection = db.connect(tmp_path / "test.duckdb")
    yield connection
    connection.close()


def test_migrations_are_idempotent(con):
    assert db.migrate(con) == []
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    assert {"observations", "releases", "benchmark_runs", "ingestion_log"} <= tables


def test_release_is_loaded_once_and_annual_view_is_derived(con):
    rel = Release("fake_1", "fake", "Fake 1", date(2025, 1, 1), "http://example", "raw.txt")
    rel.raw_path.parent.mkdir(parents=True)
    rel.raw_path.write_text("x")
    connector = FakeConnector()
    assert runner.load_release(con, connector, rel, date(2025, 1, 2)) == 12
    assert runner.load_release(con, connector, rel, date(2025, 1, 2)) == 0
    rows, derived = queries.releases_of(con, "brent_price", "WORLD", "fake", "A")
    assert derived == "M" and len(rows) == 1
    series = queries.release_series(con, rows[0], "brent_price", "WORLD", "fake", "A", derived)
    assert [(p.period, p.value) for p in series.points] == [("2025", 6.5)]
