from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agressivo.satellite.schema import SatelliteCatalogFile, SatelliteEventRecord

_DEFAULT_DURATION_H = 2.0


def effective_end_exclusive(ev: SatelliteEventRecord) -> datetime:
    """Fim efectivo inclusivo será ``end_exclusive - epsilon`` interpretado pela política."""

    if ev.end is not None:
        return ev.end
    dur = (
        float(ev.duration_hours)
        if ev.duration_hours is not None and ev.duration_hours > 0
        else _DEFAULT_DURATION_H
    )
    return ev.start + timedelta(hours=dur)


def load_satellite_catalog(path: Path) -> SatelliteCatalogFile:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    cat = SatelliteCatalogFile.model_validate(raw)

    err: list[str] = []
    for ev in cat.events:
        if not ev.veto_core:
            continue
        end_eff = effective_end_exclusive(ev)

        if end_eff <= ev.start:

            err.append(f"{ev.id}: end/duration_hours origina janela vazia")

    if err:

        raise ValueError("; ".join(err))

    return cat


def events_intersecting(
    catalog: SatelliteCatalogFile,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> list[SatelliteEventRecord]:
    """
    Eventos cuja janela [start, end_exclusive) intersecta ``[window_start_utc, window_end_utc)``.
    Todas as comparações em UTC-aware.
    """

    if window_end_utc <= window_start_utc:
        return []

    ws = window_start_utc if window_start_utc.tzinfo else window_start_utc.replace(tzinfo=UTC)
    we = window_end_utc if window_end_utc.tzinfo else window_end_utc.replace(tzinfo=UTC)

    out: list[SatelliteEventRecord] = []

    for ev in catalog.events:
        lo = ev.start if ev.start.tzinfo else ev.start.replace(tzinfo=UTC)
        hi = effective_end_exclusive(ev)
        hi = hi if hi.tzinfo else hi.replace(tzinfo=UTC)

        if hi <= ws:
            continue
        if lo >= we:
            continue

        out.append(ev)

    out.sort(key=lambda e: e.start)
    return out
