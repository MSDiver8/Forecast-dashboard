"""Fetch releases, keep raw files with metadata, load observations into DuckDB."""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb

from fdash import settings
from fdash.core import catalog as catalog_mod
from fdash.ingest.base import Connector, Release, sha256
from fdash.ingest.registry import CONNECTORS, get, load_all

log = logging.getLogger(__name__)
META_NAME = "release.json"


@dataclass
class Result:
    source_id: str
    releases_added: int
    rows_added: int
    error: str | None = None


def _meta_path(release: Release) -> Path:
    return release.raw_path.parent / META_NAME


def _write_meta(release: Release) -> None:
    meta = {
        "release_id": release.release_id,
        "source_id": release.source_id,
        "title": release.title,
        "vintage_date": release.vintage_date.isoformat(),
        "url": release.url,
        "filename": release.filename,
        "extra": release.extra,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    _meta_path(release).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _same_as_previous(release: Release) -> bool:
    """True when every raw file of the release equals the files of the latest saved release."""
    previous = [r for r, _ in local_releases(release.source_id) if r.release_id != release.release_id]
    if not previous:
        return False
    old_dir, new_dir = previous[-1].raw_path.parent, release.raw_path.parent
    new_files = sorted(p.name for p in new_dir.iterdir() if p.name != META_NAME)
    old_files = sorted(p.name for p in old_dir.iterdir() if p.name != META_NAME)
    return new_files == old_files and all(sha256(new_dir / n) == sha256(old_dir / n) for n in new_files)


def local_releases(source_id: str) -> list[tuple[Release, datetime]]:
    result = []
    for meta_file in sorted((settings.RAW_DIR / source_id).glob(f"*/{META_NAME}")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        release = Release(
            release_id=meta["release_id"],
            source_id=meta["source_id"],
            title=meta["title"],
            vintage_date=date.fromisoformat(meta["vintage_date"]),
            url=meta["url"],
            filename=meta["filename"],
            extra=meta.get("extra", {}),
        )
        if release.raw_path.exists():
            result.append((release, datetime.fromisoformat(meta["fetched_at"])))
    return sorted(result, key=lambda item: item[0].vintage_date)


def sync_catalog(con: duckdb.DuckDBPyConnection) -> None:
    cat = catalog_mod.load()
    load_all()
    con.execute("DELETE FROM sources")
    for c in CONNECTORS.values():
        con.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?)",
            [c.source_id, c.name, c.organization, c.url, c.license, c.access, c.role],
        )
    con.execute("DELETE FROM indicators")
    for i in cat.indicators:
        con.execute(
            "INSERT INTO indicators VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [i.id, i.name, i.unit, i.transform, i.base, ",".join(i.groups), i.description, i.precision],
        )
    con.execute("DELETE FROM areas")
    for a in cat.areas:
        con.execute("INSERT INTO areas VALUES (?, ?, ?)", [a.id, a.name, a.kind])
    con.execute("DELETE FROM source_series")
    for s in cat.series:
        con.execute(
            "INSERT INTO source_series VALUES (?, ?, ?, ?, ?)",
            [s.source, s.code, s.indicator, s.area, s.note],
        )


def load_release(con: duckdb.DuckDBPyConnection, connector: Connector, release: Release, fetched_at) -> int:
    exists = con.execute("SELECT 1 FROM releases WHERE release_id = ?", [release.release_id]).fetchone()
    if exists:
        return 0
    parsed = connector.parse(release.raw_path, release)
    if not parsed.observations:
        raise RuntimeError(f"{release.release_id}: parser returned no observations")
    rows = [
        (
            release.release_id,
            o.indicator_id,
            o.area_id,
            o.target_period,
            o.frequency,
            o.value,
            o.lower,
            o.upper,
            o.kind,
        )
        for o in parsed.observations
    ]
    con.execute("BEGIN")
    con.execute(
        "INSERT INTO releases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            release.release_id,
            release.source_id,
            release.title,
            release.vintage_date,
            parsed.data_cutoff,
            fetched_at,
            str(release.raw_path.relative_to(settings.ROOT)),
            release.url,
            sha256(release.raw_path),
        ],
    )
    con.executemany("INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute("COMMIT")
    return len(rows)


def ingest_source(con: duckdb.DuckDBPyConnection, source_id: str, offline: bool = False) -> Result:
    connector = get(source_id)
    started = datetime.now()
    releases_added = rows_added = 0
    errors: list[str] = []
    if not offline:
        try:
            releases = connector.list_releases()
        except Exception as exc:  # recorded in ingestion_log and reported to the user
            releases = []
            errors.append(f"list_releases: {type(exc).__name__}: {exc}")
            log.exception("list releases %s failed", source_id)
        for release in releases:
            if release.raw_path.exists():
                continue
            try:
                log.info("fetch %s", release.release_id)
                connector.fetch(release)
                if connector.dedupe and _same_as_previous(release):
                    shutil.rmtree(release.raw_path.parent)
                    continue
                _write_meta(release)
            except Exception as exc:
                errors.append(f"{release.release_id}: {type(exc).__name__}: {exc}")
                log.exception("fetch %s failed", release.release_id)
    for release, fetched_at in local_releases(source_id):
        try:
            added = load_release(con, connector, release, fetched_at)
        except Exception as exc:
            with contextlib.suppress(duckdb.Error):
                con.execute("ROLLBACK")
            errors.append(f"{release.release_id}: {type(exc).__name__}: {exc}")
            log.exception("load %s failed", release.release_id)
            continue
        if added:
            releases_added += 1
            rows_added += added
    error = "; ".join(errors) or None
    con.execute(
        "INSERT INTO ingestion_log (source_id, started_at, finished_at, status, releases, rows_added, error) "
        "VALUES (?, ?, now(), ?, ?, ?, ?)",
        [source_id, started, "error" if error else "ok", releases_added, rows_added, error],
    )
    return Result(source_id, releases_added, rows_added, error)
