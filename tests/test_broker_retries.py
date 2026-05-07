from __future__ import annotations

import json

import ccxt
import pytest

from agressivo.config import Settings
from agressivo.execution import OrderRequest
from agressivo.execution import broker as broker_mod
from agressivo.execution import retry as retry_mod
from agressivo.execution.broker import submit_order


@pytest.fixture
def filled_settings_binance(tmp_path) -> Settings:
    return Settings.model_construct(
        execute_orders=True,
        exchange="binance",
        exchange_api_key="k",
        exchange_api_secret="s",
        exchange_market_type="spot",
        order_ledger_path=tmp_path / "ledger_placeholder.jsonl",
        execute_order_retries=4,
        execute_order_retry_base_sec=0.45,
        execute_order_fetch_confirm=False,
    )


class _FakeExc:
    def __init__(self, *, failures: int) -> None:
        self._left = failures
        self.create_order_calls: list[tuple[tuple, dict]] = []

    def load_markets(self) -> None:
        pass

    def create_order(self, *args: object, params: dict | None = None) -> dict:
        self.create_order_calls.append((args, params or {}))
        if self._left > 0:
            self._left -= 1
            raise ccxt.NetworkError("transient boom")
        return {"id": "oid-99", "status": "filled", "info": {}}


def test_retries_transient_then_ok(monkeypatch, tmp_path, filled_settings_binance) -> None:
    ledger = tmp_path / "l.jsonl"
    fak = _FakeExc(failures=2)

    monkeypatch.setattr(broker_mod, "authenticated_exchange", lambda _s: fak)

    monkeypatch.setattr(retry_mod.time, "sleep", lambda *_: None)

    req = OrderRequest(symbol="BTC/USDT", side="buy", kind="market", amount=0.01)

    out = submit_order(
        filled_settings_binance,
        req,
        ledger_path=ledger,
        dry_run=False,
    )

    assert out["status"] == "submitted"

    assert len(fak.create_order_calls) == 3

    assert fak.create_order_calls[0][1].get("newClientOrderId")

    rows = ledger.read_text(encoding="utf-8").strip().splitlines()

    assert len(rows) == 2

    tail = json.loads(rows[-1])

    assert tail.get("exchange_response", {}).get("id") == "oid-99"


def test_insufficient_funds_single_attempt(monkeypatch, tmp_path, filled_settings_binance) -> None:

    ledger = tmp_path / "l2.jsonl"

    class _Broke:
        def load_markets(self) -> None:
            pass

        create_order_calls = 0

        def create_order(self, *args, params=None):
            type(self).create_order_calls += 1
            raise ccxt.InsufficientFunds("no cash")

    br = _Broke()

    monkeypatch.setattr(broker_mod, "authenticated_exchange", lambda _s: br)

    req = OrderRequest(symbol="BTC/USDT", side="buy", kind="market", amount=0.01)

    with pytest.raises(ccxt.InsufficientFunds):
        submit_order(filled_settings_binance, req, ledger_path=ledger, dry_run=False)

    assert br.create_order_calls == 1

    rows = ledger.read_text(encoding="utf-8").strip().splitlines()

    err = json.loads(rows[-1])

    assert err.get("exchange_error_type") == "InsufficientFunds"


class _FakeWithFetch(_FakeExc):
    def __init__(self) -> None:
        super().__init__(failures=0)
        self.fetch_calls: list[tuple[str, str]] = []

    def fetch_order(self, oid: str, symbol: str, params: dict | None = None) -> dict:
        self.fetch_calls.append((oid, symbol))
        return {"id": oid, "symbol": symbol, "status": "closed"}


def test_fetch_confirm_writes_ledger(monkeypatch, tmp_path, filled_settings_binance) -> None:
    ledger = tmp_path / "lfc.jsonl"
    fak = _FakeWithFetch()

    monkeypatch.setattr(broker_mod, "authenticated_exchange", lambda _s: fak)
    monkeypatch.setattr(retry_mod.time, "sleep", lambda *_: None)

    req = OrderRequest(symbol="BTC/USDT", side="buy", kind="market", amount=0.01)

    out = submit_order(
        filled_settings_binance,
        req,
        ledger_path=ledger,
        dry_run=False,
        fetch_confirm=True,
    )

    assert fak.fetch_calls == [("oid-99", "BTC/USDT")]
    fc = out.get("fetch_confirm")
    assert fc and fc.get("id") == "oid-99"

    tail = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert tail.get("exchange_fetch_confirm", {}).get("status") == "closed"


def test_fetch_skipped_without_order_id(monkeypatch, tmp_path, filled_settings_binance) -> None:
    ledger = tmp_path / "nsk.jsonl"

    class _Bare:
        def load_markets(self) -> None:
            pass

        fetched = False

        def create_order(self, *a, params=None):

            return {"info": {}, "filled": None}

        def fetch_order(self, *a, **k):
            type(self).fetched = True
            return {}

    b = _Bare()

    monkeypatch.setattr(broker_mod, "authenticated_exchange", lambda _s: b)

    req = OrderRequest(symbol="ETH/USDT", side="sell", kind="market", amount=0.02)

    out = submit_order(
        filled_settings_binance,
        req,
        ledger_path=ledger,
        dry_run=False,
        fetch_confirm=True,
    )

    assert not b.fetched

    snap = out.get("fetch_confirm", {})
    assert snap.get("_skipped") is True

    tail = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert tail["exchange_fetch_confirm"]["_skipped"] is True
