from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agressivo.satellite.catalog import load_satellite_catalog
from agressivo.satellite.schema import SatelliteCatalogFile


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SatelliteResolution:
    catalog: SatelliteCatalogFile | None
    source_path: Path | None
    sha256_hex: str | None

    def audit_line(self) -> str | None:
        if (
            self.catalog is None
            or self.source_path is None
            or self.sha256_hex is None
        ):
            return None

        sh = self.sha256_hex
        return (
            "satellite_audit "
            f"path={self.source_path.as_posix()} "
            f"sha256_full={sh} "
            f"sha256_prefix={sh[:16]} "
            f"catalog_version={self.catalog.version} "
            f"events={len(self.catalog.events)}"
        )


def satellite_from_path(path: Path) -> SatelliteResolution:
    p = Path(path)
    cat = load_satellite_catalog(p)
    return SatelliteResolution(catalog=cat, source_path=p, sha256_hex=file_sha256(p))


def satellite_from_config_path(config_path: Path | None) -> SatelliteResolution | None:
    if config_path is None:
        return None

    fp = Path(config_path)
    if not fp.is_file():
        return None

    return satellite_from_path(fp)
