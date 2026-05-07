from __future__ import annotations

from agressivo.cli import _doctor_snapshot
from agressivo.config import Settings


def test_doctor_snapshot_basic_fields() -> None:
    cfg = Settings(
        exchange="binance",
        exchange_market_type="spot",
        execute_orders=False,
        paper_state_path="data/paper_state.json",
        order_ledger_path="data/order_ledger.jsonl",
        satellite_catalog_path=None,
    )
    snap = _doctor_snapshot(cfg)

    assert snap["exchange"] == "binance"
    assert snap["market_type"] == "spot"
    assert snap["execute_orders"] is False
    assert snap["satellite_catalog_configured"] is False
    assert snap["satellite_catalog_ok"] is True


def test_doctor_snapshot_satellite_missing() -> None:
    cfg = Settings(
        satellite_catalog_path="data/satellite/does-not-exist.json",
    )
    snap = _doctor_snapshot(cfg)
    assert snap["satellite_catalog_configured"] is True
    assert snap["satellite_catalog_ok"] is False
