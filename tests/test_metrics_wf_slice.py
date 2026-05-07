from __future__ import annotations

import numpy as np
import pandas as pd

from agressivo.backtest.engine import EquityCurve, Trade
from agressivo.backtest.metrics import summarize_trades, trades_between_bar_ix


def _mk(entry: pd.Timestamp, exit_: pd.Timestamp) -> Trade:

    return Trade(
        entry_ts=entry,
        exit_ts=exit_,
        entry_price=1.0,
        exit_price=2.0,
        qty=1.0,
        pnl=5.0,
        pnl_pct=1.0,
        exit_reason="eos",
    )


def test_trades_between_bar_ix_filters_positions() -> None:

    rng = pd.date_range("2024-06-01", periods=12, freq="D", tz="UTC")

    hull = EquityCurve(
        timestamps=rng.copy(),
        equity=np.zeros(len(rng)),
        trades=[
            _mk(rng[2], rng[3]),
            _mk(rng[5], rng[6]),
            _mk(rng[9], rng[10]),
        ],
    )

    hit = trades_between_bar_ix(hull, rng, 6, 11)

    assert len(hit) == 1

    assert hit[0].entry_ts == rng[9]


def test_summarize_trades_empty_pf_inf() -> None:

    mz = summarize_trades([])

    assert mz.trades == 0

    assert np.isinf(mz.profit_factor)
