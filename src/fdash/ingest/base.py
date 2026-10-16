"""Common connector contract: list_releases() -> fetch(release) -> parse(raw)."""

from __future__ import annotations

import hashlib
import json
import shutil
import ssl
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import certifi
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from fdash import settings

USER_AGENT = "fdash/0.1 (forecast dashboard; local research use)"
RUSSIAN_CA = Path(__file__).parent / "certs" / "russian_trusted_ca.pem"


@dataclass(frozen=True)
class Release:
    release_id: str
    source_id: str
    title: str
    vintage_date: date
    url: str
    filename: str
    extra: dict = field(default_factory=dict, compare=False, hash=False)
    # A large file holding the history of many releases is stored once: the path is relative to
    # data/raw/<source>/ and release.json of every release that was read from it points there.
    shared: str | None = None

    @property
    def release_dir(self) -> Path:
        return settings.RAW_DIR / self.source_id / self.vintage_date.isoformat()

    @property
    def raw_path(self) -> Path:
        if self.shared:
            return settings.RAW_DIR / self.source_id / self.shared
        return self.release_dir / self.filename


@dataclass(frozen=True)
class Observation:
    indicator_id: str
    area_id: str
    target_period: str
    frequency: str
    value: float
    kind: str
    lower: float | None = None
    upper: float | None = None


@dataclass
class Parsed:
    observations: list[Observation]
    data_cutoff: str | None = None


class SourceStructureError(RuntimeError):
    """The raw file does not have the structure the parser expects."""


def quarter_of(day: date) -> str:
    return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}"


def projection_kind(period: str, vintage: date, projected: bool) -> str:
    """Kind of a quarterly value. The source marks what is projected; a projection for a quarter
    before the release quarter (data not yet published) is an estimate, as for annual sources."""
    if not projected:
        return "actual"
    return "forecast" if period >= quarter_of(vintage) else "estimate"


def saved_releases(source_id: str) -> dict[str, Release]:
    """Releases already saved under data/raw/<source>/, by release_id (from their release.json)."""
    result = {}
    for meta_file in sorted((settings.RAW_DIR / source_id).glob("*/release.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        release = Release(
            release_id=meta["release_id"],
            source_id=meta["source_id"],
            title=meta["title"],
            vintage_date=date.fromisoformat(meta["vintage_date"]),
            url=meta["url"],
            filename=meta["filename"],
            extra=meta.get("extra", {}),
            shared=meta.get("shared"),
        )
        if release.raw_path.exists():
            result[release.release_id] = release
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def russian_trust() -> ssl.SSLContext:
    """The usual trust store plus the Russian Trusted Root CA: rosstat.gov.ru is signed by it."""
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=RUSSIAN_CA)
    return context


def client(verify: ssl.SSLContext | bool = True) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(180, connect=30),
        follow_redirects=True,
        verify=verify,
    )


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
def http_get(url: str, verify: ssl.SSLContext | bool = True, **kwargs) -> httpx.Response:
    with client(verify) as http:
        response = http.get(url, **kwargs)
        if response.status_code >= 500:
            response.raise_for_status()
        return response


def download(url: str, destination: Path, **kwargs) -> Path:
    response = http_get(url, **kwargs)
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.write_bytes(response.content)
    tmp.replace(destination)
    return destination


def download_temp(url: str, name: str, **kwargs) -> Path:
    """Download into a fresh temporary directory: files that must be read to list releases."""
    return download(url, Path(tempfile.mkdtemp(prefix="fdash_")) / name, **kwargs)


def copy_into(source: Path, release: Release) -> Path:
    release.raw_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, release.raw_path)
    return release.raw_path


class Connector(ABC):
    source_id: str
    name: str
    organization: str
    url: str
    license: str
    access: str
    role: str = "forecast"
    # Sources without an archive of past versions: keep a new release only when the raw file changed.
    dedupe: bool = False

    @abstractmethod
    def list_releases(self) -> list[Release]:
        """Releases available at the source, oldest first."""

    def fetch(self, release: Release) -> Path:
        """Save the raw file of a release under data/raw/ and return its path."""
        return download(release.url, release.raw_path)

    @abstractmethod
    def parse(self, raw: Path, release: Release) -> Parsed:
        """Turn a raw file into observations of the common schema."""
