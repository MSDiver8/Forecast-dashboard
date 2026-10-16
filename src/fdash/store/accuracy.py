"""Accuracy tab: published forecasts and benchmark models against the actuals that became known later.

For every target period an agency is represented by its latest release published inside a window
(a half-year for annual targets, a quarter or a month otherwise). A benchmark model is estimated on the
actuals known at the end of that window, at the frequency the user picks, and its forecast is brought
to the target period: the mean of sub-periods for averages, the December value for Dec/Dec inflation.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from fdash.core import periods
from fdash.core.catalog import Catalog, Featured
from fdash.core.models import benchmarks
from fdash.store import model_runs
from fdash.store.queries import actual_series, pair_series, period_of

# Publication windows, in months from the start of the target period.
WINDOWS = {
    "A": [(-12, -6), (-6, 0), (0, 6), (6, 12)],
    "Q": [(-9, -6), (-6, -3), (-3, 0), (0, 3)],
    "M": [(-3, -2), (-2, -1), (-1, 0), (0, 1)],
}
DEFAULT_WINDOW = {"A": 1, "Q": 2, "M": 2}  # the window right before the target period
MAPE_MIN_ACTUAL = 1.0  # MAPE only when every actual in the sample is at least this, in the indicator's unit
SHORT_UNITS = {"долл. США за баррель": "долл./барр."}
APPROX_MARK = " (дата ≈)"
FINER = {"A": ("Q", "M"), "Q": ("M",), "M": ()}
MONTHS = {"A": 12, "Q": 3, "M": 1}
# Default parameters by the frequency the model is estimated at: last N points, MA order.
WINDOW_DEFAULT = {"A": 10, "Q": 20, "M": 36}
Q_DEFAULT = {"A": 3, "Q": 4, "M": 3}
WINDOW_MODELS = ("rwd", "rwds", "ts")


@dataclass(frozen=True)
class Estimation:
    """Where a model is estimated: frequency, actual series, and how its forecast becomes the target."""

    frequency: str
    indicator: str
    convert: str  # same | mean (average of sub-periods) | december (value of December)


def estimation_options(con, catalog: Catalog, item: Featured, frequency: str) -> list[Estimation]:
    indicator = catalog.indicator(item.indicator)
    options = [Estimation(frequency, item.indicator, "same")]
    if indicator and indicator.averageable and indicator.transform.startswith("avg"):
        for finer in FINER[frequency]:
            series = actual_series(con, catalog, item.indicator, item.area, finer, None)
            if series and series.points:
                options.append(Estimation(finer, item.indicator, "mean"))
    context = item.context
    if (
        indicator
        and indicator.transform == "dec_dec"
        and frequency == "A"
        and context
        and context.frequency == "M"
    ):
        series = actual_series(con, catalog, context.indicator, item.area, "M", None)
        if series and series.points:
            options.append(Estimation("M", context.indicator, "december"))
    return options


def model_params(code: str, params: dict | None, frequency: str) -> dict:
    """Parameters actually used: the window of last points and the MA order get frequency defaults."""
    params = params or {}
    result = {}
    if code in WINDOW_MODELS:
        result["window"] = int(params.get("window") or WINDOW_DEFAULT[frequency])
    if code == "ma":
        result["q"] = int(params.get("q") or Q_DEFAULT[frequency])
    return result


def unavailable(code: str, n: int, frequency: str, params: dict) -> dict | None:
    """Why a model cannot be estimated on n points at this frequency (None when it can)."""
    season = periods.SEASON[frequency]
    if code in ("rws", "rwds") and season == 1:
        return {"reason": "seasonal"}
    need = {
        "rw": 2,
        "rwd": 3,
        "rws": 2 * season,
        "rwds": 2 * season,
        "ts": max(4, 2 * season if season > 1 else 4),
        "ma": params.get("q", 3) + 2,
        "arima": benchmarks.MIN_ARIMA,
    }[code]
    return {"reason": "short", "need": need, "have": n} if n < need else None


class Estimator:
    """Benchmark forecasts of one target period as known on a date, from one actual series."""

    def __init__(self, con, catalog: Catalog, item: Featured, estimation: Estimation):
        self.con, self.item, self.estimation = con, item, estimation
        series = actual_series(con, catalog, estimation.indicator, item.area, estimation.frequency, None)
        self.points = [(p.period, p.value) for p in series.points] if series else []
        self.release = series.release_id if series else ""

    def known(self, asof: date) -> list[tuple[str, float]]:
        last = periods.shift(period_of(asof, self.estimation.frequency), -1)
        return [p for p in self.points if p[0] <= last]

    def parts(self, target: str) -> list[str]:
        """Periods at the estimation frequency that make the target value."""
        frequency, convert = self.estimation.frequency, self.estimation.convert
        if convert == "same":
            return [target]
        if convert == "december":
            return [f"{target[:4]}-12"]
        start = period_of(_period_start(target), frequency)
        count = MONTHS[periods.frequency_of(target)] // MONTHS[frequency]
        return [periods.shift(start, k) for k in range(count)]

    def forecast(self, code: str, params: dict, target: str, asof: date) -> float | None:
        train = self.known(asof)
        if not train:
            return None
        parts = self.parts(target)
        horizon = _ordinal(parts[-1]) - _ordinal(train[-1][0])
        values = dict(train)
        if horizon >= 1:
            try:
                run = model_runs.run(
                    self.con,
                    code,
                    params,
                    self.estimation.indicator,
                    self.item.area,
                    self.estimation.frequency,
                    train,
                    self.release,
                    horizon,
                )
            except benchmarks.ModelUnavailable:
                return None
            values = {**run.values(), **values}
        found = [values.get(p) for p in parts]
        if any(v is None for v in found):
            return None
        return sum(found) / len(found) if self.estimation.convert == "mean" else found[-1]


def evaluation(
    con,
    catalog: Catalog,
    item: Featured,
    frequency: str,
    window: int | None = None,
    fact_mode: str = "latest",
    sources: list[str] | None = None,
    models: list[tuple[str, dict]] = (),
    model_frequency: str | None = None,
    period: str | None = None,
    today: date | None = None,
    evolution: bool = False,
    metrics_from: str | None = None,
    metrics_to: str | None = None,
    metrics_include: tuple[str, ...] = (),
) -> dict:
    """Everything the accuracy tab shows for one indicator, frequency and set of choices.

    The path of forecasts for one period by publication date is computed only on request: models
    are estimated there on every date and that is the slow part.
    """
    today = today or date.today()
    windows = WINDOWS[frequency]
    window = DEFAULT_WINDOW[frequency] if window is None else window
    if not 0 <= window < len(windows):
        raise ValueError(f"Unknown window {window} for frequency {frequency}")
    indicator = catalog.indicator(item.indicator)
    unit = indicator.unit if indicator else ""
    percent = unit.startswith("%")
    short_unit = SHORT_UNITS.get(unit, unit)
    data = pair_series(con, catalog, item.indicator, item.area, frequency)
    actual = data["actual"]
    fact = _fact_values(actual["releases"], fact_mode) if actual else {}
    last_fact = max(fact) if fact else None

    chosen = set(sources) if sources is not None else None
    source_list, forecasts, everything = [], {}, set()
    for source in data["sources"]:
        by_period = defaultdict(list)
        for release in source["releases"]:
            stamp = {
                "vintage_date": release["vintage_date"],
                "title": release["title"].replace(APPROX_MARK, ""),
                "approx": APPROX_MARK in release["title"],
            }
            for p in release["points"]:
                if p["kind"] == "forecast":
                    by_period[p["period"]].append({**stamp, "value": p["value"]})
        if not by_period:
            continue
        everything |= set(by_period)
        selected = chosen is None or source["source_id"] in chosen
        if selected:
            forecasts[source["source_id"]] = by_period
        vintages = [r["vintage_date"] for r in source["releases"]]
        source_list.append(
            {
                **{k: source[k] for k in ("source_id", "short", "name", "organization", "color")},
                "description": source.get("description"),
                "caveat": source.get("caveat"),
                "releases": len(vintages),
                "first_vintage": vintages[0],
                "last_vintage": vintages[-1],
                "selected": selected,
            }
        )

    options = estimation_options(con, catalog, item, frequency) if actual else []
    estimation = next((o for o in options if o.frequency == model_frequency), options[0] if options else None)
    estimator = Estimator(con, catalog, item, estimation) if estimation else None
    requested = {code: params for code, params in models if code in benchmarks.MODELS}
    choices = (
        [(code, model_params(code, requested[code], estimation.frequency)) for code in requested]
        if estimation
        else []
    )
    model_list = []
    for code, spec in benchmarks.MODELS.items():
        params = model_params(code, requested.get(code), estimation.frequency) if estimation else {}
        n = len(estimator.points) if estimator else 0
        model_list.append(
            {
                "code": code,
                "name": spec.name,
                "description": spec.description,
                "selected": code in requested,
                "params": params,
                "unavailable": unavailable(code, n, estimation.frequency, params)
                if estimation
                else {"reason": "fact"},
            }
        )

    rows = []
    for target in sorted(everything):
        if target not in fact and (last_fact is None or target <= last_fact):
            continue  # a past period without an actual cannot be checked
        start, end = _window_dates(target, windows[window])
        value = fact.get(target)
        picks = {}
        for source_id, by_period in forecasts.items():
            inside = [f for f in by_period.get(target, []) if start <= f["vintage_date"] <= end]
            if inside:
                pick = inside[-1]
                picks[source_id] = {**pick, "error": None if value is None else pick["value"] - value}
        if forecasts and not picks or not forecasts and value is None:
            continue
        asof = min(end, today)
        model_values, rw = {}, None
        if estimator:
            for code, params in choices:
                v = estimator.forecast(code, params, target, asof)
                if v is not None:
                    model_values[code] = {"value": v, "error": None if value is None else v - value}
            rw = estimator.forecast("rw", {}, target, asof)
        rows.append(
            {
                "period": target,
                "window_start": start,
                "window_end": end,
                "fact": value,
                "picks": picks,
                "models": model_values,
                "rw_error": None if value is None or rw is None else rw - value,
            }
        )

    checked = [p for p in sorted(everything) if p in fact]
    pending = [p for p in sorted(everything) if last_fact is not None and p > last_fact][:1]
    period_list = [
        {
            "period": p,
            "start": _period_start(p),
            "end": _period_end(p),
            "fact": fact.get(p),
            "windows": [dict(zip(("start", "end"), _window_dates(p, w), strict=True)) for w in windows],
        }
        for p in checked + pending
    ]
    with_rows = [r["period"] for r in rows if r["fact"] is not None]
    selected_period = (
        period if period in fact else (with_rows[-1] if with_rows else (checked[-1] if checked else None))
    )

    return {
        "featured": item.id,
        "frequency": frequency,
        "unit": unit,
        "value_unit": "%" if percent else short_unit,
        "error_unit": "п.п." if percent else short_unit,
        "transform": indicator.transform if indicator else "",
        "fact_shape": "point" if indicator and indicator.transform == "dec_dec" else "segment",
        "actual": _actual_meta(actual),
        "fact_mode": fact_mode,
        "window": window,
        "window_count": len(windows),
        "sources": source_list,
        "models": model_list,
        "estimation": {
            "frequency": estimation.frequency if estimation else None,
            "convert": estimation.convert if estimation else None,
            "options": [{"frequency": o.frequency, "convert": o.convert} for o in options],
        },
        "periods": period_list,
        "context": _context(con, catalog, item),
        "rows": rows,
        "metrics": _metrics(
            rows,
            list(forecasts),
            [code for code, _ in choices],
            metrics_from,
            metrics_to,
            tuple(metrics_include),
        ),
        "evolution": _evolution(
            selected_period, period_list, forecasts, estimator, choices, windows[window], today
        )
        if evolution and selected_period
        else None,
    }


def _context(con, catalog: Catalog, item: Featured) -> dict | None:
    if not item.context:
        return None
    series = actual_series(con, catalog, item.context.indicator, item.area, item.context.frequency, None)
    if not series or not series.points:
        return None
    return {
        "label": item.context.label,
        "frequency": item.context.frequency,
        "points": [{"period": p.period, "date": _mid(p.period), "value": p.value} for p in series.points],
    }


def _evolution(target, period_list, forecasts, estimator, choices, offsets, today) -> dict:
    """How forecasts for one target period moved, by publication date, with models known on each date."""
    entry = next(p for p in period_list if p["period"] == target)
    tracks = {sid: by_period[target] for sid, by_period in forecasts.items() if target in by_period}
    dates = [f["vintage_date"] for track in tracks.values() for f in track]
    first_window = _window_dates(target, WINDOWS[periods.frequency_of(target)][0])[0]
    begin = min([first_window, *dates])
    finish = min(entry["end"], today)
    paths = {}
    if estimator:
        frequency = estimator.estimation.frequency
        for code, params in choices:
            # ARIMA takes about a second on a long monthly series: on this chart it is re-estimated
            # at the start of every quarter, the other models at every new observation.
            stride = 3 if code == "arima" and frequency == "M" else 1
            step = period_of(begin, frequency)
            while _period_start(step) <= finish:
                value = estimator.forecast(code, params, target, _period_start(step))
                if value is not None:
                    paths.setdefault(code, []).append({"date": _period_start(step), "value": value})
                step = periods.shift(step, stride)
    window_start, window_end = _window_dates(target, offsets)
    return {
        "period": target,
        "start": entry["start"],
        "end": entry["end"],
        "fact": entry["fact"],
        "window": {"start": window_start, "end": window_end},
        "tracks": tracks,
        "models": paths,
    }


def _metrics(
    rows: list[dict],
    source_ids: list[str],
    model_codes: list[str],
    start: str | None = None,
    end: str | None = None,
    include: tuple[str, ...] = (),
) -> dict:
    """Error statistics over a range of target periods.

    Series with a value in every period of the range are compared on the same periods. A series
    covering only part of the range is left out unless it is asked for in `include`
    ("source:<id>" or "model:<code>"); then it is summarised over its own periods and marked,
    because its averages are not comparable with the others. By default the range starts at the
    first period that two of the chosen agencies cover (one, if only one is chosen) and ends at
    the last period with an actual.
    """
    keys = [("source", s) for s in source_ids] + [("model", m) for m in model_codes]

    def error(row, kind, key):
        cell = (row["picks"] if kind == "source" else row["models"]).get(key)
        return None if cell is None else cell["error"]

    checked = [r for r in rows if r["fact"] is not None]
    available = [r["period"] for r in checked]
    if not checked:
        return {
            "start": None,
            "end": None,
            "available": [],
            "periods": [],
            "contiguous": False,
            "mape_min_actual": MAPE_MIN_ACTUAL,
            "rows": [],
            "partial": [],
            "empty": [],
        }
    if start not in available:
        need = min(2, len(source_ids)) or 1
        covered = [
            r["period"] for r in checked if sum(error(r, "source", s) is not None for s in source_ids) >= need
        ]
        start = covered[0] if covered else available[0]
    end = end if end in available else available[-1]
    start, end = min(start, end), max(start, end)
    in_range = [r for r in checked if start <= r["period"] <= end]
    coverage = {k: [r for r in in_range if error(r, *k) is not None] for k in keys}
    full = [k for k in keys if len(coverage[k]) == len(in_range)]
    partial = [k for k in keys if 0 < len(coverage[k]) < len(in_range)]
    wanted = {tuple(x.split(":", 1)) for x in include}
    stats = []
    for kind, key in full + [k for k in partial if k in wanted]:
        own = coverage[(kind, key)]
        stats.append(
            {
                "kind": kind,
                "key": key,
                "partial": (kind, key) in partial,
                "missing": [r["period"] for r in in_range if error(r, kind, key) is None],
                **_stats([(error(r, kind, key), r["fact"], r["rw_error"]) for r in own]),
            }
        )
    shown = [r["period"] for r in in_range]
    return {
        "start": start,
        "end": end,
        "available": available,
        "periods": shown,
        "contiguous": all(periods.shift(a, 1) == b for a, b in pairwise(shown)),
        "mape_min_actual": MAPE_MIN_ACTUAL,
        "rows": stats,
        "partial": [
            {
                "kind": k[0],
                "key": k[1],
                "n": len(coverage[k]),
                "total": len(in_range),
                "missing": [r["period"] for r in in_range if error(r, *k) is None],
                "included": k in wanted,
            }
            for k in partial
        ],
        "empty": [{"kind": k[0], "key": k[1]} for k in keys if not coverage[k]],
    }


def _stats(items: list[tuple[float, float, float | None]]) -> dict:
    """MAE, RMSE, ME, MAPE and MAE relative to RW over (error, actual, RW error) triples."""
    errors = [e for e, _, _ in items]
    n = len(errors)
    mae = sum(abs(e) for e in errors) / n
    mape = None
    if all(f >= MAPE_MIN_ACTUAL for _, f, _ in items):
        mape = 100 * sum(abs(e) / f for e, f, _ in items) / n
    rw = [r for _, _, r in items if r is not None]
    mae_rw = sum(abs(r) for r in rw) / len(rw) if len(rw) == n else None
    return {
        "n": n,
        "mae": mae,
        "rmse": math.sqrt(sum(e * e for e in errors) / n),
        "me": sum(errors) / n,
        "mape": mape,
        "ratio_rw": mae / mae_rw if mae_rw else None,
        "errors": errors,
    }


def _fact_values(releases: list[dict], mode: str) -> dict[str, float]:
    """Latest revised actuals, or the first estimate of each period found in the archive."""
    if mode == "first":
        values: dict[str, float] = {}
        for release in releases:
            for p in release["points"]:
                values.setdefault(p["period"], p["value"])
        return values
    return {p["period"]: p["value"] for p in releases[-1]["points"]}


def _actual_meta(actual: dict | None) -> dict | None:
    if not actual:
        return None
    vintages = [r["vintage_date"] for r in actual["releases"]]
    return {
        **{k: actual[k] for k in ("source_id", "short", "name", "organization")},
        "versions": len(vintages),
        "first_vintage": vintages[0],
        "last_vintage": vintages[-1],
    }


def _ordinal(period: str) -> int:
    if m := periods.MONTHLY.match(period):
        return int(m.group(1)) * 12 + int(m.group(2)) - 1
    if m := periods.QUARTERLY.match(period):
        return int(m.group(1)) * 4 + int(m.group(2)) - 1
    return int(period)


def _period_start(period: str) -> date:
    if m := periods.MONTHLY.match(period):
        return date(int(m.group(1)), int(m.group(2)), 1)
    if m := periods.QUARTERLY.match(period):
        return date(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)
    return date(int(period), 1, 1)


def _period_end(period: str) -> date:
    return _add_months(_period_start(period), MONTHS[periods.frequency_of(period)]) - timedelta(days=1)


def _mid(period: str) -> date:
    """Where a period is drawn on a time axis: the 15th of its middle month."""
    start = _period_start(period)
    return _add_months(start, (MONTHS[periods.frequency_of(period)] - 1) // 2) + timedelta(days=14)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _window_dates(period: str, offsets: tuple[int, int]) -> tuple[date, date]:
    """First and last day of a publication window given in months from the period start."""
    start = _period_start(period)
    return _add_months(start, offsets[0]), _add_months(start, offsets[1]) - timedelta(days=1)
