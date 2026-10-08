from datetime import date, datetime
from pathlib import Path

import pytest

from fdash.core.catalog import Area, Catalog, Featured, Group, Indicator, Series, SourceInfo
from fdash.store import db

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def con(tmp_path):
    connection = db.connect(tmp_path / "q.duckdb")
    for source_id, role in [("fc", "forecast"), ("old", "forecast"), ("act", "actual")]:
        connection.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?)",
            [source_id, source_id, source_id.upper(), "http://x", "lic", "api", role],
        )

    def release(release_id, source_id, vintage, points):
        connection.execute(
            "INSERT INTO releases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [release_id, source_id, release_id, vintage, None, datetime(2026, 1, 1), "raw", "u", "x"],
        )
        for period, value, kind in points:
            connection.execute(
                "INSERT INTO observations VALUES (?, 'ind', 'RU', ?, 'A', ?, NULL, NULL, ?)",
                [release_id, period, value, kind],
            )

    release(
        "fc_2024",
        "fc",
        date(2024, 3, 1),
        [("2023", 7.0, "estimate"), ("2024", 5.0, "forecast"), ("2025", 4.0, "forecast")],
    )
    release(
        "fc_2025",
        "fc",
        date(2025, 3, 1),
        [("2024", 9.0, "estimate"), ("2025", 6.0, "forecast"), ("2026", 4.5, "forecast")],
    )
    release("old_2023", "old", date(2023, 3, 1), [("2023", 3.0, "forecast")])
    release(
        "act_1",
        "act",
        date(2026, 2, 1),
        [("2023", 7.4, "actual"), ("2024", 9.5, "actual"), ("2025", 5.6, "actual")],
    )
    yield connection
    connection.close()


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(
        featured=[
            Featured(id="x", indicator="ind", area="RU", category="c", title="T", short="T", description="d")
        ],
        source_info={"fc": SourceInfo(short="FC", color="#123456", description="fc")},
        groups=[Group(id="A", name="A")],
        areas=[Area(id="RU", name="Россия", kind="country")],
        indicators=[
            Indicator(
                id="ind", name="I", unit="%", transform="dec_dec", groups=["A"], actual_sources={"RU": "act"}
            )
        ],
        series=[Series(source="fc", code="c", indicator="ind", area="RU")],
    )
