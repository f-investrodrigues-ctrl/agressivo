from __future__ import annotations

import pandas as pd


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range (Wilder-style via EWM)."""

    px = df[["high", "low", "close"]].astype(float)
    prev_close = px["close"].shift(1).fillna(px["close"])
    tr = pd.concat(
        [
            px["high"] - px["low"],
            (px["high"] - prev_close).abs(),
            (px["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    alpha = 1 / window
    return tr.ewm(alpha=alpha, adjust=False).mean()


def compression_ratio(df: pd.DataFrame, atr_series: pd.Series, lookback: int = 48) -> pd.Series:
    """
    Razão amplitude recente média sobre ATR: valores baixos sugerem compressão pré-breakout.

    amplitude_média(window) ≈ média(high-low últimos ``lookback``)
    razão ≈ média(high-low)_lookback / ATR
    """

    hl_range = df["high"] - df["low"]
    denom = atr_series.clip(lower=1e-12)
    return hl_range.rolling(lookback, min_periods=max(2, lookback // 4)).mean() / denom


def breakout_signals(
    df: pd.DataFrame,
    *,
    atr_window: int = 14,
    swing_lookback: int = 20,
    compression_lookback: int = 48,
    compression_max: float = 1.05,
    trend_ma: int = 120,
    require_above_trend: bool = True,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula série de entrada long (compressão + break do swing alto).

    Returns
    -------
    atr_series : pd.Series
    compression_ratio : pd.Series (razão alta = pouco compression)
    signals : pd.Series bool
    """

    atr_s = atr(df, atr_window)
    comp_r = compression_ratio(df, atr_s, compression_lookback)

    hh = df["high"].rolling(swing_lookback, min_periods=5).max().shift(1)
    breakout = df["close"] > hh

    compress_ok = comp_r <= compression_max

    if require_above_trend and trend_ma > 0:
        ma = df["close"].rolling(trend_ma, min_periods=trend_ma).mean()
        trendy = df["close"] > ma
    else:
        trendy = pd.Series(True, index=df.index)

    sig = breakout & compress_ok.fillna(False) & trendy.fillna(False)
    sig = sig & atr_s.notna()

    return atr_s, comp_r, sig
