from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationResult:
    local_qty: float
    exchange_qty: float
    delta: float
    ok: bool
    message: str


def compare_position_qty(
    *,
    local_qty: float,
    exchange_qty: float,
    abs_tol: float = 1e-8,
) -> ReconciliationResult:
    d = float(local_qty) - float(exchange_qty)
    ok = abs(d) <= abs_tol
    msg = "match" if ok else f"drift local_minus_exchange={d:.8f}"
    return ReconciliationResult(
        local_qty=float(local_qty),
        exchange_qty=float(exchange_qty),
        delta=d,
        ok=ok,
        message=msg,
    )
