"""All connectors, keyed by source_id."""

from importlib import import_module

from fdash.ingest.base import Connector

MODULES = [
    "eia_steo",
    "eia_brent_spot",
    "wb_cmo",
    "boe_mpr",
    "ecb_mpd",
    "cbr_survey",
    "imf_weo",
    "cbr_stats",
    "cbr_mtf",
    "ecb_spf",
    "eurostat_hicp",
    "wb_wdi",
]

CONNECTORS: dict[str, Connector] = {}


def register(connector: Connector) -> None:
    CONNECTORS[connector.source_id] = connector


def load_all() -> dict[str, Connector]:
    for module in MODULES:
        import_module(f"fdash.ingest.{module}")
    return CONNECTORS


def get(source_id: str) -> Connector:
    load_all()
    if source_id not in CONNECTORS:
        raise KeyError(f"Unknown source: {source_id}. Known: {', '.join(sorted(CONNECTORS))}")
    return CONNECTORS[source_id]
