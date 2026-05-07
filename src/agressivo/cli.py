from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import ccxt
import typer

from agressivo import __version__
from agressivo.backtest.costs import CostParams
from agressivo.backtest.engine import BacktestParams
from agressivo.backtest.fills import FillTiming
from agressivo.backtest.metrics import (
    BacktestMetrics,
    summarize_equity_curve,
    summarize_trades,
    trades_between_bar_ix,
)
from agressivo.backtest.walkforward import folds
from agressivo.config import Settings, get_settings
from agressivo.data.ohlcv import fetch_ohlcv_ccxt
from agressivo.data.quality import assess_ohlcv_quality
from agressivo.exchange import (
    authenticated_exchange,
    fetch_my_trades_for_symbol,
    fetch_open_orders_for_symbol,
    fetch_order_by_id,
    fetch_spot_balance_row,
    has_auth_config,
)
from agressivo.execution import OrderRequest, mirror_paper_trades, submit_order
from agressivo.execution.ledger_read import tail_jsonl_records
from agressivo.logging_config import setup_logging
from agressivo.paper import (
    PaperState,
    apply_snapshot_to_state,
    build_snapshot,
    causal_trim,
    flatten_state,
    load_state,
    maybe_exit_managed_position,
    save_state,
)
from agressivo.reconcile import compare_position_qty
from agressivo.risk.kelly import KellyInputs, fractional_kelly
from agressivo.runner.breakout_bt import breakout_run
from agressivo.runner.report_json import (
    build_backtest_breakout_report,
    build_walk_forward_report,
    metrics_to_dict,
    trades_to_jsonables,
    write_json_report,
)
from agressivo.satellite.catalog import effective_end_exclusive, events_intersecting
from agressivo.satellite.resolve import (
    SatelliteResolution,
    satellite_from_config_path,
    satellite_from_path,
)
from agressivo.strategy.sniper import veto_check

app = typer.Typer(help="Agressivo — dados, Core backtest, walk-forward")

_FILL_ALIASES: dict[str, FillTiming] = {
    "next_bar_open": "next_bar_open",
    "next-bar": "next_bar_open",
    "next-open": "next_bar_open",
    "nextopen": "next_bar_open",
    "close_same_bar": "close_same_bar",
    "close": "close_same_bar",
    "same-bar": "close_same_bar",
}


def _resolve_fill_timing(label: str) -> FillTiming:
    ky = label.strip().lower()

    mapped = _FILL_ALIASES.get(ky)
    if mapped is None:
        typer.echo("fill_timing inválido. Ex.: next-bar | next_bar_open | close | close_same_bar")
        raise typer.Exit(code=2)
    return mapped


def _make_cost(
    *,
    fee_bps: float | None,
    slip_bps: float | None,
    slip_atr_frac: float | None,
) -> CostParams:
    return CostParams(
        fee_rate=(fee_bps if fee_bps is not None else 4.0) / 10_000.0,
        slippage_rate=(slip_bps if slip_bps is not None else 2.0) / 10_000.0,
        slippage_atr_fraction=0.05 if slip_atr_frac is None else float(slip_atr_frac),
    )


def _core_regime_effective(
    cfg: Settings,
    trend_ma_cli: int | None,
    no_trend_filter: bool,
) -> tuple[int, bool]:
    """MA de tendência e filtro close>MA (Settings + overrides CLI)."""

    tm = int(cfg.core_trend_ma if trend_ma_cli is None else trend_ma_cli)

    if not (5 <= tm <= 500):
        typer.echo("--trend-ma deve estar entre 5 e 500")
        raise typer.Exit(code=2)

    rat = False if no_trend_filter else bool(cfg.core_require_above_trend)

    return tm, rat


def _wf_oos_summary(fold_metrics: list[BacktestMetrics]) -> dict[str, float | int]:
    """Resumo OOS agregado no conjunto de janelas de teste."""

    if not fold_metrics:
        return {
            "folds": 0,
            "folds_with_trades": 0,
            "oos_trades": 0,
            "oos_net_pnl": 0.0,
            "avg_win_rate": 0.0,
            "avg_profit_factor": 0.0,
        }

    folds_with_trades = [m for m in fold_metrics if m.trades > 0]
    oos_trades = int(sum(m.trades for m in fold_metrics))
    oos_net_pnl = float(sum(m.net_pnl for m in fold_metrics))
    avg_win_rate = (
        float(sum(m.win_rate for m in folds_with_trades) / len(folds_with_trades))
        if folds_with_trades
        else 0.0
    )
    avg_profit_factor = (
        float(sum(m.profit_factor for m in folds_with_trades) / len(folds_with_trades))
        if folds_with_trades
        else 0.0
    )

    return {
        "folds": len(fold_metrics),
        "folds_with_trades": len(folds_with_trades),
        "oos_trades": oos_trades,
        "oos_net_pnl": oos_net_pnl,
        "avg_win_rate": avg_win_rate,
        "avg_profit_factor": avg_profit_factor,
    }


def _should_abort_after_failure(streak: int, max_consecutive_failures: int) -> bool:
    """True quando guardrail de falhas consecutivas deve abortar o ciclo."""

    if max_consecutive_failures <= 0:
        return False
    return streak >= max_consecutive_failures


def _paper_run_health_summary(
    *,
    polls_total: int,
    polls_ok: int,
    polls_failed: int,
    fail_streak_end: int,
    max_fail_streak: int,
    aborted_by_guardrail: bool,
    stopped_by_keyboard: bool,
) -> dict[str, int | bool]:
    return {
        "polls_total": polls_total,
        "polls_ok": polls_ok,
        "polls_failed": polls_failed,
        "fail_streak_end": fail_streak_end,
        "max_fail_streak": max_fail_streak,
        "aborted_by_guardrail": aborted_by_guardrail,
        "stopped_by_keyboard": stopped_by_keyboard,
    }


