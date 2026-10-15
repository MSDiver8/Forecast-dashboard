"""Accuracy tab: forecasts from a publication window, benchmark models at the window end, metrics."""

from datetime import date, datetime

import pytest

from fdash.core.catalog import Context, Indicator
from fdash.store import accuracy

TODAY = date(2026, 10, 1)


def add_actuals(con, release_id, vintage, indicator, frequency, values):
    con.execute(
        "INSERT INTO releases VALUES (?, 'act', ?, ?, NULL, ?, 'raw', 'u', 'x')",
        [release_id, release_id, vintage, datetime(2026, 1, 1)],
    )
    for period, value in values.items():
        con.execute(
            "INSERT INTO observations VALUES (?, ?, 'RU', ?, ?, ?, NULL, NULL, 'actual')",
            [release_id, indicator, period, frequency, value],
        )


def test_latest_release_in_the_window_and_its_dates(con, catalog):
    item = catalog.featured[0]
    result = accuracy.evaluation(con, catalog, item, "A", window=2, today=TODAY)
    rows = {r["period"]: r for r in result["rows"]}
    # window 2 for annual targets: published from 1 January to 30 June of the target year
    assert (rows["2024"]["window_start"], rows["2024"]["window_end"]) == (date(2024, 1, 1), date(2024, 6, 30))
    assert rows["2024"]["picks"]["fc"]["vintage_date"] == date(2024, 3, 1)
    assert rows["2024"]["picks"]["fc"]["error"] == pytest.approx(5.0 - 9.5)
    assert rows["2023"]["picks"]["old"]["error"] == pytest.approx(3.0 - 7.4)
    assert result["error_unit"] == "п.п." and result["fact_shape"] == "point"  # Dec/Dec is a point
    pending = {
        r["period"]: r for r in accuracy.evaluation(con, catalog, item, "A", window=0, today=TODAY)["rows"]
    }
    assert pending["2026"]["fact"] is None and pending["2026"]["picks"]["fc"]["value"] == 4.5
    with pytest.raises(ValueError):
        accuracy.evaluation(con, catalog, item, "A", window=4)


def test_only_selected_agencies_enter_rows(con, catalog):
    result = accuracy.evaluation(
        con, catalog, catalog.featured[0], "A", window=2, sources=["fc"], today=TODAY
    )
    assert {s["source_id"]: s["selected"] for s in result["sources"]} == {"fc": True, "old": False}
    assert [r["period"] for r in result["rows"]] == ["2024", "2025"]  # 2023 had only the deselected source
    assert result["metrics"]["insufficient"] == [{"kind": "source", "key": "fc", "n": 2}]


def test_models_at_the_window_end_and_metrics(con, catalog, monkeypatch):
    history = {
        str(y): v for y, v in zip(range(2016, 2023), [5.4, 2.5, 4.3, 3.0, 4.9, 8.4, 11.9], strict=True)
    }
    add_actuals(
        con, "act_2", date(2026, 3, 1), "ind", "A", {**history, "2023": 7.4, "2024": 9.5, "2025": 5.6}
    )
    monkeypatch.setattr(accuracy, "MIN_PERIODS", 2)
    result = accuracy.evaluation(
        con,
        catalog,
        catalog.featured[0],
        "A",
        2,
        sources=["fc"],
        models=[("rw", {}), ("ma", {"q": 2})],
        today=TODAY,
    )
    rows = {r["period"]: r for r in result["rows"]}
    # known on 30 June 2025: the actual for 2024; RW repeats it, MA(2) averages 2023 and 2024
    assert rows["2025"]["models"]["rw"]["value"] == pytest.approx(9.5)
    assert rows["2025"]["models"]["ma"]["value"] == pytest.approx((7.4 + 9.5) / 2)
    assert rows["2024"]["models"]["rw"]["value"] == pytest.approx(7.4)
    metrics = {m["key"]: m for m in result["metrics"]["rows"]}
    fc = metrics["fc"]
    assert result["metrics"]["periods"] == ["2024", "2025"] and result["metrics"]["contiguous"]
    assert fc["mae"] == pytest.approx((4.5 + 0.4) / 2)
    assert fc["rmse"] == pytest.approx(((4.5**2 + 0.4**2) / 2) ** 0.5)
    assert fc["me"] == pytest.approx((-4.5 + 0.4) / 2)
    assert fc["mape"] == pytest.approx(100 * (4.5 / 9.5 + 0.4 / 5.6) / 2)
    assert fc["ratio_rw"] == pytest.approx(fc["mae"] / ((2.1 + 3.9) / 2))
    assert metrics["rw"]["ratio_rw"] == pytest.approx(1.0)
    ma = next(m for m in result["models"] if m["code"] == "ma")
    assert ma["selected"] and ma["params"] == {"q": 2}
    arima = next(m for m in result["models"] if m["code"] == "arima")
    assert arima["unavailable"] == {"reason": "short", "need": 30, "have": 10}
    assert next(m for m in result["models"] if m["code"] == "rws")["unavailable"] == {"reason": "seasonal"}


