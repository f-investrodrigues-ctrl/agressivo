from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agressivo.data.quality import DataQualityReport
from agressivo.satellite.policy import satellite_veto_label
from agressivo.satellite.schema import SatelliteCatalogFile
from agressivo.strategy.core_breakout import breakout_signals
from agressivo.strategy.sniper import score_signals


def causal_trim(df: pd.DataFrame, *, drop_last_incomplete: bool) -> pd.DataFrame:
    """Remove a última vela antes de usar OHLC causal (streaming)."""

    if drop_last_incomplete and len(df) > 1:
        return df.iloc[:-1].copy()

    return df.copy()


@dataclass(frozen=True)
class PaperSnapshot:
    """Última avaliação causal (barra de sinal + preço de execução papel)."""

    bar_timestamp: pd.Timestamp
    """Timestamp da barra usada para o sinal (fecho)."""

    fill_price: float
    """Referência de mercado paper (fecho da barra mais recente trabalhada)."""

    atr_signal: float

    wants_long: bool

    data_ok: bool

    quality_summary: str


def build_snapshot(
    df: pd.DataFrame,
    qc: DataQualityReport,
    *,
    sniper: bool,
    drop_last_incomplete: bool = True,
    satellite: SatelliteCatalogFile | None = None,
    trend_ma: int | None = None,
    require_above_trend: bool | None = None,
) -> PaperSnapshot:
    """
    Se ``drop_last_incomplete`` avalia o sinal na **penúltima** barra disponível

    (útil quando a última velas ainda está a formar na API).
    """

    src = df.iloc[:-1].copy() if drop_last_incomplete and len(df) > 1 else df

    tm_warm = int(trend_ma) if trend_ma is not None else 120

    # Warmup mínimo (MA de tendência + swing no Core v1)
    need = max(140, tm_warm + 25)
    if len(src) < need:
        last_ts = src.index[-1] if len(src) else df.index[-1]
        last_c = float(src["close"].iloc[-1]) if len(src) else float("nan")
        return PaperSnapshot(
            bar_timestamp=last_ts,
            fill_price=last_c,
            atr_signal=float("nan"),
            wants_long=False,
            data_ok=qc.ok,
            quality_summary=f"{qc.summary}; warmup<{need}bars",
        )

    sig_kw: dict = {}
    if trend_ma is not None:
        sig_kw["trend_ma"] = int(trend_ma)
    if require_above_trend is not None:
        sig_kw["require_above_trend"] = bool(require_above_trend)

    atr_raw, _c, raw_sig = breakout_signals(src, **sig_kw)

    final_sig = score_signals(src, raw_sig) if sniper else raw_sig

    i_signal = src.index[-1]
    atr_val = float(atr_raw.loc[i_signal])

    flag = bool(final_sig.loc[i_signal])

    last_px_here = float(src["close"].iloc[-1])

    sat_lab = satellite_veto_label(i_signal, satellite)

    parts = [qc.summary]
    if sat_lab:
        parts.append(sat_lab)
    qc_line = "; ".join(parts)

    atr_ok = atr_val == atr_val and atr_val > 0

    return PaperSnapshot(
        bar_timestamp=i_signal,
        fill_price=last_px_here,
        atr_signal=atr_val,
        wants_long=flag and atr_ok and sat_lab is None,
        data_ok=qc.ok,
        quality_summary=qc_line,
    )
