"""Benchmark models of SPEC section 6: RW, RWD, RWS, RWDS, TS, MA, ARIMA.

Every model takes the training series in its own frequency and returns the point
forecast with 80% and 95% intervals for h steps ahead.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import statsmodels.api as sm

Z80, Z95 = 1.2815515655446004, 1.959963984540054
MIN_ARIMA = 30


class ModelUnavailable(ValueError):
    """The model cannot be fitted on this series; the message explains why."""


@dataclass
class Forecast:
    mean: np.ndarray
    lo80: np.ndarray
    hi80: np.ndarray
    lo95: np.ndarray
    hi95: np.ndarray
    info: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    code: str
    name: str
    description: str
    params: dict


MODELS: dict[str, ModelSpec] = {
    spec.code: spec
    for spec in [
        ModelSpec("rw", "RW", "Случайное блуждание: прогноз равен последнему наблюдению", {}),
        ModelSpec(
            "rwd",
            "RWD",
            "Случайное блуждание с дрейфом: последнее значение плюс h·средний прирост",
            {"window": None},
        ),
        ModelSpec("rws", "RWS", "Сезонное случайное блуждание: значение того же сезона последнего года", {}),
        ModelSpec(
            "rwds",
            "RWDS",
            "Сезонное блуждание с дрейфом: тот же сезон плюс средний годовой прирост",
            {"window": None},
        ),
        ModelSpec("ts", "TS", "Линейный тренд по МНК, для сезонных рядов — с сезонными дамми", {"degree": 1}),
        ModelSpec("ma", "MA", "Скользящее среднее последних q наблюдений", {"q": 3}),
        ModelSpec("arima", "ARIMA", "ARIMA с автоподбором порядка по AICc", {"order": None}),
    ]
}


def _band(mean: np.ndarray, sigma: float, scale: np.ndarray, info: dict | None = None) -> Forecast:
    spread = sigma * scale
    return Forecast(
        mean, mean - Z80 * spread, mean + Z80 * spread, mean - Z95 * spread, mean + Z95 * spread, info or {}
    )


def _sd(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _window(values: np.ndarray, window: int | None) -> np.ndarray:
    return values[-window:] if window else values


def rw(y: np.ndarray, h: int) -> Forecast:
    if len(y) < 2:
        raise ModelUnavailable("RW: нужно не менее 2 наблюдений")
    steps = np.arange(1, h + 1)
    return _band(np.full(h, y[-1]), _sd(np.diff(y)), np.sqrt(steps))


def rwd(y: np.ndarray, h: int, window: int | None = None) -> Forecast:
    if len(y) < 3:
        raise ModelUnavailable("RWD: нужно не менее 3 наблюдений")
    changes = _window(np.diff(y), window)
    drift = float(np.mean(changes))
    steps = np.arange(1, h + 1)
    return _band(y[-1] + drift * steps, _sd(changes - drift), np.sqrt(steps), {"drift": drift})


def _seasonal_path(y: np.ndarray, h: int, m: int, drift: float) -> tuple[np.ndarray, np.ndarray]:
    steps = np.arange(1, h + 1)
    years_ahead = np.ceil(steps / m).astype(int)
    base = np.array([y[len(y) - m + (s - 1) % m] for s in steps])
    return base + drift * years_ahead, np.sqrt(years_ahead)


def rws(y: np.ndarray, h: int, m: int) -> Forecast:
    if m <= 1:
        raise ModelUnavailable("RWS: применяется только к сезонным (месячным, квартальным) рядам")
    if len(y) < 2 * m:
        raise ModelUnavailable(f"RWS: нужно не менее {2 * m} наблюдений")
    mean, scale = _seasonal_path(y, h, m, 0.0)
    return _band(mean, _sd(y[m:] - y[:-m]), scale)


def rwds(y: np.ndarray, h: int, m: int, window: int | None = None) -> Forecast:
    if m <= 1:
        raise ModelUnavailable("RWDS: применяется только к сезонным (месячным, квартальным) рядам")
    if len(y) < 2 * m:
        raise ModelUnavailable(f"RWDS: нужно не менее {2 * m} наблюдений")
    yearly = _window(y[m:] - y[:-m], window)
    drift = float(np.mean(yearly))
    mean, scale = _seasonal_path(y, h, m, drift)
    return _band(mean, _sd(yearly - drift), scale, {"annual_drift": drift})


def ts(y: np.ndarray, h: int, m: int, seasons: np.ndarray | None = None, degree: int = 1) -> Forecast:
    """Trend by OLS; `seasons` are calendar season indices of y followed by those of the horizon."""
    n = len(y)
    if n < max(4, (2 * m if m > 1 else 0)):
        raise ModelUnavailable(f"TS: нужно не менее {max(4, 2 * m if m > 1 else 4)} наблюдений")
    t = np.arange(n + h, dtype=float)
    columns = [t**p for p in range(degree + 1)]
    if m > 1:
        idx = seasons if seasons is not None else t.astype(int) % m
        columns += [(idx == s).astype(float) for s in range(1, m)]
    x = np.column_stack(columns)
    fit = sm.OLS(y, x[:n]).fit()
    out = fit.get_prediction(x[n:])
    f80 = out.summary_frame(alpha=0.20)
    f95 = out.summary_frame(alpha=0.05)
    return Forecast(
        f95["mean"].to_numpy(),
        f80["obs_ci_lower"].to_numpy(),
        f80["obs_ci_upper"].to_numpy(),
        f95["obs_ci_lower"].to_numpy(),
        f95["obs_ci_upper"].to_numpy(),
        {"degree": degree},
    )


def ma(y: np.ndarray, h: int, q: int = 3) -> Forecast:
    if q < 1:
        raise ModelUnavailable("MA: q должно быть не меньше 1")
    if len(y) < q + 2:
        raise ModelUnavailable(f"MA: нужно не менее {q + 2} наблюдений")
    level = float(np.mean(y[-q:]))
    # One-step errors of the same rule inside the sample give the interval width.
    errors = np.array([y[t] - np.mean(y[t - q : t]) for t in range(q, len(y))])
    steps = np.arange(1, h + 1)
    return _band(np.full(h, level), _sd(errors), np.sqrt(steps), {"q": q})


def arima(
    y: np.ndarray, h: int, m: int, order: tuple | None = None, seasonal_order: tuple | None = None
) -> Forecast:
    if len(y) < MIN_ARIMA:
        raise ModelUnavailable(f"ARIMA: нужно не менее {MIN_ARIMA} наблюдений")
    from statsforecast.models import ARIMA as SfArima
    from statsforecast.models import AutoARIMA

    season = m if m > 1 else 1
    if order:
        model = SfArima(
            order=tuple(order), seasonal_order=tuple(seasonal_order or (0, 0, 0)), season_length=season
        )
    else:
        model = AutoARIMA(season_length=season, ic="aicc")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit(y.astype(float))
        out = fitted.predict(h=h, level=[80, 95])
    info = {}
    arma = getattr(fitted, "model_", {}).get("arma") if hasattr(fitted, "model_") else None
    if arma is not None:
        p, q, sp, sq, period, d, sd = (int(v) for v in arma)
        info["order"] = [p, d, q]
        info["seasonal_order"] = [sp, sd, sq, period]
    return Forecast(out["mean"], out["lo-80"], out["hi-80"], out["lo-95"], out["hi-95"], info)


def run(
    code: str, y: np.ndarray, h: int, m: int, params: dict | None = None, seasons: np.ndarray | None = None
) -> Forecast:
    params = {k: v for k, v in (params or {}).items() if v is not None}
    y = np.asarray(y, dtype=float)
    if h < 1:
        raise ModelUnavailable("Горизонт должен быть не меньше 1")
    match code:
        case "rw":
            return rw(y, h)
        case "rwd":
            return rwd(y, h, params.get("window"))
        case "rws":
            return rws(y, h, m)
        case "rwds":
            return rwds(y, h, m, params.get("window"))
        case "ts":
            return ts(y, h, m, seasons, int(params.get("degree", 1)))
        case "ma":
            return ma(y, h, int(params.get("q", 3)))
        case "arima":
            return arima(y, h, m, params.get("order"), params.get("seasonal_order"))
    raise ModelUnavailable(f"Неизвестная модель: {code}")
