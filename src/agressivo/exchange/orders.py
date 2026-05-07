from __future__ import annotations

from typing import Any

import ccxt


def fetch_open_orders_for_symbol(
    ex: ccxt.Exchange,
    symbol: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Ordens abertas no par unificado (ccxt)."""

    ex.load_markets()

    return list(ex.fetch_open_orders(symbol, limit=limit))


def fetch_order_by_id(ex: ccxt.Exchange, *, order_id: str, symbol: str) -> dict[str, Any]:
    """Estado actual da ordem por id unificado + símbolo."""

    ex.load_markets()

    return ex.fetch_order(order_id, symbol)


def fetch_my_trades_for_symbol(
    ex: ccxt.Exchange,
    symbol: str,
    *,
    since_ms: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Histórico recente de trades da conta no par (ccxt ``fetch_my_trades``)."""

    ex.load_markets()

    return list(ex.fetch_my_trades(symbol, since=since_ms, limit=limit))
