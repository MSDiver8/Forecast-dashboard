"""Benchmark model runs on an actual series, cached in benchmark_runs and benchmark_forecasts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from fdash.core import periods
from fdash.core.models import benchmarks


@dataclass
class Run:
    run_id: str
    origin: str
    # period, value, lower80, upper80, lower95, upper95
    rows: list[tuple[str, float, float, float, float, float]]
    info: dict

    def values(self) -> dict[str, float]:
        return {row[0]: row[1] for row in self.rows}


def run(
    con,
    model: str,
    params: dict,
    indicator_id: str,
    area_id: str,
    frequency: str,
    points: list[tuple[str, float]],
    actual_release: str,
    horizon: int,
) -> Run:
    """Forecast `horizon` periods after the last point. Raises benchmarks.ModelUnavailable."""
    origin = points[-1][0]
    key = json.dumps(
        [model, params, indicator_id, area_id, frequency, origin, actual_release, horizon],
        sort_keys=True,
        default=str,
    )
    run_id = hashlib.sha1(key.encode()).hexdigest()[:16]
    cached = con.execute(
        "SELECT target_period, value, lower80, upper80, lower95, upper95 FROM benchmark_forecasts "
        "WHERE run_id = ? ORDER BY target_period",
        [run_id],
    ).fetchall()
    if cached:
        stored = con.execute("SELECT params FROM benchmark_runs WHERE run_id = ?", [run_id]).fetchone()
        info = json.loads(stored[0]).get("info", {}) if stored else {}
        return Run(run_id, origin, [tuple(row) for row in cached], info)
    y = np.array([v for _, v in points])
    future = [periods.shift(origin, k) for k in range(1, horizon + 1)]
    seasons = np.array(
        [periods.season_index(p) for p, _ in points] + [periods.season_index(p) for p in future]
    )
    fc = benchmarks.run(model, y, horizon, periods.SEASON[frequency], params, seasons)
    con.execute(
        "INSERT OR IGNORE INTO benchmark_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            run_id,
            model,
            json.dumps({**params, "horizon": horizon, "info": fc.info}, default=str),
            indicator_id,
            area_id,
            frequency,
            origin,
            actual_release,
            datetime.now(),
        ],
    )
    rows = [
        (
            future[k],
            float(fc.mean[k]),
            float(fc.lo80[k]),
            float(fc.hi80[k]),
            float(fc.lo95[k]),
            float(fc.hi95[k]),
        )
        for k in range(horizon)
    ]
    con.executemany(
        "INSERT OR IGNORE INTO benchmark_forecasts VALUES (?, ?, ?, ?, ?, ?, ?)", [(run_id, *r) for r in rows]
    )
    return Run(run_id, origin, rows, fc.info)
