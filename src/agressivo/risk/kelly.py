from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KellyInputs:
    """Entradas simples caso binário médio observado."""

    win_rate: float  # ∈ (0,1)
    win_mean: float
    lose_mean_abs: float
    payoff_ratio_b: float | None = None  # opcional média_win / média_loss

    fractional: float = 0.5


def fractional_kelly(inp: KellyInputs) -> float:
    """
    Fracção de Kelly ``f* × inp.fractional`` para payoff binário aprox.

    Formula classica … f* … ( bp - q ) / b
    ``b``: payoff/pag médio quando ``payoff_ratio_b`` é ``None`` → ``Win_mean / Lose_mean``.
    """

    p = inp.win_rate
    q = 1 - p
    b = (
        inp.payoff_ratio_b
        if inp.payoff_ratio_b is not None
        else (inp.win_mean / inp.lose_mean_abs if inp.lose_mean_abs != 0 else 0)
    )

    fk = float((b * p - q) / b) if b > 0 else 0
    fk = max(0.0, fk)
    return max(0.0, fk * inp.fractional)
