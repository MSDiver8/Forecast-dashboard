from fdash.store import queries


def test_pair_series_returns_every_release_and_actuals(con, catalog):
    data = queries.pair_series(con, catalog, "ind", "RU", "A")
    assert [s["source_id"] for s in data["sources"]] == ["fc", "old"]
    assert [r["release_id"] for r in data["sources"][0]["releases"]] == ["fc_2024", "fc_2025"]
    assert data["sources"][0]["short"] == "FC"
    assert [p["period"] for p in data["actual"]["releases"][0]["points"]] == ["2023", "2024", "2025"]


def test_featured_cards_skip_stale_sources(con, catalog):
    card = queries.featured_cards(con, catalog)[0]
    assert card["last_fact"] == {"period": "2025", "value": 5.6}
    assert card["targets"] == ["2026", "2027"]
    # "old" stopped publishing two years before the newest release, so it is not on the card
    assert [item["source_id"] for item in card["latest"]] == ["fc"]
    assert card["latest"][0]["values"]["2026"]["value"] == 4.5


def test_growth_rates_are_not_averaged_into_years(con, catalog):
    con.execute("INSERT INTO sources VALUES ('qs', 'qs', 'QS', 'http://x', 'lic', 'api', 'forecast')")
    con.execute(
        "INSERT INTO releases VALUES ('qs_1', 'qs', 'q', DATE '2025-06-01', NULL, now(), 'raw', 'u', 'x')"
    )
    for period, value in [("2025-Q1", 1.0), ("2025-Q2", 2.0), ("2025-Q3", 3.0), ("2025-Q4", 4.0)]:
        con.execute(
            "INSERT INTO observations VALUES ('qs_1', 'ind', 'RU', ?, 'Q', ?, NULL, NULL, 'forecast')",
            [period, value],
        )
    annual = queries.pair_series(con, catalog, "ind", "RU", "A")
    assert next(s for s in annual["sources"] if s["source_id"] == "qs")["derived_from"] == "Q"
    catalog.indicators[0].averageable = False  # e.g. growth on the previous quarter
    assert "qs" not in [
        s["source_id"] for s in queries.pair_series(con, catalog, "ind", "RU", "A")["sources"]
    ]
    assert [s["source_id"] for s in queries.pair_series(con, catalog, "ind", "RU", "Q")["sources"]] == ["qs"]


def test_news_block_draws_newest_release_from_last_known_value(con, catalog):
    from datetime import date

    from fdash.core.catalog import News

    catalog.news = News(featured="x", published=date(2026, 10, 13), text="t", sources=["fc"], start="2023")
    news = queries.news_block(con, catalog)
    assert news["title"] == "T" and news["fact"]["points"][0] == {"period": "2023", "value": 7.4}
    line = news["lines"][0]
    assert line["release_title"] == "fc_2025"
    # the path starts at the 2024 estimate, the value known to the source on the release date
    assert [p["period"] for p in line["points"]] == ["2024", "2025", "2026"]


def test_sources_registry_reports_the_last_check(con, catalog):
    from datetime import datetime

    log = [
        (datetime(2026, 10, 1, 9), "ok", None),
        (datetime(2026, 10, 5, 9), "offline", None),  # a rebuild from data/raw does not ask the source
        (datetime(2026, 10, 9, 9), "error", "HTTPStatusError: 403"),
    ]
    for finished, status, error in log:
        con.execute(
            "INSERT INTO ingestion_log (source_id, started_at, finished_at, status, releases, rows_added, "
            "error) VALUES ('fc', ?, ?, ?, 0, 0, ?)",
            [finished, finished, status, error],
        )
    fc = next(s for s in queries.sources_registry(con, catalog) if s["source_id"] == "fc")
    assert fc["checked_at"] == datetime(2026, 10, 1, 9)
    assert fc["check_error"] == "HTTPStatusError: 403" and fc["check_error_at"] == datetime(2026, 10, 9, 9)
