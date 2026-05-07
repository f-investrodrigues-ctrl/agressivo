from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OrderSide = Literal["buy", "sell"]
OrderKind = Literal["market", "limit"]


@dataclass(frozen=True)
class OrderRequest:
    """Pedido ccxt unificado simplificado."""

    symbol: str
    side: OrderSide
    kind: OrderKind
    amount: float
    price: float | None = None
