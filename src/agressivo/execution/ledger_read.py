from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any


def tail_jsonl_records(path: Path, *, last: int) -> list[dict[str, Any]]:
    """
    Últimas ``last`` linhas não vazias de um ficheiro JSONL.
    Cada linha inválida é omitida (não interrompe o resto).
    """

    if last < 1:
        return []

    if not path.is_file():
        return []

    buf: deque[str] = deque(maxlen=last)
    with path.open(encoding="utf-8", errors="replace", newline="\n") as handle:
        for line in handle:
            s = line.strip()
            if s:
                buf.append(s)

    out: list[dict[str, Any]] = []
    for raw in buf:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out
