import pytest

from fdash.store import queries


def test_pair_series_returns_every_release_and_actuals(con, catalog):
    data = queries.pair_series(con, catalog, "ind", "RU", "A")
    assert [s["source_id"] for s in data["sources"]] == ["fc", "old"]
    assert [r["release_id"] for r in data["sources"][0]["releases"]] == ["fc_2024", "fc_2025"]
    assert data["sources"][0]["short"] == "FC"
    assert [p["period"] for p in data["actual"]["releases"][0]["points"]] == ["2023", "2024", "2025"]


def test_evaluation_by_horizon(con, catalog):
    result = queries.evaluation(con, catalog, "ind", "RU", "A")
    fc = next(s for s in result["sources"] if s["source_id"] == "fc")
    horizons = {h["horizon"]: h for h in fc["horizons"]}
    # 2024 release: 2024 (h=0) 5.0 vs 9.5, 2025 (h=1) 4.0 vs 5.6; 2025 release: 2025 (h=0) 6.0 vs 5.6
    assert horizons[0]["n"] == 2 and horizons[0]["mae"] == pytest.approx((4.5 + 0.4) / 2)
    assert horizons[1]["n"] == 1 and horizons[1]["bias"] == pytest.approx(-1.6)


def test_featured_cards_skip_stale_sources(con, catalog):
    card = queries.featured_cards(con, catalog)[0]
    assert card["last_fact"] == {"period": "2025", "value": 5.6}
    assert card["targets"] == ["2026", "2027"]
    # "old" stopped publishing two years before the newest release, so it is not on the card
    assert [item["source_id"] for item in card["latest"]] == ["fc"]
    assert card["latest"][0]["values"]["2026"]["value"] == 4.5
