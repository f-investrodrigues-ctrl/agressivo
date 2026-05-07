from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DataQualityReport:
    bars: int
    duplicate_ts: int
    gap_count: int
    max_gap_bars: int
    non_monotonic: bool
    na_rows: int
    ok: bool
    summary: str

    @staticmethod
    def from_checks(
        *,
        bars: int,
        duplicate_ts: int,
        gap_count: int,
        max_gap_bars: int,
        non_monotonic: bool,
        na_rows: int,
        expected_freq: pd.Timedelta | None,
    ) -> DataQualityReport:
        # Gaps são informativos; falha dura só em dados claramente corrompidos.
        ok = duplicate_ts == 0 and not non_monotonic and na_rows == 0
        parts = [
            f"bars={bars}",
            f"dup_ts={duplicate_ts}",
            f"gaps={gap_count}",
            f"max_gap={max_gap_bars}",
            f"bad_order={non_monotonic}",
            f"na={na_rows}",
        ]
        summary = "; ".join(parts) + ("; OK" if ok else "; REVIEW")
        return DataQualityReport(
            bars=bars,
            duplicate_ts=duplicate_ts,
            gap_count=gap_count,
            max_gap_bars=max_gap_bars,
            non_monotonic=non_monotonic,
            na_rows=na_rows,
            ok=ok,
            summary=summary,
        )


def assess_ohlcv_quality(df: pd.DataFrame, expected_freq: str | None = None) -> DataQualityReport:
    """
    Basic integrity checks on OHLCV indexed by UTC timestamp.
    Gaps counted as multiples of inferred median bar delta (if freq not provided).
    """
    if df.empty:
        return DataQualityReport(
            bars=0,
            duplicate_ts=0,
            gap_count=0,
            max_gap_bars=0,
            non_monotonic=False,
            na_rows=0,
            ok=True,
            summary="empty",
        )

    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be DatetimeIndex")

    duplicate_ts = int(idx.duplicated().sum())
    non_monotonic = not bool(idx.is_monotonic_increasing)

    na_rows = int(df[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum())

    if expected_freq:
        ef = pd.Timedelta(expected_freq)
    else:
        deltas = idx.to_series().diff().dropna()
        ef = deltas.median() if not deltas.empty else None

    gap_count = 0
    max_gap_bars = 0
    if ef is not None and ef > pd.Timedelta(0):
        diffs = idx.to_series().diff().dropna()
        multiples = diffs / ef
        gaps = multiples[multiples > 1.05]  # allow small jitter
        gap_count = int(gaps.shape[0])
        max_gap_bars = int(gaps.max()) if gap_count else 0

    return DataQualityReport.from_checks(
        bars=len(df),
        duplicate_ts=duplicate_ts,
        gap_count=gap_count,
        max_gap_bars=max_gap_bars,
        non_monotonic=non_monotonic,
        na_rows=na_rows,
        expected_freq=ef,
    )
