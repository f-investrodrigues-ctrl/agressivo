from __future__ import annotations

import numpy as np
import pandas as pd

from agressivo.backtest.costs import CostParams
from agressivo.data.quality import assess_ohlcv_quality
from agressivo.paper.decision import build_snapshot
from agressivo.paper.persist import load_state, save_state
from agressivo.paper.state import PaperState
from agressivo.paper.step import flatten_state


def test_build_snapshot_short_warms_up() -> None:
    rng = pd.date_range("2024-01-01", periods=50, freq="h", tz="UTC")
    dfx = pd.DataFrame(
        {
            "open": 2.0,
            "high": 2.1,
            "low": 1.9,
            "close": 2.05,
            "volume": 1e3,
        },
        index=rng,
    )
    qc = assess_ohlcv_quality(dfx, expected_freq="1h")
    snap = build_snapshot(dfx, qc, sniper=False)
    assert not snap.wants_long
    assert "warmup" in snap.quality_summary


def test_flatten_state_sell() -> None:
    st = PaperState(cash=5000.0, qty=0.1, avg_entry=100.0, version=1)
    cx = CostParams(slippage_atr_fraction=0.0)
    st2, ev = flatten_state(st, exit_px=110.0, costs=cx, atr_for_slip=None)
    assert st2.qty == 0.0
    assert st2.cash > st.cash
    assert any(e.kind == "sell" for e in ev)


def test_persist_roundtrip(tmp_path) -> None:
    p = tmp_path / "paper.json"
    s0 = PaperState(cash=123.0, qty=0.0, avg_entry=None)
    save_state(p, s0)
    s1 = load_state(p)
    assert s1.cash == 123.0

    assert s1.qty == 0.0


def test_reconcile_import() -> None:
    from agressivo.reconcile import compare_position_qty

    r = compare_position_qty(local_qty=1.0, exchange_qty=1.0, abs_tol=1e-9)
    assert r.ok

    r2 = compare_position_qty(local_qty=1.0, exchange_qty=0.0)
    assert not r2.ok


def test_build_snapshot_no_drop_last() -> None:
    """Série longa monotónica: smoke sem crash."""

    rng = pd.date_range("2023-01-01", periods=400, freq="h", tz="UTC")
    r = np.arange(400.0)
    px = 10_000 + r * 3
    dfz = pd.DataFrame(
        {
            "open": px,
            "high": px + 4,
            "low": px - 4,
            "close": px,
            "volume": 1000 + r,
        },
        index=rng,
    )
    qc = assess_ohlcv_quality(dfz, expected_freq="1h")
    sn = build_snapshot(dfz, qc, sniper=False, drop_last_incomplete=False)
    assert sn.data_ok
    assert sn.fill_price == sn.fill_price
