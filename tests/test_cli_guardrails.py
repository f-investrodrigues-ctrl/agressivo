from __future__ import annotations

from agressivo.cli import _should_abort_after_failure


def test_should_abort_after_failure_when_limit_reached() -> None:
    assert _should_abort_after_failure(3, 3)
    assert _should_abort_after_failure(4, 3)
    assert not _should_abort_after_failure(2, 3)


def test_should_abort_after_failure_disabled_when_zero_or_negative() -> None:
    assert not _should_abort_after_failure(10, 0)
    assert not _should_abort_after_failure(10, -1)
