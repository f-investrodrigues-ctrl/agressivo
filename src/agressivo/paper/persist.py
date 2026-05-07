from __future__ import annotations

import json
from pathlib import Path

from agressivo.paper.state import PaperState


def load_state(path: Path) -> PaperState:
    if not path.exists():
        return PaperState()

    data = json.loads(path.read_text(encoding="utf-8"))
    return PaperState.from_dict(data)


def save_state(path: Path, state: PaperState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_jsonable(), indent=2), encoding="utf-8")
