"""Satélite event-driven — calendário versionado em JSON (planeado na Fase 6 do PLANO)."""

from agressivo.satellite.catalog import (
    effective_end_exclusive,
    events_intersecting,
    load_satellite_catalog,
)
from agressivo.satellite.policy import (
    satellite_veto_hit_ids,
    satellite_veto_label,
    series_satellite_entry_blocked,
)
from agressivo.satellite.resolve import (
    SatelliteResolution,
    file_sha256,
    satellite_from_config_path,
    satellite_from_path,
)
from agressivo.satellite.schema import SatelliteCatalogFile

__all__ = [
    "SatelliteCatalogFile",
    "SatelliteResolution",
    "effective_end_exclusive",
    "events_intersecting",
    "file_sha256",
    "load_satellite_catalog",
    "satellite_from_config_path",
    "satellite_from_path",
    "series_satellite_entry_blocked",
    "satellite_veto_hit_ids",
    "satellite_veto_label",
]
