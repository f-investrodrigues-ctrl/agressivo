from __future__ import annotations

import hashlib
from pathlib import Path

from agressivo.satellite.resolve import (
    SatelliteResolution,
    file_sha256,
    satellite_from_config_path,
    satellite_from_path,
)


def test_file_sha256_matches_stdlib(tmp_path) -> None:
    raw = b'{"version": 1}'
    fp = tmp_path / "small.json"

    fp.write_bytes(raw)

    assert file_sha256(fp) == hashlib.sha256(raw).hexdigest()


def test_satellite_from_path_audit_roundtrip() -> None:

    root = Path(__file__).resolve().parents[1]

    p = root / "data" / "satellite" / "catalog.example.json"

    res = satellite_from_path(p)

    assert res.catalog is not None
    assert res.source_path == p
    assert res.sha256_hex and len(res.sha256_hex) == 64

    audit = res.audit_line()

    assert audit is not None
    assert "sha256_full=" in audit
    assert "events=" in audit


def test_satellite_resolution_empty_has_no_audit() -> None:

    bare = SatelliteResolution(None, None, None)

    assert bare.audit_line() is None


def test_satellite_from_config_missing() -> None:

    assert satellite_from_config_path(None) is None

    assert satellite_from_config_path(Path("/nonexistent/satellite_xx.json")) is None