def test_mape_is_left_out_near_zero(con, catalog, monkeypatch):
    add_actuals(con, "act_2", date(2026, 3, 1), "ind", "A", {"2023": 0.4, "2024": 9.5, "2025": 5.6})
    monkeypatch.setattr(accuracy, "MIN_PERIODS", 1)
    result = accuracy.evaluation(con, catalog, catalog.featured[0], "A", 2, today=TODAY)
    old = next(m for m in result["metrics"]["rows"] if m["key"] == "old")
    assert old["mape"] is None and old["mae"] == pytest.approx(2.6)


def test_monthly_model_averaged_to_the_year(con, catalog):
    catalog.indicators[0].transform = "avg_year"
    months = {f"2024-{m:02d}": 9.0 for m in range(1, 13)} | {f"2025-{m:02d}": float(m) for m in range(1, 6)}
    add_actuals(con, "act_m", date(2025, 6, 10), "ind", "M", months)
    item = catalog.featured[0]
    assert [o.frequency for o in accuracy.estimation_options(con, catalog, item, "A")] == ["A", "Q", "M"]
    result = accuracy.evaluation(
        con, catalog, item, "A", 2, models=[("rw", {})], model_frequency="M", today=TODAY
    )
    assert result["estimation"]["frequency"] == "M"
    rows = {r["period"]: r for r in result["rows"]}
    # known on 30 June 2025: January–May; RW carries May (5.0) to June–December
    assert rows["2025"]["models"]["rw"]["value"] == pytest.approx((1 + 2 + 3 + 4 + 5 + 5 * 7) / 12)


def test_december_value_for_dec_dec_inflation(con, catalog):
    catalog.indicators.append(
        Indicator(
            id="ind_m", name="m", unit="%", transform="yoy_m", groups=["A"], actual_sources={"RU": "act"}
        )
    )
    item = catalog.featured[0]
    item.context = Context(indicator="ind_m", frequency="M", label="за месяц")
    add_actuals(
        con, "act_m", date(2025, 6, 10), "ind_m", "M", {f"2025-{m:02d}": 8.0 + m for m in range(1, 6)}
    )
    options = accuracy.estimation_options(con, catalog, item, "A")
    assert [(o.frequency, o.indicator, o.convert) for o in options] == [
        ("A", "ind", "same"),
        ("M", "ind_m", "december"),
    ]
    result = accuracy.evaluation(
        con, catalog, item, "A", 2, models=[("rw", {})], model_frequency="M", today=TODAY
    )
    rows = {r["period"]: r for r in result["rows"]}
    assert rows["2025"]["models"]["rw"]["value"] == pytest.approx(13.0)  # May 2025 carried to December
    assert result["context"]["points"][0] == {"period": "2025-01", "date": date(2025, 1, 15), "value": 9.0}


def test_evolution_of_the_selected_period(con, catalog):
    history = {str(y): float(y - 2010) for y in range(2016, 2023)}
    add_actuals(
        con, "act_2", date(2026, 3, 1), "ind", "A", {**history, "2023": 7.4, "2024": 9.5, "2025": 5.6}
    )
    result = accuracy.evaluation(
        con,
        catalog,
        catalog.featured[0],
        "A",
        2,
        models=[("rw", {})],
        period="2025",
        today=TODAY,
        evolution=True,
    )
    evolution = result["evolution"]
    assert evolution["period"] == "2025" and evolution["fact"] == 5.6
    assert [f["value"] for f in evolution["tracks"]["fc"]] == [4.0, 6.0]
    # RW for 2025 as known on 1 January of 2024 (actual for 2023) and of 2025 (actual for 2024)
    assert [(p["date"], p["value"]) for p in evolution["models"]["rw"]] == [
        (date(2024, 1, 1), 7.4),
        (date(2025, 1, 1), 9.5),
    ]
