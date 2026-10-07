"""DuckDB connection and SQL migrations."""

from importlib import resources
from pathlib import Path

import duckdb

from fdash import settings


def connect(path: Path | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = path or settings.DB_PATH
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        migrate(con)
    return con


def migrate(con: duckdb.DuckDBPyConnection) -> list[str]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR PRIMARY KEY, applied_at TIMESTAMP)"
    )
    applied = {row[0] for row in con.execute("SELECT version FROM schema_migrations").fetchall()}
    files = sorted(
        (f for f in resources.files("fdash.store.migrations").iterdir() if f.name.endswith(".sql")),
        key=lambda f: f.name,
    )
    done = []
    for file in files:
        version = file.name.removesuffix(".sql")
        if version in applied:
            continue
        con.execute("BEGIN")
        con.execute(file.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_migrations VALUES (?, now())", [version])
        con.execute("COMMIT")
        done.append(version)
    return done
