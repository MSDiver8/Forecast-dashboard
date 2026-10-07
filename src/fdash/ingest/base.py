"""Common connector contract: list_releases() -> fetch(release) -> parse(raw)."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from fdash import settings

USER_AGENT = "fdash/0.1 (forecast dashboard; local research use)"


@dataclass(frozen=True)
class Release:
    release_id: str
    source_id: str
    title: str
    vintage_date: date
    url: str
    filename: str
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def raw_path(self) -> Path:
        return settings.RAW_DIR / self.source_id / self.vintage_date.isoformat() / self.filename


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=httpx.Timeout(180, connect=30), follow_redirects=True
    )


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
def http_get(url: str, **kwargs) -> httpx.Response:
    with client() as http:
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
