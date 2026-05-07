from __future__ import annotations

from agressivo.risk.kelly import KellyInputs, fractional_kelly


def test_fractional_kelly_positive_edge() -> None:
    fk = fractional_kelly(
        KellyInputs(
            win_rate=0.55,
            win_mean=100.0,
            lose_mean_abs=50.0,
            fractional=0.5,
        )
    )

    assert fk > 0.0


def test_fractional_kelly_zero_when_no_edge() -> None:
    fk = fractional_kelly(
        KellyInputs(
            win_rate=0.4,
            win_mean=10.0,
            lose_mean_abs=20.0,
            fractional=0.5,
        )
    )

    assert fk == 0.0