@dataclass
class LoadedFrame:
    df: object

    qc: object


def _load(
    symbol: str, timeframe: str, exchange: str | None, bars: int, lg: logging.Logger
) -> LoadedFrame:
    cfg = get_settings()

    cid = exchange or cfg.exchange

    frm = fetch_ohlcv_ccxt(cid, symbol, timeframe, limit=bars)
    rep = assess_ohlcv_quality(frm, expected_freq=timeframe)

    ok_go, veto_why = veto_check(data_ok=rep.ok)

    if not ok_go:
        lg.warning("Veto: %s", veto_why)

        raise typer.Exit(code=1)

    return LoadedFrame(df=frm, qc=rep)


def _load_frame_qc(
    symbol: str, timeframe: str, exchange: str | None, bars: int, lg: logging.Logger
) -> LoadedFrame:
    """OHLCV + relatório de qualidade **sem** abortar por veto Sniper (só aviso)."""

    cfg = get_settings()

    cid = exchange or cfg.exchange

    frm = fetch_ohlcv_ccxt(cid, symbol, timeframe, limit=bars)

    rep = assess_ohlcv_quality(frm, expected_freq=timeframe)

    ok_go, veto_why = veto_check(data_ok=rep.ok)

    if not ok_go:
        lg.warning("Qualidade / veto (apenas informativo): %s", veto_why)

    return LoadedFrame(df=frm, qc=rep)


def _paper_mirror_report(
    *,
    enabled: bool,
    symbol: str,
    events: list[object],
    ledger_file: str | None,
    default_ledger: Path,
) -> None:
    if not enabled:
        return
    dest = Path(ledger_file) if ledger_file else default_ledger
    n = mirror_paper_trades(dest, symbol, events)
    if n:
        typer.echo(f"  paper_mirror: +{n} linha(s) em {dest}")


def _resolve_sat_catalog(
    cli_path: str | None,
    fallback_path: Path | None,
) -> SatelliteResolution:
    if cli_path is not None and str(cli_path).strip():
        p = Path(cli_path.strip())
        if not p.is_file():
            typer.echo(f"Catálogo satélite não encontrado: {p}")
            raise typer.Exit(code=2)
        return satellite_from_path(p)

    got = satellite_from_config_path(fallback_path)
    if got is None and fallback_path is not None and str(fallback_path).strip():
        logging.getLogger("cli").warning(
            "AGRESSIVO_SATELLITE_CATALOG_PATH inexistente, satélite desligado: %s",
            fallback_path,
        )

    return got if got is not None else SatelliteResolution(None, None, None)


def _echo_sat_audit(res: SatelliteResolution) -> None:
    line = res.audit_line()
    if line:
        typer.echo(line)


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:

    settings = get_settings()

    lvl = "DEBUG" if verbose else settings.log_level

    setup_logging(lvl)


@app.command()
def version() -> None:

    typer.echo(__version__)


@app.command("satellite-scan")
def satellite_scan(
    catalog_path: str = typer.Option(..., "--catalog"),
    within_hours: float = typer.Option(
        168.0,
        "--within-hours",
        help="Horas à frente (1–8760); limitado no corpo do comando.",
    ),
) -> None:
    """Lista eventos no horizonte UTC [agora, agora+within_hours).

    Catálogo de exemplo em ``data/satellite/catalog.example.json``.
    """

    if within_hours < 1.0 or within_hours > 8760.0:
        typer.echo("within_hours deve estar entre 1 e 8760")
        raise typer.Exit(code=2)

    cp = Path(catalog_path)

    if not cp.is_file():
        typer.echo(f"Catálogo não encontrado: {cp}")
        raise typer.Exit(code=2)

    sat_res = satellite_from_path(cp)
    _echo_sat_audit(sat_res)

    now = datetime.now(UTC)

    until = now + timedelta(hours=within_hours)

    cat = sat_res.catalog
    assert cat is not None

    evs = events_intersecting(cat, now, until)
    typer.echo(
        f"UTC [{now.isoformat()} .. {until.isoformat()}) → {len(evs)} evento(s) com sobreposição"
    )
    for ev in evs:
        hi = effective_end_exclusive(ev)
        tags = ",".join(ev.tags) if ev.tags else ""
        line = (
            f"  {ev.start.isoformat()} .. {hi.isoformat()} | veto_core={ev.veto_core} | "
            f"{ev.id}: {ev.title}"
        )
        if tags:
            line += f" | [{tags}]"
        typer.echo(line)
    typer.echo(
        "Veto Paper: só eventos veto_core=true; janelas [start,end) em UTC."
    )


@app.command("fetch-ohlcv")
def fetch_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    limit: int = typer.Option(500),
) -> None:

    cfg = get_settings()

    cid = exchange or cfg.exchange

    frm = fetch_ohlcv_ccxt(cid, symbol, timeframe, limit=limit)

    rep = assess_ohlcv_quality(frm, expected_freq=timeframe)

    typer.echo(rep.summary)

    typer.echo(frm.tail(3).to_string())


@app.command("ohlcv-qc")
def ohlcv_qc_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(500),
) -> None:
    """Apenas qualidade OHLCV (não aborta por veto; útil para data health)."""

    lg = logging.getLogger("cli")

    lf = _load_frame_qc(symbol, timeframe, exchange, bars, lg)

    typer.echo(f"data_ok={lf.qc.ok} bars={len(lf.df)}")
    typer.echo(lf.qc.summary)


