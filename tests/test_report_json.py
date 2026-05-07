from __future__ import annotations

import json

import pandas as pd

from agressivo.backtest.engine import Trade
from agressivo.backtest.metrics import BacktestMetrics
from agressivo.runner.report_json import (
    build_backtest_breakout_report,
    build_walk_forward_report,
    metrics_to_dict,
    satellite_meta,
    trades_to_jsonables,
    write_json_report,
)
from agressivo.satellite.resolve import SatelliteResolution


def test_metrics_to_dict_handles_inf_pf() -> None:
    m = BacktestMetrics(
        bars=100,
        trades=2,
        wins=1,
        losses=1,
        net_pnl=1.0,
        gross_profit=2.0,
        gross_loss=1.0,
        profit_factor=float("inf"),
        win_rate=0.5,
        max_drawdown_pct=0.1,
        final_equity=10_001.0,
    )

    d = metrics_to_dict(m)

    assert d["profit_factor"] is None
    assert d["profit_factor_is_infinite"] is True


def test_write_json_report_roundtrip(tmp_path) -> None:
    p = tmp_path / "out.json"

    write_json_report(p, {"a": 1, "b": [2, 3]})

    obj = json.loads(p.read_text(encoding="utf-8"))

    assert obj == {"a": 1, "b": [2, 3]}


def test_trades_to_jsonables_roundtrip_fields() -> None:
    t = Trade(
        entry_ts=pd.Timestamp("2020-01-01", tz="UTC"),
        exit_ts=pd.Timestamp("2020-01-02", tz="UTC"),
        entry_price=1.0,
        exit_price=1.1,
        qty=2.0,
        pnl=0.2,
        pnl_pct=0.1,
        exit_reason="eos",
    )

    rows = trades_to_jsonables([t])

    assert rows[0]["exit_reason"] == "eos"
    assert rows[0]["entry_ts"].startswith("2020")


def test_build_backtest_report_has_satellite_block() -> None:
    sat = SatelliteResolution(catalog=None, source_path=None, sha256_hex=None)

    m = BacktestMetrics(
        bars=10,
        trades=0,
        wins=0,
        losses=0,
        net_pnl=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        profit_factor=float("nan"),
        win_rate=0.0,
        max_drawdown_pct=0.0,
        final_equity=10_000.0,
    )

    doc = build_backtest_breakout_report(
        symbol="BTC/USDT",
        timeframe="1h",
        frame_rows=10,
        exchange_cli=None,
        exchange_effective="binance",
        sniper=False,
        fill_timing="next_bar_open",
        fee_bps=None,
        slip_bps=None,
        slip_atr_frac=None,
        bar_index_start_iso="2020-01-01T00:00:00+00:00",
        bar_index_end_iso="2020-01-02T00:00:00+00:00",
        qc_summary="ok",
        metrics=m,
        sat=sat,
    )

    assert doc["run_type"] == "backtest_breakout"
    assert doc["satellite"]["audit_line"] is None
    assert "metrics" in doc
    assert "trades" not in doc


def test_build_backtest_report_core_regime_in_params() -> None:
    sat = SatelliteResolution(catalog=None, source_path=None, sha256_hex=None)

    m = BacktestMetrics(
        bars=10,
        trades=0,
        wins=0,
        losses=0,
        net_pnl=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        profit_factor=float("nan"),
        win_rate=0.0,
        max_drawdown_pct=0.0,
        final_equity=10_000.0,
    )

    doc = build_backtest_breakout_report(
        symbol="BTC/USDT",
        timeframe="1h",
        frame_rows=10,
        exchange_cli=None,
        exchange_effective="binance",
        sniper=False,
        fill_timing="next_bar_open",
        fee_bps=None,
        slip_bps=None,
        slip_atr_frac=None,
        bar_index_start_iso="2020-01-01T00:00:00+00:00",
        bar_index_end_iso="2020-01-02T00:00:00+00:00",
        qc_summary="ok",
        metrics=m,
        sat=sat,
        core_regime={"trend_ma": 99, "require_above_trend": False},
    )

    assert doc["params"]["core_regime"] == {"trend_ma": 99, "require_above_trend": False}


