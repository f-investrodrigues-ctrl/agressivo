from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ccxt


def base_asset_from_symbol(symbol: str) -> str:
    """BTC/USDT ou BTC/USDT:USDT → ``BTC``."""
    return symbol.split("/")[0]


@dataclass(frozen=True)
class SpotBalanceRow:
    asset: str
    free: float

    used: float
    total: float


def fetch_spot_balance_row(exchange: ccxt.Exchange, symbol: str) -> SpotBalanceRow:
    """Unified balance da moeda base do par spot."""
    asset = base_asset_from_symbol(symbol)
    exchange.load_markets()
    bal: dict[str, Any] = exchange.fetch_balance()
    row = bal.get(asset) or {}

    def grab(k: str) -> float:
        try:
            raw = row.get(k, 0) if isinstance(row, dict) else 0
            return float(raw or 0)
        except (TypeError, ValueError):
            return 0.0

    return SpotBalanceRow(asset=asset, free=grab("free"), used=grab("used"), total=grab("total"))
