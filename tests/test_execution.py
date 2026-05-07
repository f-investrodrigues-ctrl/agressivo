from __future__ import annotations

import json

import pytest

from agressivo.config import Settings
from agressivo.execution import OrderRequest, submit_order
from agressivo.execution.ledger import append_ledger


def test_append_ledger_two_lines(tmp_path) -> None:
    pth = tmp_path / "ledger.jsonl"
    append_ledger(pth, {"x": 1})
    append_ledger(pth, {"x": 2})
    raw = pth.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 2
    r0 = json.loads(raw[0])
    assert r0["x"] == 1
    assert "_ts_iso" in r0


@pytest.mark.parametrize("execute_orders", [True, False])
def test_submit_order_dry_run_no_network(tmp_path, execute_orders: bool, monkeypatch) -> None:
    monkeypatch.delenv("AGRESSIVO_EXCHANGE_API_KEY", raising=False)
    monkeypatch.delenv("AGRESSIVO_EXCHANGE_API_SECRET", raising=False)

    ledger = tmp_path / "o.jsonl"
    cfg = Settings.model_construct(
        execute_orders=execute_orders,
        order_ledger_path=ledger,
        exchange_market_type="spot",
        exchange_api_key=None,
        exchange_api_secret=None,
        execute_order_retries=4,
        execute_order_retry_base_sec=0.45,
        execute_order_fetch_confirm=False,
    )

    req = OrderRequest(symbol="BTC/USDT", side="sell", kind="market", amount=0.001)
    out = submit_order(cfg, req, ledger_path=ledger, dry_run=True)

    assert out["status"] == "dry_run"
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_submit_live_without_keys_raises_or_drys(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGRESSIVO_EXCHANGE_API_KEY", raising=False)
    monkeypatch.delenv("AGRESSIVO_EXCHANGE_API_SECRET", raising=False)

    ledger = tmp_path / "o.jsonl"
    cfg = Settings.model_construct(
        execute_orders=True,
        order_ledger_path=ledger,
        exchange_market_type="spot",
        exchange_api_key=None,
        exchange_api_secret=None,
        execute_order_retries=4,
        execute_order_retry_base_sec=0.45,
        execute_order_fetch_confirm=False,
    )

    req = OrderRequest(symbol="BTC/USDT", side="buy", kind="market", amount=0.001)
    # dry_run False mas sem keys → comportamento igual a dry-run
    out = submit_order(cfg, req, ledger_path=ledger, dry_run=False)

    assert out["status"] == "dry_run"
