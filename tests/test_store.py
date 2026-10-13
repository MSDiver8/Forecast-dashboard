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


class HistoryConnector(FakeConnector):
    """Two releases read from one shared file, as for the Bank of England history."""

    source_id = "hist"

    def list_releases(self):
        return [
            Release(
                f"hist_{y}",
                "hist",
                f"H {y}",
                date(y, 2, 1),
                "http://example/f.zip",
                "f.zip",
                shared="2025-02-01/f.zip",
            )
            for y in (2024, 2025)
        ]

    def fetch(self, release: Release) -> Path:
        release.raw_path.parent.mkdir(parents=True, exist_ok=True)
        release.raw_path.write_text("history")
        return release.raw_path


def test_releases_share_one_raw_file(con, monkeypatch):
    connector = HistoryConnector()
    monkeypatch.setattr(runner, "get", lambda source_id: connector)
    result = runner.ingest_source(con, "hist")
    assert result.error is None and result.releases_added == 2
    files = sorted(
        p.relative_to(settings.RAW_DIR / "hist").as_posix() for p in (settings.RAW_DIR / "hist").rglob("*")
    )
    assert files == [
        "2024-02-01",
        "2024-02-01/release.json",
        "2025-02-01",
        "2025-02-01/f.zip",
        "2025-02-01/release.json",
    ]
    saved = runner.local_releases("hist")
    assert [r.shared for r, _ in saved] == ["2025-02-01/f.zip", "2025-02-01/f.zip"]
    assert runner.ingest_source(con, "hist").releases_added == 0
