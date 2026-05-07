from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PaperState:
    """Carteira virtual só long; campos extras para gestão trailing/stop igual ao Core."""

    cash: float = 10_000.0
    qty: float = 0.0
    avg_entry: float | None = None
    entry_timestamp_iso: str | None = None
    trail_peak: float | None = None
    hard_stop: float | None = None

    version: int = 2

    @property
    def in_position(self) -> bool:
        return self.qty > 1e-18

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> PaperState:
        raw_tp = d.get("trail_peak")
        raw_hs = d.get("hard_stop")
        return PaperState(
            cash=float(d.get("cash", 10_000)),
            qty=float(d.get("qty", 0.0)),
            avg_entry=None if d.get("avg_entry") in (None, "null") else float(d["avg_entry"]),
            entry_timestamp_iso=d.get("entry_timestamp_iso"),
            trail_peak=None if raw_tp in (None, "null") else float(raw_tp),
            hard_stop=None if raw_hs in (None, "null") else float(raw_hs),
            version=int(d.get("version", 2)),
        )
