from __future__ import annotations

from agressivo.exchange.orders import fetch_open_orders_for_symbol, fetch_order_by_id


class _Ex:
    def __init__(self) -> None:
        self.loaded = False

    def load_markets(self) -> None:
        self.loaded = True

    def fetch_open_orders(self, symbol, since=None, limit=None, params=None):
        assert self.loaded
        assert symbol == "BTC/USDT"
        return [{"id": "a", "symbol": symbol, "status": "open"}]

    def fetch_order(self, oid, symbol, params=None):
        assert self.loaded
        return {"id": oid, "symbol": symbol, "status": "closed"}


def test_fetch_open_orders_for_symbol() -> None:
    ex = _Ex()

    out = fetch_open_orders_for_symbol(ex, "BTC/USDT", limit=10)

    assert len(out) == 1
    assert out[0]["id"] == "a"


def test_fetch_order_by_id() -> None:
    ex = _Ex()

    row = fetch_order_by_id(ex, order_id="99", symbol="BTC/USDT")

    assert row["id"] == "99"
    assert row["status"] == "closed"


class _ExTrades(_Ex):
    def fetch_my_trades(self, symbol, since=None, limit=None, params=None):
        assert self.loaded
        return [{"id": "t1", "symbol": symbol}]


def test_fetch_my_trades_for_symbol() -> None:
    from agressivo.exchange.orders import fetch_my_trades_for_symbol

    ex = _ExTrades()

    rows = fetch_my_trades_for_symbol(ex, "ETH/USDT", since_ms=1, limit=5)

    assert len(rows) == 1
    assert rows[0]["id"] == "t1"