@app.command("kelly-calc")
def kelly_calc_cmd(
    win_rate: float = typer.Option(..., "--win-rate", help="Taxa de acerto em ]0,1["),
    win_mean: float = typer.Option(..., "--win-mean", help="Ganho médio por vitória (>0)"),
    lose_mean: float = typer.Option(
        ...,
        "--lose-mean",
        help="Magnitude positiva da perda média (ex.: média de |PnL| em perdas)",
    ),
    fractional: float = typer.Option(0.5, "--fractional", help="Kelly fraccionado ]0,1]"),
) -> None:
    """Kelly fraccionado (modelo binário aproximado; ver ``risk/kelly.py``)."""

    if not (0.0 < win_rate < 1.0):
        typer.echo("win_rate deve estar estritamente entre 0 e 1")
        raise typer.Exit(code=2)

    if win_mean <= 0 or lose_mean <= 0:
        typer.echo("win_mean e lose_mean devem ser > 0")
        raise typer.Exit(code=2)

    if not (0.0 < fractional <= 1.0):
        typer.echo("fractional deve estar em ]0,1]")
        raise typer.Exit(code=2)

    fk = fractional_kelly(
        KellyInputs(
            win_rate=win_rate,
            win_mean=win_mean,
            lose_mean_abs=lose_mean,
            fractional=fractional,
        )
    )

    typer.echo(f"fractional_kelly={fk:.8f}")


@app.command("backtest-breakout")
def cmd_single(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(1500),
    sniper: bool = typer.Option(False),
    fill_timing: str = typer.Option("next_bar_open", "--fill-timing", "-f"),
    fee_bps: float | None = typer.Option(None, "--fee-bps"),
    slip_bps: float | None = typer.Option(None, "--slip-bps"),
    slip_atr_frac: float | None = typer.Option(None, "--slip-atr-frac"),
    satellite_catalog: str | None = typer.Option(
        None,
        "--satellite-catalog",
        help="JSON satélite: veto_core só suprime novas entradas (igual ao Paper).",
    ),
    export_json: str | None = typer.Option(
        None,
        "--export-json",
        help="Escrever relatório JSON (métricas + params + satellite_audit).",
    ),
    export_include_trades: bool = typer.Option(
        False,
        "--export-include-trades",
        help="Com --export-json, incluir lista completa de trades no JSON.",
    ),
    trend_ma: int | None = typer.Option(
        None,
        "--trend-ma",
        help="Override AGRESSIVO_CORE_TREND_MA (5–500).",
    ),
    no_trend_filter: bool = typer.Option(
        False,
        "--no-trend-filter",
        help="Desliga exigência close>MA (ignora AGRESSIVO_CORE_REQUIRE_ABOVE_TREND).",
    ),
) -> None:

    log = logging.getLogger("cli")

    cfg_bt = get_settings()

    tm, rat = _core_regime_effective(cfg_bt, trend_ma, no_trend_filter)

    lf = _load(symbol, timeframe, exchange, bars, log)

    ft = _resolve_fill_timing(fill_timing)

    bx = _make_cost(fee_bps=fee_bps, slip_bps=slip_bps, slip_atr_frac=slip_atr_frac)

    sat_bt = _resolve_sat_catalog(satellite_catalog, cfg_bt.satellite_catalog_path)

    _echo_sat_audit(sat_bt)

    _, _, _, curve = breakout_run(
        lf.df,
        sniper_filter=sniper,
        bp=BacktestParams(fill_timing=ft),
        cx=bx,
        satellite=sat_bt.catalog,
        trend_ma=tm,
        require_above_trend=rat,
    )

    agg = summarize_equity_curve(curve, bars=len(lf.df))

    typer.echo(
        f"{symbol} {timeframe} bars={len(lf.df)} qc={lf.qc.summary} | "
        f"trades={agg.trades} PF~{agg.profit_factor:.2f} "
        f"DD~{agg.max_drawdown_pct * 100:.1f}% net={agg.net_pnl:.2f} "
        f"EqEnd={agg.final_equity:.2f} fill={fill_timing} "
        f"trend_ma={tm} above_trend={rat}"
    )

    if export_json:
        ix = lf.df.index

        trades_blob = trades_to_jsonables(curve.trades) if export_include_trades else None

        doc_bt = build_backtest_breakout_report(
            symbol=symbol,
            timeframe=timeframe,
            frame_rows=len(lf.df),
            exchange_cli=exchange,
            exchange_effective=exchange or cfg_bt.exchange,
            sniper=sniper,
            fill_timing=fill_timing,
            fee_bps=fee_bps,
            slip_bps=slip_bps,
            slip_atr_frac=slip_atr_frac,
            bar_index_start_iso=ix[0].isoformat(),
            bar_index_end_iso=ix[-1].isoformat(),
            qc_summary=lf.qc.summary,
            metrics=agg,
            sat=sat_bt,
            trades=trades_blob,
            core_regime={"trend_ma": tm, "require_above_trend": rat},
        )

        outp = Path(export_json)

        write_json_report(outp, doc_bt)

        typer.echo(f"export_json -> {outp}")


