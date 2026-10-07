"""Project paths and secrets from `.env`."""

import os
from pathlib import Path

ROOT = Path(os.environ.get("FDASH_HOME", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "fdash.duckdb"
CONFIG_PATH = ROOT / "config" / "indicators.yaml"
WEB_DIST = ROOT / "web" / "dist"


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def secret(name: str) -> str | None:
    return os.environ.get(name) or None
