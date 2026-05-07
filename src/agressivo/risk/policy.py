from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRiskBudget:
    """Parâmetros declarativos (plano mestre); depois mover para env/live."""

    risk_pct_daily_stop: float = 0.05
    risk_pct_weekly_stop: float = 0.10
    leverage_cap: float = 5.0
    concurrent_loss_pause: int = 3