@app.command()
def wf(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(2200),
    train_bars: int = typer.Option(900, "--train"),
    test_bars: int = typer.Option(300, "--test"),
    step_bars: int | None = typer.Option(None, "--step"),
    sniper: bool = typer.Option(False),
    fill_timing: str = typer.Option("next_bar_open", "--fill-timing", "-f"),
    fee_bps: float | None = typer.Option(None, "--fee-bps"),
    slip_bps: float | None = typer.Option(None, "--slip-bps"),
    slip_atr_frac: float | None = typer.Option(None, "--slip-atr-frac"),
    satellite_catalog: str | None = typer.Option(
        None,
        "--satellite-catalog",
        help="JSON satélite aplicado ao backtest inteiro antes do WF filtrar trades de teste.",
    ),
    export_json: str | None = typer.Option(
        None,
        "--export-json",
        help="Escrever relatório JSON (folds + global + satellite_audit).",
    ),
    export_include_trades: bool = typer.Option(
        False,
        "--export-include-trades",
        help="Com --export-json, incluir global_trades (curva completa) no JSON.",
    ),
    trend_ma: int | None = typer.Option(
        None,
        "--trend-ma",
        help="Override AGRESSIVO_CORE_TREND_MA (5–500).",
    ),
    no_trend_filter: bool = typer.Option(
        False,
        "--no-trend-filter",
        help="Desliga exigência close>MA (ignora AGRESSIVO_CORE_REQUIRE_ABOVE_TREND).",
    ),
) -> None:

    lg = logging.getLogger("cli")

    cfg_wf = get_settings()

    tm_wf, rat_wf = _core_regime_effective(cfg_wf, trend_ma, no_trend_filter)

    lf = _load(symbol, timeframe, exchange, bars, lg)

    idx = lf.df.index

    ft_mode = _resolve_fill_timing(fill_timing)

    cx_here = _make_cost(fee_bps=fee_bps, slip_bps=slip_bps, slip_atr_frac=slip_atr_frac)

    sat_wf = _resolve_sat_catalog(satellite_catalog, cfg_wf.satellite_catalog_path)

    _echo_sat_audit(sat_wf)

    _, _, _, whole = breakout_run(
        lf.df,
        sniper_filter=sniper,
        bp=BacktestParams(fill_timing=ft_mode),
        cx=cx_here,
        satellite=sat_wf.catalog,
        trend_ma=tm_wf,
        require_above_trend=rat_wf,
    )

    plist = folds(
        len(lf.df),
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
    )

    if not plist:
        typer.echo("Barras insuficientes para o walk-forward solicitado.")

        raise typer.Exit(code=1)

    typer.echo(
        f"WF {symbol} {timeframe} n={len(lf.df)} folds={len(plist)} qc={lf.qc.summary}"
        f" fill={fill_timing} trend_ma={tm_wf} above_trend={rat_wf}"
    )

    folds_out: list[dict] = []
    fold_metrics: list[BacktestMetrics] = []

    for j, (_, teg) in enumerate(plist):
        filt = trades_between_bar_ix(whole, idx, teg.start, teg.stop)

        zm = summarize_trades(filt)
        fold_metrics.append(zm)

        folds_out.append(
            {
                "fold_index": j,
                "test_bar_start": teg.start,
                "test_bar_stop_exclusive": teg.stop,
                "metrics": metrics_to_dict(zm),
            }
        )

        typer.echo(
            f"  [{j}] test[{teg.start},{teg.stop}) trades={zm.trades} "
            f"PF~{zm.profit_factor:.2f} net={zm.net_pnl:.2f} WR~{zm.win_rate * 100:.1f}%"
        )

    gm = summarize_equity_curve(whole, bars=len(lf.df))
    oos = _wf_oos_summary(fold_metrics)

    typer.echo(
        f"GLOBAL trades={gm.trades} PF~{gm.profit_factor:.2f} "
        f"net={gm.net_pnl:.2f} EqEnd={gm.final_equity:.2f}"
    )
    typer.echo(
        f"OOS folds_with_trades={oos['folds_with_trades']}/{oos['folds']} "
        f"trades={oos['oos_trades']} net={float(oos['oos_net_pnl']):.2f} "
        f"WR~{float(oos['avg_win_rate']) * 100:.1f}% PF~{float(oos['avg_profit_factor']):.2f}"
    )

    if export_json:
        gt = trades_to_jsonables(whole.trades) if export_include_trades else None

        doc_wf = build_walk_forward_report(
            symbol=symbol,
            timeframe=timeframe,
            frame_rows=len(lf.df),
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            exchange_cli=exchange,
            exchange_effective=exchange or cfg_wf.exchange,
            sniper=sniper,
            fill_timing=fill_timing,
            fee_bps=fee_bps,
            slip_bps=slip_bps,
            slip_atr_frac=slip_atr_frac,
            bar_index_start_iso=idx[0].isoformat(),
            bar_index_end_iso=idx[-1].isoformat(),
            qc_summary=lf.qc.summary,
            global_metrics=gm,
            folds_payload=folds_out,
            sat=sat_wf,
            global_trades=gt,
            core_regime={"trend_ma": tm_wf, "require_above_trend": rat_wf},
            oos_summary=oos,
        )

        outp_wf = Path(export_json)

        write_json_report(outp_wf, doc_wf)

        typer.echo(f"export_json -> {outp_wf}")


