from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agressivo import __version__
from agressivo.backtest.engine import Trade
from agressivo.backtest.metrics import BacktestMetrics
from agressivo.satellite.resolve import SatelliteResolution


def _finite_num(x: float) -> float | None:
    xf = float(x)
    if not math.isfinite(xf):
        return None
    return xf


def trade_to_dict(t: Trade) -> dict[str, Any]:
    return {
        "entry_ts": t.entry_ts.isoformat(),
        "exit_ts": t.exit_ts.isoformat(),
        "entry_price": float(t.entry_price),
        "exit_price": float(t.exit_price),
        "qty": float(t.qty),
        "pnl": float(t.pnl),
        "pnl_pct": float(t.pnl_pct),
        "exit_reason": t.exit_reason,
    }


def trades_to_jsonables(trades: list[Trade]) -> list[dict[str, Any]]:
    return [trade_to_dict(x) for x in trades]


def metrics_to_dict(m: BacktestMetrics) -> dict[str, Any]:
    pf = float(m.profit_factor)

    return {
        "bars": int(m.bars),
        "trades": int(m.trades),
        "wins": int(m.wins),
        "losses": int(m.losses),
        "net_pnl": _finite_num(m.net_pnl),
        "gross_profit": _finite_num(m.gross_profit),
        "gross_loss": _finite_num(m.gross_loss),
        "profit_factor": None if not math.isfinite(pf) else pf,
        "profit_factor_is_infinite": math.isinf(pf) and pf > 0,
        "win_rate": _finite_num(m.win_rate),
        "max_drawdown_pct": _finite_num(m.max_drawdown_pct),
        "final_equity": _finite_num(m.final_equity),
    }


def satellite_meta(res: SatelliteResolution) -> dict[str, Any]:
    return {
        "audit_line": res.audit_line(),
        "source_path": res.source_path.as_posix() if res.source_path else None,
        "sha256_hex": res.sha256_hex,
    }


def write_json_report(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def runtime_meta() -> dict[str, str]:
    return {
        "agressivo_version": __version__,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }


def build_backtest_breakout_report(
    *,
    symbol: str,
    timeframe: str,
    frame_rows: int,
    exchange_cli: str | None,
    exchange_effective: str,
    sniper: bool,
    fill_timing: str,
    fee_bps: float | None,
    slip_bps: float | None,
    slip_atr_frac: float | None,
    bar_index_start_iso: str,
    bar_index_end_iso: str,
    qc_summary: str,
    metrics: BacktestMetrics,
    sat: SatelliteResolution,
    trades: list[dict[str, Any]] | None = None,
    core_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": frame_rows,
        "exchange_cli": exchange_cli,
        "exchange_effective": exchange_effective,
        "sniper": sniper,
        "fill_timing": fill_timing,
        "fee_bps": fee_bps,
        "slip_bps": slip_bps,
        "slip_atr_frac": slip_atr_frac,
    }

    if core_regime is not None:
        params["core_regime"] = core_regime

    doc: dict[str, Any] = {
        "schema_version": 1,
        "run_type": "backtest_breakout",
        "runtime": runtime_meta(),
        "params": params,
        "satellite": satellite_meta(sat),
        "data": {
            "bars": frame_rows,
            "index_start": bar_index_start_iso,
            "index_end": bar_index_end_iso,
            "qc": qc_summary,
        },
        "metrics": metrics_to_dict(metrics),
    }

    if trades is not None:
        doc["trades"] = trades

    return doc


def build_walk_forward_report(
    *,
    symbol: str,
    timeframe: str,
    frame_rows: int,
    train_bars: int,
    test_bars: int,
    step_bars: int | None,
    exchange_cli: str | None,
    exchange_effective: str,
    sniper: bool,
    fill_timing: str,
    fee_bps: float | None,
    slip_bps: float | None,
    slip_atr_frac: float | None,
    bar_index_start_iso: str,
    bar_index_end_iso: str,
    qc_summary: str,
    global_metrics: BacktestMetrics,
    folds_payload: list[dict[str, Any]],
    sat: SatelliteResolution,
    global_trades: list[dict[str, Any]] | None = None,
    core_regime: dict[str, Any] | None = None,
    oos_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": frame_rows,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "step_bars": step_bars,
        "exchange_cli": exchange_cli,
        "exchange_effective": exchange_effective,
        "sniper": sniper,
        "fill_timing": fill_timing,
        "fee_bps": fee_bps,
        "slip_bps": slip_bps,
        "slip_atr_frac": slip_atr_frac,
    }

    if core_regime is not None:
        params["core_regime"] = core_regime

    doc: dict[str, Any] = {
        "schema_version": 1,
        "run_type": "walk_forward",
        "runtime": runtime_meta(),
        "params": params,
        "satellite": satellite_meta(sat),
        "data": {
            "bars": frame_rows,
            "index_start": bar_index_start_iso,
            "index_end": bar_index_end_iso,
            "qc": qc_summary,
        },
        "global_metrics": metrics_to_dict(global_metrics),
        "folds": folds_payload,
    }

    if global_trades is not None:
        doc["global_trades"] = global_trades
    if oos_summary is not None:
        doc["oos_summary"] = oos_summary

    return doc
