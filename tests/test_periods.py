from fdash.core import periods


def test_frequency_of():
    assert periods.frequency_of("2026") == "A"
    assert periods.frequency_of("2026-Q4") == "Q"
    assert periods.frequency_of("2026-07") == "M"
    assert periods.frequency_of("2026/27") == "MY"


def test_shift_crosses_year():
    assert periods.shift("2026-12", 1) == "2027-01"
    assert periods.shift("2026-Q4", 2) == "2027-Q2"
    assert periods.shift("2026", -3) == "2023"
    assert periods.shift("2025/26", 1) == "2026/27"


def test_aggregate_mean_needs_complete_subperiods():
    months = [(f"2025-{m:02d}", float(m)) for m in range(1, 13)] + [("2026-01", 100.0)]
    annual = periods.aggregate_mean(months, "A")
    assert annual == {"2025": 6.5}
    quarterly = periods.aggregate_mean(months, "Q")
    assert quarterly["2025-Q1"] == 2.0 and "2026-Q1" not in quarterly


def test_one_quarter_a_year_is_not_an_annual_value():
    assert periods.aggregate_mean([("2025-Q4", 60.0), ("2026-Q4", 62.0)], "A") == {}