@app.command("paper-once")
def paper_once(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(400, help=">= ~200 para warmup breakout"),
    sniper: bool = typer.Option(False),
    fee_bps: float | None = typer.Option(None, "--fee-bps"),
    slip_bps: float | None = typer.Option(None, "--slip-bps"),
    slip_atr_frac: float | None = typer.Option(None, "--slip-atr-frac"),
    drop_last: bool = typer.Option(True, help="Tratar última vela como incompleta"),
    state_file: str | None = typer.Option(None, "--state-file"),
    mirror_ledger: bool = typer.Option(
        False,
        "--mirror-ledger",
        help="Registrar compras/vendas paper no order ledger (sem exchange)",
    ),
    mirror_ledger_file: str | None = typer.Option(
        None,
        "--mirror-ledger-file",
        help="Ficheiro JSONL do espelho (default: AGRESSIVO_ORDER_LEDGER_PATH)",
    ),
    satellite_catalog: str | None = typer.Option(
        None,
        "--satellite-catalog",
        help="JSON de eventos; omissão = AGRESSIVO_SATELLITE_CATALOG_PATH se existir",
    ),
    trend_ma: int | None = typer.Option(
        None,
        "--trend-ma",
        help="Override AGRESSIVO_CORE_TREND_MA (5–500).",
    ),
    no_trend_filter: bool = typer.Option(
        False,
        "--no-trend-filter",
        help="Desliga exigência close>MA (ignora AGRESSIVO_CORE_REQUIRE_ABOVE_TREND).",
    ),
) -> None:
    """Um poll: snapshot causal + compra paper se sinal e carteira plana (não envia ordens)."""

    cfg_here = get_settings()

    tm_p, rat_p = _core_regime_effective(cfg_here, trend_ma, no_trend_filter)

    spath = Path(state_file) if state_file else cfg_here.paper_state_path

    lg_msg = logging.getLogger("cli")

    sat_rs = _resolve_sat_catalog(satellite_catalog, cfg_here.satellite_catalog_path)

    _echo_sat_audit(sat_rs)

    lf_here = _load(symbol, timeframe, exchange, bars, lg_msg)

    snap_here = build_snapshot(
        lf_here.df,
        lf_here.qc,
        sniper=sniper,
        drop_last_incomplete=drop_last,
        satellite=sat_rs.catalog,
        trend_ma=tm_p,
        require_above_trend=rat_p,
    )

    typer.echo(
        f"snap bar={snap_here.bar_timestamp} want_long={snap_here.wants_long} "
        f"px~{snap_here.fill_price:.6f} atr~{snap_here.atr_signal:.6f} "
        f"trend_ma={tm_p} above_trend={rat_p}"
    )
    typer.echo(f"  qc={snap_here.quality_summary}")

    bx_p = _make_cost(fee_bps=fee_bps, slip_bps=slip_bps, slip_atr_frac=slip_atr_frac)

    bp0 = BacktestParams()
    work = causal_trim(lf_here.df, drop_last_incomplete=drop_last)

    st0 = load_state(spath)

    st_px, ev_ex = maybe_exit_managed_position(st0, work, params=bp0, costs=bx_p)

    for z in ev_ex:
        typer.echo(f"  [{z.kind}] {z.detail}")

    st1, ev_buy = apply_snapshot_to_state(
        st_px,
        snap_here,
        params=bp0,
        costs=bx_p,
    )

    for z in ev_buy:
        typer.echo(f"  [{z.kind}] {z.detail}")

    _paper_mirror_report(
        enabled=mirror_ledger,
        symbol=symbol,
        events=[*ev_ex, *ev_buy],
        ledger_file=mirror_ledger_file,
        default_ledger=cfg_here.order_ledger_path,
    )

    save_state(spath, st1)

    typer.echo(
        f"state cash={st1.cash:.2f} qty={st1.qty:.8f} avg_entry={st1.avg_entry} file={spath}"
    )


@app.command("paper-close")
def paper_close(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(50),
    fee_bps: float | None = typer.Option(None, "--fee-bps"),
    slip_bps: float | None = typer.Option(None, "--slip-bps"),
    slip_atr_frac: float | None = typer.Option(None, "--slip-atr-frac"),
    drop_last: bool = typer.Option(True),
    state_file: str | None = typer.Option(None, "--state-file"),
    mirror_ledger: bool = typer.Option(
        False,
        "--mirror-ledger",
        help="Registrar venda paper no order ledger (sem exchange)",
    ),
    mirror_ledger_file: str | None = typer.Option(
        None,
        "--mirror-ledger-file",
        help="Ficheiro JSONL do espelho (default: AGRESSIVO_ORDER_LEDGER_PATH)",
    ),
) -> None:
    """Liquidar posição paper ao preço de fecho mais recente causal (ainda sem exchange)."""

    cfg_x = get_settings()

    sp = Path(state_file) if state_file else cfg_x.paper_state_path

    lg2 = logging.getLogger("cli")

    lf2 = _load(symbol, timeframe, exchange, bars, lg2)

    work = causal_trim(lf2.df, drop_last_incomplete=drop_last)

    exit_px = float(work["close"].iloc[-1])

    cx2 = _make_cost(fee_bps=fee_bps, slip_bps=slip_bps, slip_atr_frac=slip_atr_frac)

    so = load_state(sp)

    stx, evs = flatten_state(so, exit_px, cx2, atr_for_slip=None)

    for e in evs:
        typer.echo(f"  [{e.kind}] {e.detail}")

    _paper_mirror_report(
        enabled=mirror_ledger,
        symbol=symbol,
        events=list(evs),
        ledger_file=mirror_ledger_file,
        default_ledger=cfg_x.order_ledger_path,
    )

    save_state(sp, stx)

    typer.echo(f"state cash={stx.cash:.2f} qty={stx.qty} -> {sp}")


@app.command("paper-reset")
def paper_reset(state_file: str | None = typer.Option(None, "--state-file")) -> None:

    path = Path(state_file) if state_file else get_settings().paper_state_path

    save_state(path, PaperState())

    typer.echo(f"Paper state reset: {path}")


