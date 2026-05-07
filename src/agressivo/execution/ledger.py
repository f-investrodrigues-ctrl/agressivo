from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def append_ledger(path: Path, record: dict[str, Any]) -> None:
    """Uma linha JSON por entrada (replay / auditoria)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    blob = dict(record)
    blob.setdefault("_ts_iso", datetime.now(UTC).isoformat())
    line = json.dumps(blob, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
