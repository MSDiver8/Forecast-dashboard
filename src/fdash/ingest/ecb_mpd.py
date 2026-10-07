"""ECB Macroeconomic Projection Database: Brent oil price assumption per projection round."""

from __future__ import annotations

import csv
import io
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fdash.ingest.base import Connector, Observation, Parsed, Release, SourceStructureError, http_get
from fdash.ingest.registry import register

API = "https://data-api.ecb.europa.eu/service/data/MPD"
INDEX = "https://www.ecb.europa.eu/press/projections/html/index.en.html"
ROUND_MONTH = {"W": 3, "G": 6, "S": 9, "A": 12}
ROUND_NAME = {"W": "март", "G": "июнь", "S": "сентябрь", "A": "декабрь"}
EXERCISE = re.compile(r"^([WGSA])(\d{2})$")
LINK = re.compile(r"projections(20\d{2})(\d{2})_[a-z]+~[0-9a-f]+\.en\.html")
DATE = re.compile(r"(\d{1,2} [A-Z][a-z]+ \d{4})")


def exercise_month(code: str) -> tuple[int, int]:
    match = EXERCISE.match(code)
    if not match:
        raise ValueError(f"Unknown projection exercise: {code}")
    return 2000 + int(match.group(2)), ROUND_MONTH[match.group(1)]


def publication_dates(html: str) -> dict[tuple[int, int], date]:
    """(year, month) of a projection round -> publication date; the date follows the link."""
    tokens = sorted(
        [(m.start(), "L", (int(m.group(1)), int(m.group(2)))) for m in LINK.finditer(html)]
        + [(m.start(), "D", m.group(1)) for m in DATE.finditer(html)]
    )
    result: dict[tuple[int, int], date] = {}
    pending = None
    for _, kind, value in tokens:
        if kind == "L":
            pending = value
        elif pending is not None:
            try:
                published = datetime.strptime(value, "%d %B %Y").date()
            except ValueError:
                continue
            if (published.year, published.month) == pending:
                result.setdefault(pending, published)
            pending = None
    return result


def get_csv(url: str, attempts: int = 6, pause: float = 15.0) -> str:
    """The ECB portal sometimes answers with an HTML error page (also with status 200)."""
    last = ""
    for attempt in range(attempts):
        response = http_get(url)
        text = response.text
        if response.status_code == 200 and text.startswith("KEY,"):
            return text
        last = f"HTTP {response.status_code}: {text[:80]!r}"
        if attempt < attempts - 1:
            time.sleep(pause)
    raise RuntimeError(f"ECB API did not return CSV after {attempts} attempts: {last}")


def parse_csv(text: str, required: frozenset = frozenset({"KEY", "FREQ", "PD_SEAS_EX"})) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if rows and not required <= rows[0].keys():
        raise SourceStructureError(f"MPD csv: columns {sorted(required - rows[0].keys())} missing")
    return rows


class EcbMpd(Connector):
    source_id = "ecb_mpd"
    name = "Macroeconomic projections: oil price assumption"
    organization = "ЕЦБ"
    url = INDEX
    license = "ECB statistics, reuse with attribution"
    access = "SDMX REST API без ключа"
    key_prefix = "A+Q.A1.POU.U"
    items = {("POU", "U"): ("brent_price", "WORLD")}
    file_prefix = "MPD_POU"
    areas: set[str] = set()

    def list_releases(self) -> list[Release]:
        keys = get_csv(f"{API}/..POU...?format=csvdata&detail=serieskeysonly")
        exercises = sorted({r["PD_SEAS_EX"] for r in parse_csv(keys) if EXERCISE.match(r["PD_SEAS_EX"])})
        index = http_get(INDEX)
        known = publication_dates(index.text) if index.status_code == 200 else {}
        since = date.today() - timedelta(days=365 * 5 + 92)
        releases = []
        for code in exercises:
            year, month = exercise_month(code)
            published = known.get((year, month))
            approx = published is None
            published = published or date(year, month, 15)
            if published < since or published > date.today():
                continue
            releases.append(
                Release(
                    release_id=f"{self.source_id}_{year}_{month:02d}",
                    source_id=self.source_id,
                    title=f"Прогноз ЕЦБ, {ROUND_NAME[code[0]]} {year}" + (" (дата ≈)" if approx else ""),
                    vintage_date=published,
                    url=f"{API}/{self.key_prefix}.{code}.0000?format=csvdata",
                    filename=f"{self.file_prefix}_{code}.csv",
                    extra={"exercise": code, "approximate_date": approx},
                )
            )
        return releases

    def fetch(self, release: Release) -> Path:
        release.raw_path.parent.mkdir(parents=True, exist_ok=True)
        release.raw_path.write_text(get_csv(release.url), encoding="utf-8")
        return release.raw_path

    def parse(self, raw: Path, release: Release) -> Parsed:
        rows = parse_csv(
            raw.read_text(encoding="utf-8"), frozenset({"KEY", "FREQ", "PD_ITEM", "TIME_PERIOD", "OBS_VALUE"})
        )
        if not rows:
            raise SourceStructureError(f"{raw.name}: no observations")
        published = release.vintage_date
        observations = []
        for r in rows:
            target = self.items.get((r["PD_ITEM"], r["SERIES_DENOM"]))
            if not r["OBS_VALUE"] or target is None:
                continue
            if self.areas and r["REF_AREA"] not in self.areas:
                continue
            period, freq = r["TIME_PERIOD"], r["FREQ"]
            year = int(period[:4])
            if freq == "A":
                past = year < published.year
            else:
                quarter_end_month = int(period[-1]) * 3
                past = (year, quarter_end_month) < (published.year, published.month)
            observations.append(
                Observation(
                    target[0],
                    target[1],
                    period,
                    freq,
                    float(r["OBS_VALUE"]),
                    "estimate" if past else "forecast",
                )
            )
        return Parsed(observations, data_cutoff=None)


class EcbMpdMacro(EcbMpd):
    """Euro area real GDP growth, HICP inflation and unemployment from the same projection rounds."""

    source_id = "ecb_mpd_macro"
    name = "Macroeconomic projections: euro area"
    key_prefix = "A.U2.YER+HIC+URX.A+F"
    items = {
        ("YER", "A"): ("gdp_growth", "EA"),
        ("HIC", "A"): ("cpi_avg", "EA"),
        ("URX", "F"): ("unemployment_avg", "EA"),
    }
    file_prefix = "MPD_U2"
    areas = {"U2"}


register(EcbMpd())
register(EcbMpdMacro())