@app.command("paper-run")
def paper_run(
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h"),
    exchange: str | None = typer.Option(None, "--exchange"),
    bars: int = typer.Option(400),
    sniper: bool = typer.Option(False),
    fee_bps: float | None = typer.Option(None, "--fee-bps"),
    slip_bps: float | None = typer.Option(None, "--slip-bps"),
    slip_atr_frac: float | None = typer.Option(None, "--slip-atr-frac"),
    drop_last: bool = typer.Option(True),
    state_file: str | None = typer.Option(None, "--state-file"),
    loops: int = typer.Option(0, "--loops", help="0 = até Ctrl+C"),
    sleep_sec: float = typer.Option(60.0, "--sleep"),
    max_consecutive_failures: int = typer.Option(
        3,
        "--max-consecutive-failures",
        help="Abortar após N falhas seguidas no poll (0 desativa).",
        min=0,
    ),
    run_summary_json: str | None = typer.Option(
        None,
        "--run-summary-json",
        help="Guardar resumo operacional do loop em JSON.",
    ),
    mirror_ledger: bool = typer.Option(
        False,
        "--mirror-ledger",
        help="Registrar compras/vendas paper no order ledger (sem exchange)",
    ),
    mirror_ledger_file: str | None = typer.Option(
        None,
        "--mirror-ledger-file",
        help="Ficheiro JSONL do espelho (default: AGRESSIVO_ORDER_LEDGER_PATH)",
    ),
    satellite_catalog: str | None = typer.Option(
        None,
        "--satellite-catalog",
        help="JSON de eventos; omissão = AGRESSIVO_SATELLITE_CATALOG_PATH se existir",
    ),
    trend_ma: int | None = typer.Option(
        None,
        "--trend-ma",
        help="Override AGRESSIVO_CORE_TREND_MA (5–500).",
    ),
    no_trend_filter: bool = typer.Option(
        False,
        "--no-trend-filter",
        help="Desliga exigência close>MA (ignora AGRESSIVO_CORE_REQUIRE_ABOVE_TREND).",
    ),
) -> None:
    """

    Ciclo polling: igual a ``paper-once`` repetido (saídas automáticas + entradas).



    """

    log = logging.getLogger("cli")

    cfg = get_settings()

    tm_pr, rat_pr = _core_regime_effective(cfg, trend_ma, no_trend_filter)

    dest = Path(state_file) if state_file else cfg.paper_state_path

    sat_rs = _resolve_sat_catalog(satellite_catalog, cfg.satellite_catalog_path)

    _echo_sat_audit(sat_rs)

    bx = _make_cost(fee_bps=fee_bps, slip_bps=slip_bps, slip_atr_frac=slip_atr_frac)

    bp = BacktestParams()

    nrun = 0
    polls_ok = 0
    polls_failed = 0
    fail_streak = 0
    max_fail_streak = 0
    aborted_by_guardrail = False
    stopped_by_keyboard = False
    started_at = datetime.now(UTC)

    try:
        while loops == 0 or nrun < loops:
            nrun += 1

            typer.echo(f"--- poll #{nrun} @ {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            try:
                lf3 = _load(symbol, timeframe, exchange, bars, log)

                work3 = causal_trim(lf3.df, drop_last_incomplete=drop_last)

                snap = build_snapshot(
                    lf3.df,
                    lf3.qc,
                    sniper=sniper,
                    drop_last_incomplete=drop_last,
                    satellite=sat_rs.catalog,
                    trend_ma=tm_pr,
                    require_above_trend=rat_pr,
                )

                typer.echo(
                    f"  snap ts={snap.bar_timestamp} long={snap.wants_long} "
                    f"px~{snap.fill_price:.4f} trend_ma={tm_pr} above_trend={rat_pr}"
                )

                st_a = load_state(dest)

                st_b, ev1 = maybe_exit_managed_position(st_a, work3, params=bp, costs=bx)

                for e in ev1:
                    typer.echo(f"    [{e.kind}] {e.detail}")

                st_c, ev2 = apply_snapshot_to_state(st_b, snap, params=bp, costs=bx)

                for e in ev2:
                    typer.echo(f"    [{e.kind}] {e.detail}")

                _paper_mirror_report(
                    enabled=mirror_ledger,
                    symbol=symbol,
                    events=[*ev1, *ev2],
                    ledger_file=mirror_ledger_file,
                    default_ledger=cfg.order_ledger_path,
                )

                save_state(dest, st_c)

                typer.echo(f"  cash={st_c.cash:.2f} qty={st_c.qty:.8f} -> {dest}")
                polls_ok += 1
                if fail_streak > 0:
                    typer.echo(f"  recovered after {fail_streak} falha(s) consecutiva(s).")
                fail_streak = 0
            except Exception as exc:
                polls_failed += 1
                fail_streak += 1
                max_fail_streak = max(max_fail_streak, fail_streak)
                typer.echo(
                    f"  [poll_error] {type(exc).__name__}: {exc} "
                    f"(streak={fail_streak}/{max_consecutive_failures or 'off'})"
                )
                if _should_abort_after_failure(fail_streak, max_consecutive_failures):
                    typer.echo("Abortado: máximo de falhas consecutivas atingido.")
                    aborted_by_guardrail = True
                    raise typer.Exit(code=1) from exc

            if loops == 0 or nrun < loops:
                time.sleep(max(sleep_sec, 1.0))

    except KeyboardInterrupt:
        stopped_by_keyboard = True
        typer.echo("Encerrado por utilizador.")
    finally:
        summary = _paper_run_health_summary(
            polls_total=nrun,
            polls_ok=polls_ok,
            polls_failed=polls_failed,
            fail_streak_end=fail_streak,
            max_fail_streak=max_fail_streak,
            aborted_by_guardrail=aborted_by_guardrail,
            stopped_by_keyboard=stopped_by_keyboard,
        )
        typer.echo(
            f"RUN_SUMMARY polls={summary['polls_total']} ok={summary['polls_ok']} "
            f"failed={summary['polls_failed']} max_streak={summary['max_fail_streak']} "
            f"guardrail_abort={summary['aborted_by_guardrail']} "
            f"keyboard_stop={summary['stopped_by_keyboard']}"
        )
        if run_summary_json:
            out = Path(run_summary_json)
            doc = {
                "schema_version": 1,
                "run_type": "paper_run_summary",
                "symbol": symbol,
                "timeframe": timeframe,
                "started_at": started_at.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "summary": summary,
            }
            write_json_report(out, doc)
            typer.echo(f"run_summary_json -> {out}")


@app.command()
def reconcile(
    local_qty: float = typer.Option(..., "--local-qty"),
    exchange_qty: float = typer.Option(..., "--exchange-qty"),
    tol: float = typer.Option(1e-6, "--tol"),
) -> None:

    r = compare_position_qty(local_qty=local_qty, exchange_qty=exchange_qty, abs_tol=tol)

    typer.echo(f"ok={r.ok} delta={r.delta:.8f} ({r.message})")


@app.command("exchange-balance")
def exchange_balance_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    exchange_id: str | None = typer.Option(None, "--exchange"),
) -> None:
    """Spot: mostra free/used/total do activo-base (requer API keys no .env)."""

    cfg_here = get_settings()

    if not has_auth_config(cfg_here):
        typer.echo("Falta config: AGRESSIVO_EXCHANGE_API_KEY e AGRESSIVO_EXCHANGE_API_SECRET")

        raise typer.Exit(code=2)

    ex = authenticated_exchange(cfg_here, exchange_id=exchange_id)

    row_here = fetch_spot_balance_row(ex, symbol)

    typer.echo(
        f"{row_here.asset}: free={row_here.free:.8f} used={row_here.used:.8f} "
        f"total={row_here.total:.8f} (exchange={exchange_id or cfg_here.exchange})"
    )


