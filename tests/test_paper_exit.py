from __future__ import annotations

import numpy as np
import pandas as pd

from agressivo.backtest.costs import CostParams
from agressivo.backtest.engine import BacktestParams
from agressivo.paper.state import PaperState
from agressivo.paper.step import maybe_exit_managed_position


def test_managed_exit_hits_stop() -> None:
    rng = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
    base = np.full(200, 100.0)
    base[-5:] = 70.0
    df = pd.DataFrame(
        {
            "open": base,
            "high": base + 1,
            "low": base - 2,
            "close": base,
            "volume": 1e3,
        },
        index=rng,
    )
    entry_ts = rng[150]
    st = PaperState(
        cash=0.0,
        qty=1.0,
        avg_entry=100.0,
        entry_timestamp_iso=entry_ts.isoformat(),
        trail_peak=101.0,
        hard_stop=95.0,
        version=2,
    )
    cx = CostParams(slippage_atr_fraction=0.0)
    bp = BacktestParams(take_profit_r_multiple=None)
    st2, ev = maybe_exit_managed_position(st, df, params=bp, costs=cx)
    assert st2.qty == 0.0
    assert any("stop" in e.detail for e in ev if e.kind == "sell")


def test_legacy_position_skips_auto() -> None:
    rng = pd.date_range("2024-05-01", periods=200, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100.0},
        index=rng,
    )
    st = PaperState(cash=0.0, qty=0.5, avg_entry=1.0, version=1)
    st2, ev = maybe_exit_managed_position(
        st, df, params=BacktestParams(), costs=CostParams(slippage_atr_fraction=0.0)
    )
    assert st2 is st
    assert any(e.kind == "note" for e in ev)
