from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowSpec:
    """Um bloco índices ``[start, stop)`` em número de barras."""

    start: int
    stop: int


def folds(
    n_bars: int,
    *,
    train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    min_remainder_drop: bool = True,
) -> list[tuple[WindowSpec, WindowSpec]]:
    """
    Gera folds (train, test) encadeados.

    Por omissão ``step_bars=test_bars`` (janelas contíguas típicas de walk-forward).
    Descarta o final se não couber um teste inteiro quando ``min_remainder_drop``.
    """

    step = step_bars or test_bars
    folds_out: list[tuple[WindowSpec, WindowSpec]] = []
    t0 = 0

    while True:
        tr_start = t0
        tr_stop = tr_start + train_bars
        te_start = tr_stop
        te_stop = te_start + test_bars

        if te_stop > n_bars:
            if not min_remainder_drop and te_stop - n_bars > 0 and te_start < n_bars:
                folds_out.append(
                    (
                        WindowSpec(tr_start, tr_stop),
                        WindowSpec(te_start, n_bars),
                    )
                )
            break

        folds_out.append(
            (
                WindowSpec(tr_start, tr_stop),
                WindowSpec(te_start, te_stop),
            )
        )
        t0 += step

    return folds_out