@app.command("exchange-open-orders")
def exchange_open_orders_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    exchange_id: str | None = typer.Option(None, "--exchange"),
    limit: int = typer.Option(50, "--limit", help="Máximo de ordens (1–200)."),
) -> None:
    """Lista ordens abertas no par (ccxt autenticado; só leitura)."""

    if limit < 1 or limit > 200:
        typer.echo("--limit deve estar entre 1 e 200")
        raise typer.Exit(code=2)

    cfg_o = get_settings()

    if not has_auth_config(cfg_o):
        typer.echo("Falta config: AGRESSIVO_EXCHANGE_API_KEY e AGRESSIVO_EXCHANGE_API_SECRET")
        raise typer.Exit(code=2)

    ex = authenticated_exchange(cfg_o, exchange_id=exchange_id)

    try:
        rows = fetch_open_orders_for_symbol(ex, symbol, limit=limit)
    except ccxt.BaseError as e:
        typer.echo(f"Erro ccxt: {e}")
        raise typer.Exit(code=3) from e

    exid = exchange_id or cfg_o.exchange
    typer.echo(f"open_orders count={len(rows)} symbol={symbol} exchange={exid}")
    for row in rows:
        typer.echo(json.dumps(row, ensure_ascii=False, default=str))


@app.command("exchange-order-fetch")
def exchange_order_fetch_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    order_id: str = typer.Option(..., "--id"),
    exchange_id: str | None = typer.Option(None, "--exchange"),
) -> None:
    """Consulta uma ordem por id unificado (ccxt autenticado; só leitura)."""

    cfg_f = get_settings()

    if not has_auth_config(cfg_f):
        typer.echo("Falta config: AGRESSIVO_EXCHANGE_API_KEY e AGRESSIVO_EXCHANGE_API_SECRET")
        raise typer.Exit(code=2)

    ex = authenticated_exchange(cfg_f, exchange_id=exchange_id)

    try:
        row = fetch_order_by_id(ex, order_id=order_id.strip(), symbol=symbol)
    except ccxt.BaseError as e:
        typer.echo(f"Erro ccxt: {e}")
        raise typer.Exit(code=3) from e

    typer.echo(json.dumps(row, ensure_ascii=False, default=str))


@app.command("exchange-my-trades")
def exchange_my_trades_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    exchange_id: str | None = typer.Option(None, "--exchange"),
    limit: int = typer.Option(50, "--limit", help="Máximo de trades (1–500)."),
    since_ms: int | None = typer.Option(
        None,
        "--since-ms",
        help="Epoch ms opcional (ccxt ``since``).",
    ),
) -> None:
    """Trades da conta no par (ccxt ``fetch_my_trades``; só leitura)."""

    if limit < 1 or limit > 500:
        typer.echo("--limit deve estar entre 1 e 500")
        raise typer.Exit(code=2)

    cfg_mt = get_settings()

    if not has_auth_config(cfg_mt):
        typer.echo("Falta config: AGRESSIVO_EXCHANGE_API_KEY e AGRESSIVO_EXCHANGE_API_SECRET")
        raise typer.Exit(code=2)

    ex = authenticated_exchange(cfg_mt, exchange_id=exchange_id)

    try:
        rows = fetch_my_trades_for_symbol(
            ex, symbol, since_ms=since_ms, limit=limit
        )
    except ccxt.BaseError as e:
        typer.echo(f"Erro ccxt: {e}")
        raise typer.Exit(code=3) from e

    exid = exchange_id or cfg_mt.exchange
    typer.echo(f"my_trades count={len(rows)} symbol={symbol} exchange={exid}")
    for row in rows:
        typer.echo(json.dumps(row, ensure_ascii=False, default=str))


