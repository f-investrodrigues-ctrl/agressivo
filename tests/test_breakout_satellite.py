from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
from test_engine import _trend_df

from agressivo.runner.breakout_bt import breakout_run
from agressivo.satellite.policy import satellite_veto_hit_ids, series_satellite_entry_blocked
from agressivo.satellite.schema import SatelliteCatalogFile, SatelliteEventRecord


def test_series_blocked_matches_hit_ids() -> None:
    ix = pd.date_range("2026-06-01", periods=3, freq="h", tz="UTC")
    cat = SatelliteCatalogFile(
        version=1,
        events=[
            SatelliteEventRecord(
                id="win",
                title="w",
                start=datetime(2026, 6, 1, 1, tzinfo=UTC),
                end=datetime(2026, 6, 1, 3, tzinfo=UTC),
                veto_core=True,
            ),
        ],
    )
    bl = series_satellite_entry_blocked(ix, cat)

    assert not bool(bl.iloc[0])
    assert bool(bl.iloc[1])

    assert satellite_veto_hit_ids(ix[1], cat) == ["win"]

    empty = series_satellite_entry_blocked(ix, None)
    assert not empty.any()


def test_breakout_full_veto_flat_equity() -> None:
    df = _trend_df(400)

    cat = SatelliteCatalogFile(
        version=1,
        events=[
            SatelliteEventRecord(
                id="freeze",
                title="no entries",
                start=datetime(2020, 1, 1, tzinfo=UTC),
                end=datetime(2035, 1, 1, tzinfo=UTC),
                veto_core=True,
            ),
        ],
    )

    _a, _b, _sig, curve = breakout_run(df, satellite=cat)

    assert len(curve.trades) == 0
    np.testing.assert_allclose(curve.equity, 10_000.0)


def test_partial_satellite_year_veto_truncates_signals() -> None:
    df = _trend_df(500)

    cat = SatelliteCatalogFile(
        version=1,
        events=[
            SatelliteEventRecord(
                id="y2023",
                title="só veto em 2023",
                start=datetime(2023, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 1, tzinfo=UTC),
                veto_core=True,
            ),
        ],
    )

    *_, curve0 = breakout_run(df, satellite=None)
    *_, curve1 = breakout_run(df, satellite=cat)

    assert len(curve1.trades) <= len(curve0.trades)
