import pandas as pd

from agressivo.data.quality import assess_ohlcv_quality


def test_quality_ok_flat() -> None:
    ix = pd.date_range("2024-01-01", periods=50, freq="h", tz="UTC")
    df = pd.DataFrame(index=ix)
    df["open"] = 1
    df["high"] = 2
    df["low"] = 1
    df["close"] = 1
    df["volume"] = 100.0

    q = assess_ohlcv_quality(df, expected_freq="1h")
    assert q.ok


def test_quality_detects_na() -> None:
    ix = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    df = pd.DataFrame(index=ix)
    for c in ["open", "high", "low", "close"]:
        df[c] = 1.0
    df["volume"] = 100.0
    df.loc[df.index[2], "close"] = pd.NA

    q = assess_ohlcv_quality(df)
    assert not q.ok
