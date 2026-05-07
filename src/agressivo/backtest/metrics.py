from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from agressivo.backtest.engine import EquityCurve, Trade


@dataclass(frozen=True)
class BacktestMetrics:
    bars: int

    trades: int
    wins: int
    losses: int

    net_pnl: float
    gross_profit: float

    gross_loss: float

    profit_factor: float

    win_rate: float

    max_drawdown_pct: float

    final_equity: float


def max_drawdown_pct(eq: np.ndarray) -> float:
    if eq.size == 0:
        return 0.0

    peaks = np.maximum.accumulate(eq)

    dd = (eq - peaks) / np.where(peaks > 1e-12, peaks, 1.0)
    return float(dd.min())


def summarize_equity_curve(curve: EquityCurve, *, bars: int) -> BacktestMetrics:
    w = sum(1 for z in curve.trades if z.pnl > 0)
    lc = sum(1 for z in curve.trades if z.pnl <= 0)

    gw = sum(x.pnl for x in curve.trades if x.pnl > 0)
    glm = sum(-x.pnl for x in curve.trades if x.pnl < 0)
    pfq = gw / glm if glm > 0 else float("inf")
    tally = curve.trades or []
    netz = float(sum(x.pnl for x in tally))

    return BacktestMetrics(
        bars=bars,
        trades=len(curve.trades),
        wins=w,
        losses=lc,
        net_pnl=netz,
        gross_profit=gw,
        gross_loss=glm,
        profit_factor=pfq,
        win_rate=w / len(curve.trades) if curve.trades else 0.0,
        max_drawdown_pct=max_drawdown_pct(curve.equity),
        final_equity=float(curve.equity[-1]) if curve.equity.size else 0.0,
    )


def summarize_trades(ts: Iterable[Trade]) -> BacktestMetrics:

    lst = list(ts)

    wsum = sum(1 for q in lst if q.pnl > 0)

    lw = sum(1 for q in lst if q.pnl <= 0)

    gpi = sum(q.pnl for q in lst if q.pnl > 0)

    gle = sum(-q.pnl for q in lst if q.pnl < 0)

    pfd = gpi / gle if gle > 0 else float("inf")
    nets = float(sum(q.pnl for q in lst))

    return BacktestMetrics(
        bars=0,
        trades=len(lst),
        wins=wsum,
        losses=lw,
        net_pnl=nets,
        gross_profit=gpi,
        gross_loss=gle,
        profit_factor=pfd,
        win_rate=wsum / len(lst) if lst else 0.0,
        max_drawdown_pct=float("nan"),
        final_equity=float("nan"),
    )


def trades_between_bar_ix(
    curve: EquityCurve, ix: pd.DatetimeIndex, lo: int, hi_ex: int
) -> list[Trade]:
    """

    Lista trades cuja entrada cai nos índices inteiro ``[lo, hi_ex)`` do ``df`` original.



    """

    if not curve.trades:
        return []

    et = pd.DatetimeIndex([p.entry_ts for p in curve.trades])

    placements = ix.get_indexer(et)

    acc: list[Trade] = []

    for jloop, trader in enumerate(curve.trades):
        kk = placements[jloop]

        if kk < 0:
            continue
        if lo <= int(kk) < hi_ex:
            acc.append(trader)

    return acc
