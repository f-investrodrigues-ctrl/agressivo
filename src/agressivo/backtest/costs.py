from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CostParams:
    """
    Custo por perna (entrada ou saída).

    Opcionalmente acrescenta slippage ``(atr / fill_price) * slippage_atr_fraction``.
    """

    fee_rate: float = 0.0004

    slippage_rate: float = 0.0002

    slippage_atr_fraction: float = 0.05

    def leg_rate(self, fill_price: float, atr_for_slip: float | None = None) -> float:
        slip = float(self.slippage_rate)
        if (
            self.slippage_atr_fraction != 0.0
            and atr_for_slip is not None
            and np.isfinite(atr_for_slip)
            and fill_price > 0
        ):
            slip += self.slippage_atr_fraction * float(atr_for_slip) / float(fill_price)
        return float(self.fee_rate) + slip


def apply_trade_cost(notional_abs: float, leg_rate_fraction: float) -> float:
    return abs(notional_abs) * leg_rate_fraction


def roundtrip_fee_slippage(
    notional: float, c: CostParams, *, price: float, atr: float | None
) -> float:
    r = c.leg_rate(price, atr)
    return notional * (2 * r)
