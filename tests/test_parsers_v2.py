"""Parsers of the sources added for the curated indicators."""

import json
from datetime import date

import pytest

from fdash.ingest import cbr_mtf, ecb_spf, eurostat_hicp, wb_wdi
from fdash.ingest.base import Release


def release(source_id: str, vintage: date, **extra) -> Release:
    return Release(f"{source_id}_test", source_id, "test", vintage, "http://example", "x", extra)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("4,0", (4.0, None, None)),
        ("6,0–7,0", (6.5, 6.0, 7.0)),
        ("7,4-7,9", (7.65, 7.4, 7.9)),
        ("14,5–14,61", (14.55, 14.5, 14.6)),  # trailing footnote 1
        ("17,51", (17.5, None, None)),  # single value with footnote 1
        ("(-1,0)-(+1,0)", (0.0, -1.0, 1.0)),
        ("-(8,0-10,0)", (-9.0, -10.0, -8.0)),  # a fall of 8-10%
        ("-3,0", (-3.0, None, None)),
    ],
)
def test_cbr_mtf_cells(token, expected):
    assert cbr_mtf.parse_cell(token) == pytest.approx(expected)


@pytest.mark.parametrize(
    "name,first_year,cpi_next,rate_next",
    [
        ("forecast_211022.pdf", "2020", (7.4, 7.9), (5.7, 5.8)),
        ("forecast_230210.pdf", "2022", (5.0, 7.0), (7.0, 9.0)),
        ("forecast_260724.pdf", "2025", (6.0, 7.0), (14.5, 14.6)),
    ],
)
def test_cbr_mtf_tables(fixtures, name, first_year, cpi_next, rate_next):
    parsed = cbr_mtf.CbrMtf().parse(fixtures / "cbr_mtf" / name, release("cbr_mtf", date(2026, 7, 24)))
    assert parsed.data_cutoff == first_year
    by = {(o.indicator_id, o.target_period): o for o in parsed.observations}
    next_year = str(int(first_year) + 1)
    assert by[("cpi_dec", first_year)].kind == "estimate"
    assert (by[("cpi_dec", next_year)].lower, by[("cpi_dec", next_year)].upper) == cpi_next
    assert (by[("key_rate_avg", next_year)].lower, by[("key_rate_avg", next_year)].upper) == rate_next
    assert {o.area_id for o in parsed.observations} == {"RU"}


def test_cbr_mtf_release_list(fixtures):
    links = cbr_mtf.list_links((fixtures / "cbr_mtf" / "decision_key_rate.html").read_text(encoding="utf-8"))
    assert links[date(2026, 7, 24)].endswith("forecast_260724.pdf")


def test_ecb_spf_round(fixtures):
    raw = fixtures / "ecb_spf" / "hicp-2026.csv"
    parsed = ecb_spf.EcbSpf().parse(raw, release("ecb_spf", date(2026, 7, 24), round="2026-Q3"))
    values = {o.target_period: o.value for o in parsed.observations}
    assert values == pytest.approx({"2026": 2.73, "2027": 2.17, "2028": 2.0, "2031": 2.04}, abs=0.01)
    html = (fixtures / "ecb_spf" / "spf2026q3-excerpt.html").read_text(encoding="utf-8")
    assert ecb_spf.report_date(html) == date(2026, 7, 24)


def test_eurostat_hicp(fixtures):
    series = eurostat_hicp.read_series(
        json.loads((fixtures / "eurostat_hicp" / "prc_hicp_aind_EA.json").read_text())
    )
    assert series["2022"] == 8.4 and series["2025"] == 2.1


def test_wdi_gdp_matches_bank_of_russia_page(fixtures):
    series = wb_wdi.read_series(json.loads((fixtures / "wb_wdi" / "RUS_NY.GDP.MKTP.KD.ZG.json").read_text()))
    # Figures shown on the Bank of Russia survey page: 5,9 / -1,4 / 4,1 / 4,9 / 1,0
    assert [round(series[y], 1) for y in ("2021", "2022", "2023", "2024", "2025")] == [
        5.9,
        -1.4,
        4.1,
        4.9,
        1.0,
    ]
