import numpy as np
import pandas as pd

from agressivo.backtest.costs import CostParams
from agressivo.backtest.engine import BacktestParams, run_long_backtest


def _trend_df(n: int = 260) -> pd.DataFrame:
    ix = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    t = np.linspace(1, 3, n)
    close = pd.Series(
        np.cumsum(np.random.RandomState(0).normal(loc=0.02, scale=0.5, size=n)) + 100 * t,
        index=ix,
    )
    high = close.to_numpy(dtype=float) + np.abs(np.random.RandomState(1).normal(0, 0.8, size=n))
    low = close.to_numpy(dtype=float) - np.abs(np.random.RandomState(2).normal(0, 0.8, size=n))

    df = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": high,
            "low": low,
            "close": close,
            "volume": 1e6 + np.linspace(0, 5e5, n),
        },
        index=ix,
    )
    return df


def test_engine_runs_flat_signal() -> None:
    df = _trend_df(400)
    sig = pd.Series(False, index=df.index)

    atr = (df["high"] - df["low"]).rolling(14).mean()
    curve = run_long_backtest(df, sig, atr, params=BacktestParams(), costs=CostParams())
    assert len(curve.trades) == 0

    np.testing.assert_allclose(curve.equity, 10_000.0)


def test_engine_with_constant_signal_handles() -> None:
    df = _trend_df(400)
    sig = pd.Series(True, index=df.index)

    atr = (df["high"] - df["low"]).rolling(14).mean()
    curve = run_long_backtest(df, sig, atr, params=BacktestParams(), costs=CostParams())
    assert len(curve.equity) == len(df)
    assert np.isfinite(curve.equity[-1])
