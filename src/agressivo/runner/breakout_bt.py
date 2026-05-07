from __future__ import annotations

from typing import Any

import pandas as pd

from agressivo.backtest.costs import CostParams
from agressivo.backtest.engine import BacktestParams, EquityCurve, run_long_backtest
from agressivo.satellite.policy import series_satellite_entry_blocked
from agressivo.satellite.schema import SatelliteCatalogFile
from agressivo.strategy.core_breakout import breakout_signals
from agressivo.strategy.sniper import score_signals


def breakout_run(
    df: pd.DataFrame,
    *,
    sniper_filter: bool = False,
    bp: BacktestParams | None = None,
    cx: CostParams | None = None,
    satellite: SatelliteCatalogFile | None = None,
    trend_ma: int | None = None,
    require_above_trend: bool | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series, EquityCurve]:
    """ATR + sinais breakout + opcional burst volume + veto satélite em novas entradas."""

    bp = bp or BacktestParams()
    cx = cx or CostParams()

    kw: dict[str, Any] = {}
    if trend_ma is not None:
        kw["trend_ma"] = int(trend_ma)
    if require_above_trend is not None:
        kw["require_above_trend"] = bool(require_above_trend)

    atr_s, _comp, base = breakout_signals(df, **kw)

    signals = score_signals(df, base) if sniper_filter else base

    blocked = series_satellite_entry_blocked(df.index, satellite)

    signals = signals.fillna(False) & (~blocked.fillna(False))

    curve = run_long_backtest(df, signals, atr_s, params=bp, costs=cx)

    return atr_s, base, signals, curve
