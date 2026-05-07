from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from agressivo.satellite.catalog import (
    effective_end_exclusive,
    events_intersecting,
    load_satellite_catalog,
)
from agressivo.satellite.policy import satellite_veto_label
from agressivo.satellite.schema import SatelliteCatalogFile, SatelliteEventRecord


def test_load_example_catalog(project_root: Path) -> None:
    p = project_root / "data" / "satellite" / "catalog.example.json"
    cat = load_satellite_catalog(p)
    assert cat.version == 1
    assert len(cat.events) >= 1


def test_veto_label_honours_veto_core_only(project_root: Path) -> None:
    p = project_root / "data" / "satellite" / "catalog.example.json"
    cat = load_satellite_catalog(p)
    lb = satellite_veto_label(pd.Timestamp("2026-06-01T14:00:00+00:00"), cat)
    assert lb is not None
    assert "example-macro-quiet" in lb

    no = satellite_veto_label(pd.Timestamp("2026-06-10T10:00:00+00:00"), cat)
    assert no is None


def test_events_intersecting_window(project_root: Path) -> None:
    p = project_root / "data" / "satellite" / "catalog.example.json"
    cat = load_satellite_catalog(p)
    w0 = datetime(2026, 5, 1, tzinfo=UTC)
    w1 = datetime(2026, 7, 1, tzinfo=UTC)
    evs = events_intersecting(cat, w0, w1)
    ids = {e.id for e in evs}
    assert len(ids) == 3
    assert "example-may-demo" in ids
    assert "example-macro-quiet" in ids
    assert "example-unlock-info" in ids


def test_effective_end_exclusive_uses_duration_hours() -> None:
    ev = SatelliteEventRecord(
        id="d",
        title="t",
        start=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        end=None,
        duration_hours=3.0,
        veto_core=True,
    )
    endx = effective_end_exclusive(ev)
    assert endx == datetime(2026, 1, 1, 13, 0, tzinfo=UTC)


def test_load_rejects_bad_veto_window(tmp_path) -> None:
    bad = SatelliteCatalogFile(
        version=1,
        events=[
            SatelliteEventRecord(
                id="bad",
                title="x",
                start=datetime(2026, 1, 2, tzinfo=UTC),
                end=datetime(2026, 1, 1, tzinfo=UTC),
                veto_core=True,
            )
        ],
    )
    fp = tmp_path / "bad.json"
    fp.write_text(bad.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="vazia"):
        load_satellite_catalog(fp)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_intersecting_returns_empty_on_inverted_window(project_root: Path) -> None:
    cat = load_satellite_catalog(project_root / "data" / "satellite" / "catalog.example.json")
    t0 = datetime(2026, 8, 1, tzinfo=UTC)
    t1 = datetime(2026, 7, 1, tzinfo=UTC)
    assert events_intersecting(cat, t0, t1) == []
