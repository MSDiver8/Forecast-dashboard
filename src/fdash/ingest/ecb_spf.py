"""ECB Survey of Professional Forecasters: euro area HICP inflation for calendar years."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fdash.ingest.base import Connector, Observation, Parsed, Release, SourceStructureError, http_get
from fdash.ingest.ecb_mpd import get_csv
from fdash.ingest.registry import register

API = "https://data-api.ecb.europa.eu/service/data/SPF/Q.U2.HICP.POINT..Q.AVG"
REPORT = "https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/ecb.spf{year}q{q}.en.html"
ONLINE_DATE = re.compile(r'citation_online_date"\s+content="(\d{1,2} [A-Z][a-z]+ \d{4})"')
ROUND = re.compile(r"^(\d{4})-Q([1-4])$")


def report_date(html: str) -> date | None:
    match = ONLINE_DATE.search(html)
    return datetime.strptime(match.group(1), "%d %B %Y").date() if match else None


def parse_rows(text: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if rows and not {"TIME_PERIOD", "FCT_HORIZON", "OBS_VALUE"} <= rows[0].keys():
        raise SourceStructureError("SPF csv: unexpected columns")
    return rows


class EcbSpf(Connector):
    source_id = "ecb_spf"
    name = "Survey of Professional Forecasters: HICP"
    organization = "ЕЦБ, опрос SPF"
    url = "https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html"
    license = "ECB statistics, reuse with attribution"
    access = "SDMX REST API без ключа"

    def list_releases(self) -> list[Release]:
        since = date.today() - timedelta(days=365 * 5 + 92)
        rows = parse_rows(get_csv(f"{API}?format=csvdata&detail=dataonly&startPeriod={since.year}-Q1"))
        rounds = sorted(
            {r["TIME_PERIOD"] for r in rows if ROUND.match(r["TIME_PERIOD"]) and r["FCT_HORIZON"].isdigit()}
        )
        releases = []
        for code in rounds:
            year, quarter = (int(x) for x in ROUND.match(code).groups())
            first_month = 3 * quarter - 2
            published = None
            if year >= date.today().year - 1:
                page = http_get(REPORT.format(year=year, q=quarter))
                if page.status_code == 200:
                    published = report_date(page.text)
            approx = published is None
            published = published or date(year, first_month, 25)
            if published < since or published > date.today():
                continue
            releases.append(
                Release(
                    release_id=f"ecb_spf_{year}_q{quarter}",
                    source_id=self.source_id,
                    title=f"SPF {quarter} кв. {year}" + (" (дата ≈)" if approx else ""),
                    vintage_date=published,
                    url=f"{API}?format=csvdata&startPeriod={code}&endPeriod={code}",
                    filename=f"SPF_HICP_{year}Q{quarter}.csv",
                    extra={"round": code, "approximate_date": approx},
                )
            )
        return releases

    def fetch(self, release: Release) -> Path:
        release.raw_path.parent.mkdir(parents=True, exist_ok=True)
        release.raw_path.write_text(get_csv(release.url), encoding="utf-8")
        return release.raw_path

    def parse(self, raw: Path, release: Release) -> Parsed:
        rows = parse_rows(raw.read_text(encoding="utf-8"))
        round_year = int(release.extra["round"][:4])
        observations = [
            Observation(
                "cpi_avg",
                "EA",
                r["FCT_HORIZON"],
                "A",
                float(r["OBS_VALUE"]),
                "estimate" if int(r["FCT_HORIZON"]) < round_year else "forecast",
            )
            for r in rows
            if r["TIME_PERIOD"] == release.extra["round"] and r["FCT_HORIZON"].isdigit() and r["OBS_VALUE"]
        ]
        if not observations:
            raise SourceStructureError(f"{raw.name}: no calendar-year HICP expectations")
        return Parsed(observations, data_cutoff=None)


register(EcbSpf())