@app.command("paper-vs-exchange")
def paper_vs_exchange(
    symbol: str = typer.Option(..., "--symbol"),
    exchange_id: str | None = typer.Option(None, "--exchange"),
    state_file: str | None = typer.Option(None, "--state-file"),
    tol: float = typer.Option(1e-8, "--tol"),
    use_free: bool = typer.Option(False, help="Comparar qty paper com saldo free"),
) -> None:
    """Paper vs saldo spot na moeda base do par (não é perp/contracts)."""

    cfg_o = get_settings()

    if not has_auth_config(cfg_o):
        typer.echo("Falta config: AGRESSIVO_EXCHANGE_API_KEY e AGRESSIVO_EXCHANGE_API_SECRET")

        raise typer.Exit(code=2)

    spot = Path(state_file) if state_file else cfg_o.paper_state_path

    st_p = load_state(spot)

    exg = authenticated_exchange(cfg_o, exchange_id=exchange_id)

    rowz = fetch_spot_balance_row(exg, symbol)

    x_qty = rowz.free if use_free else rowz.total

    rpt = compare_position_qty(local_qty=st_p.qty, exchange_qty=x_qty, abs_tol=tol)

    key = "free" if use_free else "total"
    typer.echo(
        f"paper_qty={st_p.qty:.10f} exch_{key}={x_qty:.10f} ok={rpt.ok} delta={rpt.delta}"
    )

    typer.echo("Nota: total inclui todo o inventário base na spot; qty paper só simula estratégia.")


@app.command("order-ledger-tail")
def order_ledger_tail_cmd(
    last: int = typer.Option(20, "--last", "-n", help="Número de linhas tail (1–5000)."),
    ledger_file: str | None = typer.Option(
        None,
        "--ledger-file",
        help="JSONL (default: AGRESSIVO_ORDER_LEDGER_PATH)",
    ),
) -> None:
    """Mostra as últimas entradas JSON do ledger de ordens (dry-run, paper_mirror, respostas)."""

    if last < 1 or last > 5000:
        typer.echo("--last deve estar entre 1 e 5000")
        raise typer.Exit(code=2)

    cfg = get_settings()
    path = Path(ledger_file) if ledger_file else cfg.order_ledger_path

    rows = tail_jsonl_records(path, last=last)

    if not rows:
        typer.echo(f"Sem registos JSON válidos (ficheiro: {path})")
        raise typer.Exit(code=0)

    typer.echo(f"--- últimas {len(rows)} linha(s) em {path} ---")
    for row in rows:
        typer.echo(json.dumps(row, ensure_ascii=False, default=str))


@app.command("order-send")
def order_send_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    side: str = typer.Option(..., "--side", help="buy | sell"),
    qty: float = typer.Option(..., "--qty"),
    kind: str = typer.Option("market", "--kind", help="market | limit"),
    price: float | None = typer.Option(None, "--price"),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Enviar à exchange (exige AGRESSIVO_EXECUTE_ORDERS=true e API keys)",
    ),
    ledger_file: str | None = typer.Option(None, "--ledger-file"),
    fetch_confirm_cli: bool = typer.Option(
        False,
        "--fetch-confirm",
        help="Após envio real, gravar snapshot fetch_order no ledger (+ combina com .env)",
    ),
    no_fetch_confirm_cli: bool = typer.Option(
        False,
        "--no-fetch-confirm",
        help="Não executar fetch confirm mesmo que AGRESSIVO_EXECUTE_ORDER_FETCH_CONFIRM=true",
    ),
) -> None:
    """Dry-run por omissão: regista sempre em ``order_ledger_path``."""

    cfg = get_settings()

    lp = Path(ledger_file) if ledger_file else cfg.order_ledger_path

    sk = side.strip().lower()
    if sk not in ("buy", "sell"):
        typer.echo("side deve ser buy ou sell")
        raise typer.Exit(code=2)

    kk = kind.strip().lower()
    if kk not in ("market", "limit"):
        typer.echo("kind deve ser market ou limit")
        raise typer.Exit(code=2)

    if kk == "limit" and (price is None or price <= 0):
        typer.echo("Ordem limit requer --price > 0")
        raise typer.Exit(code=2)

    dry_run = not execute

    if execute and not cfg.execute_orders:
        typer.echo("AGRESSIVO_EXECUTE_ORDERS não está habilitado; abortar.")
        raise typer.Exit(code=2)

    if execute and not has_auth_config(cfg):
        typer.echo("Faltam AGRESSIVO_EXCHANGE_API_KEY / AGRESSIVO_EXCHANGE_API_SECRET")
        raise typer.Exit(code=2)

    req = OrderRequest(symbol=symbol, side=sk, kind=kk, amount=float(qty), price=price)

    fetch_do = (cfg.execute_order_fetch_confirm or fetch_confirm_cli) and not no_fetch_confirm_cli

    result = submit_order(
        cfg,
        req,
        ledger_path=lp,
        dry_run=dry_run,
        fetch_confirm=fetch_do,
    )

    typer.echo(str(result))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