def test_build_walk_forward_report_core_regime_in_params() -> None:
    sat = SatelliteResolution(catalog=None, source_path=None, sha256_hex=None)

    m = BacktestMetrics(
        bars=10,
        trades=0,
        wins=0,
        losses=0,
        net_pnl=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        profit_factor=float("nan"),
        win_rate=0.0,
        max_drawdown_pct=0.0,
        final_equity=10_000.0,
    )

    doc = build_walk_forward_report(
        symbol="BTC/USDT",
        timeframe="1h",
        frame_rows=10,
        train_bars=5,
        test_bars=3,
        step_bars=None,
        exchange_cli=None,
        exchange_effective="binance",
        sniper=False,
        fill_timing="next_bar_open",
        fee_bps=None,
        slip_bps=None,
        slip_atr_frac=None,
        bar_index_start_iso="2020-01-01T00:00:00+00:00",
        bar_index_end_iso="2020-01-02T00:00:00+00:00",
        qc_summary="ok",
        global_metrics=m,
        folds_payload=[],
        sat=sat,
        core_regime={"trend_ma": 50, "require_above_trend": True},
    )

    assert doc["params"]["core_regime"] == {"trend_ma": 50, "require_above_trend": True}


def test_build_walk_forward_report_includes_oos_summary() -> None:
    sat = SatelliteResolution(catalog=None, source_path=None, sha256_hex=None)

    m = BacktestMetrics(
        bars=10,
        trades=0,
        wins=0,
        losses=0,
        net_pnl=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        profit_factor=float("nan"),
        win_rate=0.0,
        max_drawdown_pct=0.0,
        final_equity=10_000.0,
    )

    oos = {"folds": 3, "folds_with_trades": 2, "oos_trades": 9, "oos_net_pnl": 12.5}

    doc = build_walk_forward_report(
        symbol="BTC/USDT",
        timeframe="1h",
        frame_rows=10,
        train_bars=5,
        test_bars=3,
        step_bars=None,
        exchange_cli=None,
        exchange_effective="binance",
        sniper=False,
        fill_timing="next_bar_open",
        fee_bps=None,
        slip_bps=None,
        slip_atr_frac=None,
        bar_index_start_iso="2020-01-01T00:00:00+00:00",
        bar_index_end_iso="2020-01-02T00:00:00+00:00",
        qc_summary="ok",
        global_metrics=m,
        folds_payload=[],
        sat=sat,
        oos_summary=oos,
    )

    assert doc["oos_summary"] == oos


def test_build_backtest_report_includes_trades_key() -> None:
    sat = SatelliteResolution(catalog=None, source_path=None, sha256_hex=None)

    m = BacktestMetrics(
        bars=10,
        trades=0,
        wins=0,
        losses=0,
        net_pnl=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        profit_factor=float("nan"),
        win_rate=0.0,
        max_drawdown_pct=0.0,
        final_equity=10_000.0,
    )

    tj = [{"id": "x"}]

    doc = build_backtest_breakout_report(
        symbol="BTC/USDT",
        timeframe="1h",
        frame_rows=10,
        exchange_cli=None,
        exchange_effective="binance",
        sniper=False,
        fill_timing="next_bar_open",
        fee_bps=None,
        slip_bps=None,
        slip_atr_frac=None,
        bar_index_start_iso="2020-01-01T00:00:00+00:00",
        bar_index_end_iso="2020-01-02T00:00:00+00:00",
        qc_summary="ok",
        metrics=m,
        sat=sat,
        trades=tj,
    )

    assert doc["trades"] == tj


def test_satellite_meta_with_path(tmp_path) -> None:
    p = tmp_path / "c.json"
    p.write_text('{"version": 1, "events": []}', encoding="utf-8")

    from agressivo.satellite.catalog import load_satellite_catalog

    cat = load_satellite_catalog(p)

    from agressivo.satellite.resolve import file_sha256

    res = SatelliteResolution(catalog=cat, source_path=p, sha256_hex=file_sha256(p))

    meta = satellite_meta(res)

    assert meta["audit_line"]
    assert meta["source_path"] == p.as_posix()
