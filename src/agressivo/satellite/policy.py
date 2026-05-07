from __future__ import annotations

import numpy as np
import pandas as pd

from agressivo.satellite.catalog import effective_end_exclusive
from agressivo.satellite.schema import SatelliteCatalogFile


def _bar_as_utc(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


def _dt_as_utc(dt) -> pd.Timestamp:
    t = pd.Timestamp(dt)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


def satellite_veto_hit_ids(
    bar_timestamp: pd.Timestamp,
    catalog: SatelliteCatalogFile | None,
) -> list[str]:
    """Ids ``veto_core`` cuja janela [start, end_exclusive) cobre o instante da barra (UTC)."""

    if catalog is None or not catalog.events:
        return []

    t_bar = _bar_as_utc(bar_timestamp)

    hit: list[str] = []
    for ev in catalog.events:
        if not ev.veto_core:
            continue
        lo = _dt_as_utc(ev.start)
        hi_exc = _dt_as_utc(effective_end_exclusive(ev))
        if lo <= t_bar < hi_exc:
            hit.append(ev.id)

    return sorted(set(hit))


def satellite_veto_label(
    bar_timestamp: pd.Timestamp,
    catalog: SatelliteCatalogFile | None,
) -> str | None:
    """Rótulo para logs quando há veto Core (Paper / métricas)."""

    ids = satellite_veto_hit_ids(bar_timestamp, catalog)
    if not ids:
        return None

    return "satellite_veto=" + ",".join(ids)


def series_satellite_entry_blocked(
    index: pd.DatetimeIndex,
    catalog: SatelliteCatalogFile | None,
) -> pd.Series:
    """
    ``True`` nas barras em que não se permite **nova** entrada long por satélite (igual ao Paper).
    Índice alinhado ao DataFrame OHLC.
    """

    if catalog is None or not catalog.events:

        return pd.Series(np.zeros(len(index), dtype=bool), index=index)

    blocked = np.fromiter(
        (bool(satellite_veto_hit_ids(t, catalog)) for t in index),
        dtype=bool,
        count=len(index),
    )

    return pd.Series(blocked, index=index)
