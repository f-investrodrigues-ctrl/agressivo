from __future__ import annotations

import json

from agressivo.execution.paper_mirror import mirror_paper_trades
from agressivo.paper.step import PaperEvent


def test_mirror_skips_non_trades(tmp_path) -> None:
    ledger = tmp_path / "m.jsonl"
    n = mirror_paper_trades(
        ledger,
        "ETH/USDT",
        [
            PaperEvent("hold", "no_signal"),
            PaperEvent("skip", "already_long"),
        ],
    )
    assert n == 0
    assert not ledger.exists()


def test_mirror_buy_sell_writes_jsonl(tmp_path) -> None:
    ledger = tmp_path / "m.jsonl"
    events = [
        PaperEvent("buy", "qty=0.5 px=10 fee=0 bar=...; stop0=9"),
        PaperEvent("sell", "qty=0.5 px=11 fee=0"),
    ]
    n = mirror_paper_trades(ledger, "BTC/USDT", events)
    assert n == 2

    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    buy = json.loads(lines[0])
    assert buy["channel"] == "paper_mirror"
    assert buy["side"] == "buy"
    assert buy["amount"] == 0.5
    assert buy["symbol"] == "BTC/USDT"

    sell = json.loads(lines[1])
    assert sell["side"] == "sell"
    assert sell["amount"] == 0.5
