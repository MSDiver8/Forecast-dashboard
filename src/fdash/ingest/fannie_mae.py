"""Fannie Mae Economic & Strategic Research: monthly Economic Forecast (PDF), US real GDP, quarterly SAAR.

PDF is an exception approved by the customer on 13 October 2026: the table is read from the text
layer of page 1, projected quarters are the shaded columns ("Shaded areas denote forecasts").
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
    copy_into,
    http_get,
    projection_kind,
    saved_releases,
)
from fdash.ingest.registry import register

BASE = "https://www.fanniemae.com"
ARCHIVE = f"{BASE}/data-and-insights/forecast/forecast-monthly-archive"
# The archive page links every Economic Forecast from September 2020: economic-forecast-<MM><YYYY>
# from July 2022, earlier economic-forecast-<MM><DD><YY> (091520 = 15 September 2020), once with "pdf".
ARCHIVE_LINK = re.compile(r'href="(/media/document/pdf/economic-forecast-(\d{6})(?:pdf)?)"')
HEADER = re.compile(r"^(\d{2})\.([1-4])$")
DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4})"
)
# "Economic Forecast: January 2021" on top of page 1 names the release month
TITLE = re.compile(
    r"Economic Forecast:\s+(January|February|March|April|May|June|July|August|September|October|November"
    r"|December)\s+(\d{4})"
)
WHITE_OR_BLACK = (None, 0, 1, (0,), (1,), (0, 0, 0), (1, 1, 1), [0], [1], [0, 0, 0], [1, 1, 1])


def read_pdf(path: Path) -> tuple[date, list[tuple[str, float, bool]]]:
    """Publication date and (YYYY-Qn, value, projected) of 'Gross Domestic Product' on page 1."""
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        if "Quarterly SAAR" not in text or "Shaded areas denote forecasts" not in text:
            raise SourceStructureError(
                f"{path.name}: units 'Quarterly SAAR' or forecast shading note not found"
            )
        words = page.extract_words()
        heads = [w for w in words if HEADER.match(w["text"])]
        heads = [w for w in heads if heads and abs(w["top"] - heads[0]["top"]) < 2]
        line = next((s for s in text.splitlines() if s.startswith("Gross Domestic Product ")), None)
        label = next((w for w in words if w["text"] == "Gross"), None)
        if len(heads) != 12 or line is None or label is None:
            raise SourceStructureError(f"{path.name}: 12 quarterly columns and the GDP row expected")
        values = [float(v) for v in line.removeprefix("Gross Domestic Product ").split()]
        if len(values) < len(heads):
            raise SourceStructureError(f"{path.name}: fewer GDP values than quarterly columns")
        y = (label["top"] + label["bottom"]) / 2
        points = []
        for head, value in zip(heads, values, strict=False):
            x = (head["x0"] + head["x1"]) / 2
            shaded = any(
                r["x0"] <= x <= r["x1"]
                and r["top"] <= y <= r["bottom"]
                and r["non_stroking_color"] not in WHITE_OR_BLACK
                for r in page.rects
            )
            yy, q = HEADER.match(head["text"]).groups()
            points.append((f"20{yy}-Q{q}", value, shaded))
        found = DATE.search(text)
        if not found:
            raise SourceStructureError(f"{path.name}: publication date not found")
    published = datetime.strptime(" ".join(found.groups()), "%B %d %Y").date()
    title = TITLE.search(text)
    if title and title.group(1) == found.group(1) and int(title.group(2)) != published.year:
        # the January 2021 release is dated "January 11, 2020": the year of the title is taken
        published = published.replace(year=int(title.group(2)))
    return published, points


def archive_links(html: str) -> dict[tuple[int, int], str]:
    """(year, month) -> PDF address of each Economic Forecast linked from the archive page."""
    found: dict[tuple[int, int], str] = {}
    for href, digits in ARCHIVE_LINK.findall(html):
        # MMYYYY, or MMDDYY for releases before July 2022; a day of 20 gives the same month either way
        year = int(digits[2:]) if digits[2:4] == "20" else 2000 + int(digits[4:])
        found.setdefault((year, int(digits[:2])), BASE + href)
    return found


class FannieMae(Connector):
    source_id = "fannie_mae"
    name = "Economic Forecast (Economic & Strategic Research Group)"
    organization = "Fannie Mae"
    url = ARCHIVE
    license = "Fannie Mae, публичная публикация; используется со ссылкой на источник"
    access = "PDF по постоянной ссылке на месяц"

    def __init__(self) -> None:
        self._downloaded: dict[str, Path] = {}
        self._tmp: Path | None = None

    def _save_temp(self, release_id: str, content: bytes) -> Path:
        """The PDF is read before it is saved: the publication date is known only from its text."""
        if self._tmp is None:
            self._tmp = Path(tempfile.mkdtemp(prefix="fdash_"))
        path = self._tmp / f"{release_id}.pdf"
        path.write_bytes(content)
        self._downloaded[release_id] = path
        return path

    def list_releases(self) -> list[Release]:
        saved = saved_releases(self.source_id)
        page = http_get(ARCHIVE)
        page.raise_for_status()
        releases = []
        for (year, month), url in sorted(archive_links(page.text).items()):
            release_id = f"{self.source_id}_{year}_{month:02d}"
            if release_id in saved:
                releases.append(saved[release_id])
                continue
            response = http_get(url)
            content_type = response.headers.get("content-type", "")
            if response.status_code != 200 or not content_type.startswith("application/pdf"):
                # e.g. 403: the site blocks some clients; a failed check must not pass for "nothing new"
                raise SourceStructureError(f"{url}: answer {response.status_code} {content_type}")
            published, _ = read_pdf(self._save_temp(release_id, response.content))
            releases.append(
                Release(
                    release_id=release_id,
                    source_id=self.source_id,
                    title=f"Economic Forecast {month:02d}.{year}",
                    vintage_date=published,
                    url=url,
                    filename="economic-forecast.pdf",
                    extra={"month": f"{year}-{month:02d}"},
                )
            )
        return releases

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


register(FannieMae())
