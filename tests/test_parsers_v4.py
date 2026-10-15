"""Finer actual series for the accuracy tab: Rosstat quarterly GDP, monthly CPI and key rate, Eurostat."""

import json
import shutil
from datetime import date

import pytest

from fdash.ingest import cbr_stats, eurostat_hicp, rosstat_gdp_q
from fdash.ingest.base import Release


def test_rosstat_quarterly_gdp_growth(fixtures):
    folder = fixtures / "rosstat_gdp_q"
    growth = rosstat_gdp_q.read_growth(folder / "VVP_kvartal_s-1995-2026.xlsx")
    assert next(iter(growth)) == "1996-Q1" and list(growth)[-1] == "2026-Q2"
    # sheet 12 (from 2012): index 101,31 for II quarter 2026, 99,85 for I quarter 2026
    assert growth["2026-Q2"] == pytest.approx(1.31, abs=0.005)
    assert growth["2026-Q1"] == pytest.approx(-0.15, abs=0.005)
    assert growth["2012-Q1"] == pytest.approx(5.70, abs=0.005)
    html = (folder / "accounts-excerpt.html").read_text(encoding="utf-8")
    assert (
        rosstat_gdp_q.file_url(html)
        == "https://rosstat.gov.ru/storage/mediabank/VVP_kvartal_s-1995-2026.xlsx"
    )


def test_cbr_monthly_inflation_and_key_rate(fixtures, tmp_path):
    raw = tmp_path / "infl.xlsx"
    shutil.copyfile(fixtures / "cbr_stats" / "infl.xlsx", raw)
    shutil.copyfile(fixtures / "cbr_stats" / "keyrate-soap-response.xml", tmp_path / "keyrate.xml")
    release = Release("r", "cbr_stats", "t", date(2026, 3, 15), "u", "infl.xlsx")
    parsed = cbr_stats.CbrStats().parse(raw, release)
    monthly = {o.target_period: o.value for o in parsed.observations if o.indicator_id == "cpi_yoy_m"}
    annual = {o.target_period: o.value for o in parsed.observations if o.indicator_id == "cpi_dec"}
    assert monthly["2025-12"] == pytest.approx(annual["2025"])  # December y/y is Dec/Dec

    rates = {date(2024, 1, 1): 16.0, date(2024, 7, 29): 18.0, date(2024, 10, 28): 21.0}
    months = cbr_stats.monthly_average_calendar_days(rates, date(2024, 11, 15))
    assert months["2024-07"] == pytest.approx((16 * 28 + 18 * 3) / 31)
    assert months["2024-10"] == pytest.approx((18 * 27 + 21 * 4) / 31)
    assert "2024-11" not in months  # the month of the release is not complete
    started = cbr_stats.monthly_average_calendar_days({date(2013, 9, 13): 5.5}, date(2013, 12, 1))
    assert list(started) == ["2013-10", "2013-11"]  # September 2013 is not complete


def test_eurostat_annual_and_monthly_sets(fixtures, tmp_path):
    folder = fixtures / "eurostat_hicp"
    annual = eurostat_hicp.read_series(json.loads((folder / "prc_hicp_ainr_EA.json").read_text()))
    old = eurostat_hicp.read_series(json.loads((folder / "prc_hicp_aind_EA.json").read_text()))
    assert annual["2022"] == old["2022"] == 8.4 and annual["2025"] == old["2025"] == 2.1
    monthly = eurostat_hicp.read_series(json.loads((folder / "prc_hicp_minr_EA.json").read_text()), "RCH_A")
    assert list(monthly)[0] == "1997-01" and monthly["2025-12"] == 2.0
    with pytest.raises(eurostat_hicp.SourceStructureError):
        eurostat_hicp.read_series(json.loads((folder / "prc_hicp_minr_EA.json").read_text()))

    # a release saved before 2026 holds only the older annual set
    shutil.copyfile(folder / "prc_hicp_aind_EA.json", tmp_path / "prc_hicp_aind_EA.json")
    release = Release("r", "eurostat_hicp", "t", date(2026, 2, 6), "u", "prc_hicp_aind_EA.json")
    parsed = eurostat_hicp.EurostatHicp().parse(tmp_path / "prc_hicp_aind_EA.json", release)
    assert {o.indicator_id for o in parsed.observations} == {"cpi_avg"}
    shutil.copyfile(folder / "prc_hicp_minr_EA.json", tmp_path / "prc_hicp_minr_EA.json")
    parsed = eurostat_hicp.EurostatHicp().parse(tmp_path / "prc_hicp_aind_EA.json", release)
    assert {o.indicator_id for o in parsed.observations} == {"cpi_avg", "cpi_yoy_m"}
