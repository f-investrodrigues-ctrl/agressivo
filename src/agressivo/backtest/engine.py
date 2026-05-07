from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from agressivo.backtest.costs import CostParams, apply_trade_cost
from agressivo.backtest.fills import FillTiming

ExitReason = Literal["stop", "take_profit", "eos"]


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    pnl_pct: float
    exit_reason: ExitReason


@dataclass
class PendingEntry:
    atr_signal: float


@dataclass(frozen=True)
class BacktestParams:
    """Long só. Por omissão sinal barras ``i`` → entrada no ``open`` de ``i+1``."""

    initial_equity: float = 10_000.0
    risk_pct_per_trade: float = 0.02
    max_leverage: float = 1.0
    stop_atr_multiple: float = 2.0
    trailing_atr_multiple: float = 3.0
    take_profit_r_multiple: float | None = 5.0

    fill_timing: FillTiming = "next_bar_open"


@dataclass
class EquityCurve:
    timestamps: pd.DatetimeIndex
    equity: np.ndarray

    trades: list[Trade] = field(default_factory=list)


def _attempt_long_entry(
    *,
    px_fill: float,
    atr_sig: float,
    equity_cap_base: float,
    cash_avail: float,
    params: BacktestParams,
    costs: CostParams,
    ts: pd.Timestamp,
) -> tuple[float, float, float, float, float, pd.Timestamp] | None:

    sd = params.stop_atr_multiple * atr_sig
    q = equity_cap_base * params.risk_pct_per_trade / sd if sd > 0 else 0.0

    notion = q * px_fill
    cap_notional = equity_cap_base * params.max_leverage

    if cap_notional > 0 < px_fill and notion > cap_notional:
        q = cap_notional / px_fill

    notion = q * px_fill
    lr_buy = costs.leg_rate(px_fill, atr_sig)
    fees = apply_trade_cost(notion, lr_buy)

    if q <= 0 or notion + fees > cash_avail + 1e-12:
        return None

    qty = float(q)
    cash_after = cash_avail - (qty * px_fill + fees)

    pk0 = float(px_fill)
    hs_stop = px_fill - sd

    return qty, cash_after, sd, hs_stop, pk0, ts


def run_long_backtest(
    df: pd.DataFrame,
    signal_long: pd.Series,
    atr: pd.Series,
    *,
    params: BacktestParams,
    costs: CostParams,
) -> EquityCurve:
    idx = df.index

    ox = df["open"].astype(float).to_numpy()
    hg = df["high"].astype(float).to_numpy()
    lw = df["low"].astype(float).to_numpy()
    cl = df["close"].astype(float).to_numpy()

    atrv = atr.reindex(df.index).ffill().astype(float).to_numpy()
    sg = signal_long.reindex(df.index).fillna(False).to_numpy(dtype=bool)

    n = len(df)
    equity = np.zeros(n, dtype=float)
    trades: list[Trade] = []
    cash = float(params.initial_equity)

    qty = 0.0
    entry_px = 0.0
    entr_atr_ref = float("nan")

    sd0 = 0.0
    hstop = 0.0

    trek = 0.0

    t_entry = idx[0]
    pend: PendingEntry | None = None

    def bail_out(b_ix: int, why: ExitReason, qx: float, x_price: float, atr_here: float) -> None:

        nonlocal cash, qty

        gv = qx * x_price

        f_out = apply_trade_cost(gv, costs.leg_rate(x_price, atr_here))
        buy_notional = qx * entry_px
        f_in = apply_trade_cost(buy_notional, costs.leg_rate(entry_px, entr_atr_ref))

        pnl_here = gv - f_out - (buy_notional + f_in)

        trades.append(
            Trade(
                entry_ts=t_entry,
                exit_ts=idx[b_ix],
                entry_price=float(entry_px),
                exit_price=float(x_price),
                qty=float(qx),
                pnl=float(pnl_here),
                pnl_pct=(x_price - entry_px) / entry_px if entry_px else 0.0,
                exit_reason=why,
            )
        )

        cash = cash + gv - f_out

        qty = 0.0

    for k in range(n):
        ahere = float(atrv[k])

        # ordem entrada pendente antes de stops da mesma barra

        if qty == 0 and pend is not None and params.fill_timing == "next_bar_open":
            hold = pend
            pend = None
            atr_s = hold.atr_signal
            oo = float(ox[k])
            if atr_s > 0 and oo > 0 and np.isfinite(atr_s) and np.isfinite(oo):
                res = _attempt_long_entry(
                    px_fill=oo,
                    atr_sig=float(atr_s),
                    equity_cap_base=cash,
                    cash_avail=cash,
                    params=params,
                    costs=costs,
                    ts=idx[k],
                )

                if res:
                    qty, cash, sd0, hstop, trek, t_entry = res

                    entry_px = oo

                    entr_atr_ref = float(atr_s)

        if qty > 0 and np.isfinite(ahere) and ahere > 0:
            trek = max(trek, float(hg[k]))
            trail_stop = trek - params.trailing_atr_multiple * ahere
            eff_stop = max(hstop, trail_stop)

            tp_px = (
                entry_px + params.take_profit_r_multiple * sd0
                if params.take_profit_r_multiple is not None and sd0 > 0
                else float("inf")
            )

            sl_touch = float(lw[k]) <= eff_stop
            tp_touch = tp_px < float("inf") and float(hg[k]) >= tp_px

            reason: ExitReason | None = None
            xh = 0.0

            if sl_touch:
                reason = "stop"
                xh = min(eff_stop, float(cl[k]))

            elif tp_touch:
                reason = "take_profit"
                xh = tp_px

            if reason:
                bail_out(k, reason, qty, xh, ahere)

        equity[k] = cash + qty * cl[k]

        if params.fill_timing == "close_same_bar":
            if qty == 0 and sg[k] and np.isfinite(ahere) and ahere > 0:
                res2 = _attempt_long_entry(
                    px_fill=float(cl[k]),
                    atr_sig=ahere,
                    equity_cap_base=equity[k],
                    cash_avail=cash,
                    params=params,
                    costs=costs,
                    ts=idx[k],
                )

                if res2:
                    qty, cash, sd0, hstop, trek, t_entry = res2
                    entry_px = float(cl[k])

                    entr_atr_ref = ahere

                    equity[k] = cash + qty * cl[k]

        if params.fill_timing == "next_bar_open" and qty == 0 and sg[k]:
            if np.isfinite(ahere) and ahere > 0 and k + 1 < n:
                pend = PendingEntry(atr_signal=float(ahere))

    if qty > 0:
        xf = float(cl[-1])
        at_end = float(atrv[-1]) if np.isfinite(atrv[-1]) else 0.0

        gv2 = qty * xf
        fout = apply_trade_cost(gv2, costs.leg_rate(xf, at_end))

        gv0 = qty * entry_px
        fi = apply_trade_cost(gv0, costs.leg_rate(entry_px, entr_atr_ref))

        pnlEOS = gv2 - fout - (gv0 + fi)

        trades.append(
            Trade(
                entry_ts=t_entry,
                exit_ts=idx[-1],
                entry_price=float(entry_px),
                exit_price=xf,
                qty=float(qty),
                pnl=float(pnlEOS),
                pnl_pct=(xf - entry_px) / entry_px if entry_px else 0.0,
                exit_reason="eos",
            )
        )

        cash = cash + gv2 - fout

        qty = 0.0
        equity[-1] = cash

    return EquityCurve(timestamps=idx.copy(), equity=equity, trades=trades)
