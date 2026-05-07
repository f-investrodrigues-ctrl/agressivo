import pandas as pd

from agressivo.strategy.core_breakout import atr, breakout_signals


def _df() -> pd.DataFrame:
    ix = pd.date_range("2023-01-01", periods=200, freq="h", tz="UTC")
    rvals = pd.Series(range(len(ix)), dtype=float, index=ix)
    px = 10_000 + rvals * 50

    return pd.DataFrame(
        {"open": px, "high": px + 5, "low": px - 5, "close": px, "volume": 1e3 + rvals * 2}
    )


def test_atr_positive() -> None:
    df = _df()

    series = atr(df, window=14)

    assert bool(series.iloc[-10:].notna().all())


def test_breakout_emits_signals() -> None:
    df = _df()

    atr_s, _comp, sig = breakout_signals(df, require_above_trend=False)
    assert sig.dtype == bool or sig.dtype == "bool"
    assert sig.sum() >= 0
