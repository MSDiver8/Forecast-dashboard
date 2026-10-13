"""TD Economics Quarterly Economic Forecast (PDF): US real GDP, period-over-period annualized change.

PDF is an exception approved by the customer on 13 October 2026. The site links only the newest
report; earlier ones are found by the folder and file names TD has used. Reports before December
2025 carry the US table as an image without a text layer and are not read.
"""

from __future__ import annotations

import re
import tempfile
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from fdash.ingest.base import (
    Connector,
    Observation,
    Parsed,
    Release,
    SourceStructureError,
    archive_start,
    client,
    copy_into,
    projection_kind,
    saved_releases,
)
from fdash.ingest.registry import register

SITE = "https://economics.td.com"
PAGE = f"{SITE}/us-quarterly-economic-forecast"
BASE = f"{SITE}/domains/economics.td.com/documents/reports/qef"
FIRST_WITH_TEXT = (2025, 12)
MONTHS = {3: ("mar", "March"), 6: ("jun", "June"), 9: ("sep", "September"), 12: ("dec", "December")}
LINK = re.compile(
    r'href="(/domains/economics\.td\.com/documents/reports/qef/(\d{4})-([a-z]+)/[^"]+_US\.pdf)"', re.I
)
DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4})"
)
QUARTER = re.compile(r"^Q([1-4])(F?)$")
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def candidates(year: int, month: int) -> list[str]:
    """Folder and file names TD used for the US report, e.g. 2026-june/QEF_June2026_US.pdf."""
    short, full = MONTHS[month]
    folders = [f"{year}-{short}", f"{year}-{full.lower()}"]
    names = [
        f"QEF_{full}{year}_US.pdf",
        f"QEF{full}{year}_US.pdf",
        f"qef{short}{year}_us.pdf",
        f"QEF_{short}{year}_US.pdf",
    ]
    return [f"{BASE}/{folder}/{name}" for folder in folders for name in names]


def newest_link(html: str) -> tuple[int, int, str] | None:
    """(year, month, URL) of the US report linked from the forecast page."""
    for path, year, month_name in LINK.findall(html):
        month = next((m for m, (s, f) in MONTHS.items() if month_name.lower() in (s, f.lower())), None)
        if month:
            return int(year), month, SITE + path
    return None


def read_pdf(path: Path) -> tuple[date, list[tuple[str, float, bool]]]:
    """Publication date and (YYYY-Qn, value, projected) of Real GDP from the U.S. Economic Outlook table."""
    with pdfplumber.open(path) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages]
    page = next((t for t in texts if "U.S. Economic Outlook" in t and "\nReal GDP " in t), None)
    if page is None:
        raise SourceStructureError(f"{path.name}: U.S. Economic Outlook table not found in the text layer")
    if "Period-Over-Period Annualized Per Cent Change" not in page:
        raise SourceStructureError(
            f"{path.name}: units 'Period-Over-Period Annualized Per Cent Change' not found"
        )
    lines = page.splitlines()
    years_line = next((s for s in lines if re.match(r"^20\d{2} 20\d{2} 20\d{2}", s)), None)
    quarter_line = next((s for s in lines if re.match(r"^Q1F? Q2F? Q3F? Q4F? ", s)), None)
    gdp_line = next((s for s in lines if s.startswith("Real GDP ")), None)
    if years_line is None or quarter_line is None or gdp_line is None:
        raise SourceStructureError(f"{path.name}: years, quarter header or Real GDP row not found")
    years = [int(y) for y in re.findall(r"20\d{2}", years_line)[:3]]
    quarters = [QUARTER.match(token) for token in quarter_line.split()]
    quarters = [q for q in quarters if q][:12]
    values = [float(v) for v in gdp_line.removeprefix("Real GDP ").split() if NUMBER.match(v)]
    if len(quarters) != 12 or len(years) != 3 or len(values) < 12:
        raise SourceStructureError(f"{path.name}: 12 quarters of 3 years expected")
    # Every quarter after the first one marked F is projected (the September 2026 report omits F on 2027 Q1).
    first = next((i for i, q in enumerate(quarters) if q.group(2)), len(quarters))
    points = [(f"{years[i // 4]}-Q{q.group(1)}", values[i], i >= first) for i, q in enumerate(quarters)]
    found = DATE.search("\n".join(texts[:2]))
    if not found:
        raise SourceStructureError(f"{path.name}: publication date not found")
    return datetime.strptime(" ".join(found.groups()), "%B %d %Y").date(), points


class TdEconomics(Connector):
    source_id = "td_economics"
    name = "Quarterly Economic Forecast: U.S. Economic Outlook"
    organization = "TD Economics"
    url = PAGE
    license = "TD Economics, публичная публикация; используется со ссылкой на источник"
    access = "PDF по ссылке со страницы прогноза (исключение из правила о PDF, решение заказчика 13.10.2026)"

    def __init__(self) -> None:
        self._downloaded: dict[str, Path] = {}
        self._tmp: Path | None = None

    def _save_temp(self, release_id: str, content: bytes) -> Path:
        if self._tmp is None:
            self._tmp = Path(tempfile.mkdtemp(prefix="fdash_"))
        path = self._tmp / f"{release_id}.pdf"
        path.write_bytes(content)
        self._downloaded[release_id] = path
        return path

    def list_releases(self) -> list[Release]:
        saved = saved_releases(self.source_id)
        start, today = archive_start(2), date.today()
        found: dict[tuple[int, int], str] = {}
        with client() as http:
            page = http.get(PAGE)
            page.raise_for_status()
            newest = newest_link(page.text)
            if newest:
                found[(newest[0], newest[1])] = newest[2]
            for year in range(start.year, today.year + 1):
                for month in MONTHS:
                    key = (year, month)
                    if key < FIRST_WITH_TEXT or date(year, month, 1) < start or date(year, month, 1) > today:
                        continue
                    if key in found or f"{self.source_id}_{year}_{month:02d}" in saved:
                        continue
                    for url in candidates(year, month):
                        head = http.head(url)
                        if head.status_code == 200 and "pdf" in head.headers.get("content-type", ""):
                            found[key] = url
                            break
            releases = []
            for (year, month), url in sorted(found.items()):
                release_id = f"{self.source_id}_{year}_{month:02d}"
                if (year, month) < FIRST_WITH_TEXT:
                    continue
                if release_id in saved:
                    continue
                response = http.get(url)
                response.raise_for_status()
                published, _ = read_pdf(self._save_temp(release_id, response.content))
                releases.append(
                    Release(
                        release_id=release_id,
                        source_id=self.source_id,
                        title=f"QEF {month:02d}.{year}",
                        vintage_date=published,
                        url=url,
                        filename="qef_us.pdf",
                        extra={"report": f"{year}-{month:02d}"},
                    )
                )
        return sorted([*saved.values(), *releases], key=lambda r: r.vintage_date)

    def fetch(self, release: Release) -> Path:
        path = self._downloaded.get(release.release_id)
        if path and path.exists():
            return copy_into(path, release)
        return super().fetch(release)

    def parse(self, raw: Path, release: Release) -> Parsed:
        published, points = read_pdf(raw)
        observations = [
            Observation("gdp_qoq_saar", "US", p, "Q", v, projection_kind(p, published, projected))
            for p, v, projected in points
        ]
        actual = [p for p, _, projected in points if not projected]
        return Parsed(observations, data_cutoff=max(actual) if actual else None)


register(TdEconomics())
