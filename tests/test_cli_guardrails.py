from __future__ import annotations

from agressivo.cli import _paper_run_health_summary, _should_abort_after_failure


def test_should_abort_after_failure_when_limit_reached() -> None:
    assert _should_abort_after_failure(3, 3)
    assert _should_abort_after_failure(4, 3)
    assert not _should_abort_after_failure(2, 3)


def test_should_abort_after_failure_disabled_when_zero_or_negative() -> None:
    assert not _should_abort_after_failure(10, 0)
    assert not _should_abort_after_failure(10, -1)


def test_paper_run_health_summary_fields() -> None:
    s = _paper_run_health_summary(
        polls_total=7,
        polls_ok=5,
        polls_failed=2,
        fail_streak_end=1,
        max_fail_streak=2,
        aborted_by_guardrail=False,
        stopped_by_keyboard=True,
    )
    assert s["polls_total"] == 7
    assert s["polls_ok"] == 5
    assert s["polls_failed"] == 2
    assert s["fail_streak_end"] == 1
    assert s["max_fail_streak"] == 2
    assert s["aborted_by_guardrail"] is False
    assert s["stopped_by_keyboard"] is True
