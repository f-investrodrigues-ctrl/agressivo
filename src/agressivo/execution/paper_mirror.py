from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from agressivo.execution.ledger import append_ledger

_QTY_RE = re.compile(r"qty=([-+eE\d.]+)")


def mirror_paper_trades(
    ledger_path: Path,
    symbol: str,
    events: Iterable[object],
) -> int:
    """
    Para cada ``PaperEvent`` com kind buy/sell, grava uma linha no ledger
    espelho (nunca envia ordem à exchange).
    """

    written = 0
    sym = symbol.strip()

    for ev in events:
        kind = getattr(ev, "kind", None)
        detail = getattr(ev, "detail", None)
        if kind not in ("buy", "sell") or not isinstance(detail, str):
            continue

        qty_m = _QTY_RE.search(detail)
        if qty_m is None:
            continue

        amount = float(qty_m.group(1))
        if not (amount == amount and amount > 0):
            continue

        append_ledger(
            ledger_path,
            {
                "channel": "paper_mirror",
                "symbol": sym,
                "side": kind,
                "kind": "market",
                "amount": amount,
                "paper_detail": detail,
                "note": "ledger mirror only — no ccxt.create_order",
            },
        )

        written += 1

    return written
