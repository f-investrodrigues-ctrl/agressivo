from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agressivo.backtest.costs import CostParams, apply_trade_cost
from agressivo.backtest.engine import BacktestParams
from agressivo.paper.decision import PaperSnapshot
from agressivo.paper.state import PaperState
from agressivo.strategy.core_breakout import atr


@dataclass(frozen=True)
class PaperEvent:
    kind: str
    detail: str


def qty_for_long_leg(
    *,
    cash: float,
    fill_px: float,
    atr_sig: float,
    params: BacktestParams,
    costs: CostParams,
) -> float | None:
    sd = params.stop_atr_multiple * atr_sig
    if sd <= 0 or fill_px <= 0 or cash <= 0:
        return None

    q_risk = cash * params.risk_pct_per_trade / sd
    notion = q_risk * fill_px
    cap = cash * params.max_leverage
    if notion > cap and cap > 0 and fill_px > 0:
        q_risk = cap / fill_px

    notion = q_risk * fill_px
    lr = costs.leg_rate(fill_px, atr_sig)
    fee = apply_trade_cost(notion, lr)

    if q_risk <= 0 or notion + fee > cash + 1e-9:
        return None

    return float(q_risk)


def maybe_exit_managed_position(
    st: PaperState,
    df_work: pd.DataFrame,
    *,
    params: BacktestParams,
    costs: CostParams,
) -> tuple[PaperState, list[PaperEvent]]:
    """
    Stop/trailing/TP apenas na última barra causal de df_work.

    Posição sem plano novo (qty>0 sem entry_timestamp_iso/hard_stop) → só nota legacy.
    """
    logs: list[PaperEvent] = []
    if not st.in_position or df_work.shape[0] < 14:
        return st, logs
    if st.avg_entry is None or st.entry_timestamp_iso is None or st.hard_stop is None:
        logs.append(PaperEvent("note", "position_without_exit_plan_legacy_skip_auto"))
        return st, logs

    try:
        ts_entry = pd.Timestamp(st.entry_timestamp_iso)
    except (ValueError, TypeError):
        logs.append(PaperEvent("warn", "bad_entry_iso"))
        return st, logs

    if df_work.index.tz is not None and ts_entry.tzinfo is None:
        ts_entry = ts_entry.tz_localize(df_work.index.tz)
    if ts_entry not in df_work.index:
        ix = int(df_work.index.searchsorted(ts_entry))
        if ix >= len(df_work):
            return st, logs
        ts_entry = df_work.index[ix]

    atr_s = atr(df_work, window=14)
    last_ix = df_work.index[-1]
    a_bar = float(atr_s.loc[last_ix])
    if not (a_bar == a_bar) or a_bar <= 0:
        return st, logs

    seg = df_work.loc[ts_entry:]
    peak = float(seg["high"].max())
    hstop = float(st.hard_stop)
    ee = float(st.avg_entry)
    stop_line = max(hstop, peak - params.trailing_atr_multiple * a_bar)

    lw = float(df_work.loc[last_ix, "low"])
    hi = float(df_work.loc[last_ix, "high"])
    clo = float(df_work.loc[last_ix, "close"])
    sd0 = ee - hstop
    tp_px = (
        ee + params.take_profit_r_multiple * sd0
        if params.take_profit_r_multiple is not None and sd0 > 0
        else float("inf")
    )

    reason: str | None = None
    xh = clo
    if lw <= stop_line:
        reason = "stop"
        xh = min(stop_line, clo)
    elif tp_px < float("inf") and hi >= tp_px:
        reason = "take_profit"
        xh = tp_px

    if reason is None:
        return st, logs

    st_o, lg = flatten_state(st, xh, costs, atr_for_slip=a_bar)
    lg2 = []
    for e in lg:
        lg2.append(PaperEvent(kind=e.kind, detail=f"{e.detail} [{reason}]"))
    return st_o, lg2


def apply_snapshot_to_state(
    st: PaperState,
    snap: PaperSnapshot,
    *,
    params: BacktestParams,
    costs: CostParams,
) -> tuple[PaperState, list[PaperEvent]]:
    ev: list[PaperEvent] = []
    if not snap.data_ok:
        ev.append(PaperEvent("skip", f"data_quality:{snap.quality_summary}"))
        return st, ev
    if not snap.wants_long:
        ev.append(PaperEvent("hold", "no_signal"))
        return st, ev
    if st.in_position:
        ev.append(PaperEvent("skip", "already_long"))
        return st, ev

    px_here = snap.fill_price
    if not (px_here == px_here) or px_here <= 0:
        ev.append(PaperEvent("skip", "bad_fill_price"))
        return st, ev

    qh = qty_for_long_leg(
        cash=st.cash,
        fill_px=px_here,
        atr_sig=snap.atr_signal,
        params=params,
        costs=costs,
    )
    if qh is None:
        ev.append(PaperEvent("skip", "sizing_failed"))
        return st, ev

    notion = qh * px_here
    lr_buy = costs.leg_rate(px_here, snap.atr_signal)
    fee_buy = apply_trade_cost(notion, lr_buy)
    sd0 = params.stop_atr_multiple * snap.atr_signal
    hx = px_here - sd0

    st2 = PaperState(
        cash=st.cash - notion - fee_buy,
        qty=st.qty + qh,
        avg_entry=px_here,
        entry_timestamp_iso=snap.bar_timestamp.isoformat(),
        trail_peak=px_here,
        hard_stop=hx,
        version=max(st.version, 2),
    )
    bd = f"qty={qh:.6f} px={px_here:.4f} fee={fee_buy:.4f} bar={snap.bar_timestamp}; stop0={hx:.4f}"

    ev.append(PaperEvent("buy", bd))
    return st2, ev


def flatten_state(
    st: PaperState,
    exit_px: float,
    costs: CostParams,
    atr_for_slip: float | None = None,
) -> tuple[PaperState, list[PaperEvent]]:
    logs: list[PaperEvent] = []
    if not st.in_position:
        logs.append(PaperEvent("skip", "flat"))
        return st, logs
    if not (exit_px == exit_px) or exit_px <= 0:
        logs.append(PaperEvent("skip", "bad_exit_price"))
        return st, logs

    gv = st.qty * exit_px
    fee_out = apply_trade_cost(gv, costs.leg_rate(exit_px, atr_for_slip))
    logs.append(PaperEvent("sell", f"qty={st.qty:.6f} px={exit_px:.4f} fee={fee_out:.4f}"))

    return (
        PaperState(
            cash=st.cash + gv - fee_out,
            qty=0.0,
            avg_entry=None,
            entry_timestamp_iso=None,
            trail_peak=None,
            hard_stop=None,
            version=st.version,
        ),
        logs,
    )
