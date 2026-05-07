"""Leitura autenticada opcional (ccxt) — nunca regista segredos."""

from agressivo.exchange.balance import SpotBalanceRow, fetch_spot_balance_row
from agressivo.exchange.factory import authenticated_exchange, has_auth_config
from agressivo.exchange.orders import (
    fetch_my_trades_for_symbol,
    fetch_open_orders_for_symbol,
    fetch_order_by_id,
)

__all__ = [
    "SpotBalanceRow",
    "authenticated_exchange",
    "fetch_my_trades_for_symbol",
    "fetch_open_orders_for_symbol",
    "fetch_order_by_id",
    "fetch_spot_balance_row",
    "has_auth_config",
]
