from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SniperWeights:
    """Pontuações versionáveis conforme docs/PLANO-MAESTRO-BOT-AGRESSIVO.md §5."""

    breakout_weight: float = 1.0
    min_volume_burst: float = 1.25
    threshold: float = 1.0


def veto_check(
    *,
    spread_bps_est: float | None = None,
    max_spread_bps: float = 40.0,
    data_ok: bool = True,
    funding_abs_max: float | None = None,
    funding_latest: float | None = None,
) -> tuple[bool, str]:
    """Sem dados de livro/orderbook ⇒ ``spread`` ignorado até existir ingestão."""

    if not data_ok:
        return False, "data_quality"
    if spread_bps_est is not None and spread_bps_est > max_spread_bps:
        return False, "spread_wide"
    if funding_abs_max is not None and funding_latest is not None:
        if abs(funding_latest) > funding_abs_max:
            return False, "funding_extreme"

    return True, ""


def score_signals(
    df: pd.DataFrame, base_signal: pd.Series, w: SniperWeights | None = None
) -> pd.Series:
    """
    MVP: exige ruptura base + rajada de volume relativa (~``min_volume_burst``× média móvel).
    """

    w = w or SniperWeights()
    vol_ma = df["volume"].astype(float).rolling(48, min_periods=12).mean().replace(0, pd.NA)
    burst_ratio = df["volume"].astype(float) / vol_ma
    burst_ok = burst_ratio >= w.min_volume_burst

    return base_signal.fillna(False) & burst_ok.fillna(False)
