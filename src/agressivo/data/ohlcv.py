from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

logger = logging.getLogger(__name__)


def ohlcv_to_dataframe(rows: list[list[Any]]) -> pd.DataFrame:
    """ccxt list of [ts, open, high, low, close, volume] → DataFrame UTC."""
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df


def fetch_ohlcv_ccxt(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    limit: int = 500,
    since_ms: int | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV via ccxt (public data, no API keys required for most exchanges)."""
    ex_class = getattr(ccxt, exchange_id)
    exchange = ex_class({"enableRateLimit": True})
    exchange.load_markets()
    params: dict[str, Any] = {}
    raw = exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        since=since_ms,
        limit=limit,
        params=params,
    )
    logger.info(
        "Fetched %s candles %s %s %s",
        len(raw),
        exchange_id,
        symbol,
        timeframe,
    )
    return ohlcv_to_dataframe(list(raw))


def cache_path(cache_dir: Path, exchange_id: str, symbol: str, timeframe: str) -> Path:
    safe = symbol.replace("/", "-")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{exchange_id}_{safe}_{timeframe}.parquet"


def load_or_fetch(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    limit: int,
    cache_dir: Path | None,
    refresh: bool = False,
) -> pd.DataFrame:
    path = cache_path(cache_dir, exchange_id, symbol, timeframe) if cache_dir else None
    if path and path.exists() and not refresh:
        return pd.read_parquet(path)
    df = fetch_ohlcv_ccxt(exchange_id, symbol, timeframe, limit=limit)
    if path:
        df.to_parquet(path)
    return df
