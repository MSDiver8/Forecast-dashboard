import numpy as np
import pytest
from statsforecast.models import Naive, RandomWalkWithDrift, SeasonalNaive

from fdash.core.models import benchmarks


@pytest.fixture
def monthly() -> np.ndarray:
    rng = np.random.default_rng(7)
    t = np.arange(72)
    return 50 + 0.3 * t + 5 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1, 72)


def test_rw_matches_statsforecast(monthly):
    ours = benchmarks.run("rw", monthly, 6, 12)
    ref = Naive().forecast(monthly, h=6, level=[80, 95])
    np.testing.assert_allclose(ours.mean, ref["mean"])


def test_rwd_matches_statsforecast(monthly):
    ours = benchmarks.run("rwd", monthly, 6, 12)
    ref = RandomWalkWithDrift().forecast(monthly, h=6, level=[80, 95])
    np.testing.assert_allclose(ours.mean, ref["mean"])


def test_rws_matches_statsforecast(monthly):
    ours = benchmarks.run("rws", monthly, 18, 12)
    ref = SeasonalNaive(season_length=12).forecast(monthly, h=18, level=[80, 95])
    np.testing.assert_allclose(ours.mean, ref["mean"])


def test_rwds_adds_mean_annual_change(monthly):
    ours = benchmarks.run("rwds", monthly, 13, 12)
    drift = np.mean(monthly[12:] - monthly[:-12])
    assert ours.mean[0] == pytest.approx(monthly[-12] + drift)
    assert ours.mean[12] == pytest.approx(monthly[-12] + 2 * drift)


def test_ma_is_mean_of_last_q(monthly):
    ours = benchmarks.run("ma", monthly, 4, 12, {"q": 5})
    assert np.allclose(ours.mean, monthly[-5:].mean())


def test_ts_recovers_linear_trend():
    y = 2.0 + 0.5 * np.arange(20)
    out = benchmarks.run("ts", y, 3, 1)
    np.testing.assert_allclose(out.mean, 2.0 + 0.5 * np.arange(20, 23), atol=1e-9)


def test_intervals_are_ordered(monthly):
    for code in ["rw", "rwd", "rws", "rwds", "ts", "ma", "arima"]:
        out = benchmarks.run(code, monthly, 6, 12)
        assert np.all(out.lo95 <= out.lo80) and np.all(out.lo80 <= out.mean)
        assert np.all(out.mean <= out.hi80) and np.all(out.hi80 <= out.hi95)


def test_refusals_explain_why():
    with pytest.raises(benchmarks.ModelUnavailable, match="сезонным"):
        benchmarks.run("rws", np.arange(10.0), 2, 1)
    with pytest.raises(benchmarks.ModelUnavailable, match="30"):
        benchmarks.run("arima", np.arange(10.0), 2, 1)
