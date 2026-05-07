"""Paper: snapshot causal, estado persistido, sem ordens reais na exchange."""

from agressivo.paper.decision import PaperSnapshot, build_snapshot, causal_trim
from agressivo.paper.persist import load_state, save_state
from agressivo.paper.state import PaperState
from agressivo.paper.step import (
    apply_snapshot_to_state,
    flatten_state,
    maybe_exit_managed_position,
    qty_for_long_leg,
)

__all__ = [
    "PaperSnapshot",
    "PaperState",
    "apply_snapshot_to_state",
    "build_snapshot",
    "causal_trim",
    "flatten_state",
    "load_state",
    "maybe_exit_managed_position",
    "qty_for_long_leg",
    "save_state",
]
