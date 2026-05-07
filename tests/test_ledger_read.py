from __future__ import annotations

from pathlib import Path

from agressivo.execution.ledger_read import tail_jsonl_records


def test_tail_jsonl_empty_missing(tmp_path) -> None:
    missing = tmp_path / "nope.jsonl"
    assert tail_jsonl_records(missing, last=5) == []


def test_tail_jsonl_last_skips_invalid(tmp_path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text(
        '{"a":1}\n'
        '{"a":2}\n'
        '{"a":3}\n'
        "not-json\n"
        '{"a":4}\n',
        encoding="utf-8",
    )
    rows_tail2 = tail_jsonl_records(Path(p), last=2)
    assert [r.get("a") for r in rows_tail2] == [4]

    rows_tail4 = tail_jsonl_records(Path(p), last=4)
    assert [r.get("a") for r in rows_tail4] == [2, 3, 4]


def test_tail_jsonl_last_zero_returns_empty(tmp_path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"x":1}\n', encoding="utf-8")
    assert tail_jsonl_records(Path(p), last=0) == []
