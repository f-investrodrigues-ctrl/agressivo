from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import ccxt

T = TypeVar("T")


_DEFAULT_RETRY_EXCEPTIONS = (
    ccxt.NetworkError,
    ccxt.RequestTimeout,
    ccxt.DDoSProtection,
    ccxt.ExchangeNotAvailable,
)


def call_with_exchange_retries(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    base_sleep_sec: float = 0.45,
    retry_exceptions: tuple[type[BaseException], ...] = _DEFAULT_RETRY_EXCEPTIONS,
) -> T:
    """
    Reexecuta ``fn`` em falhas típicas transitórias (rede / rate-limit / DDOS / indisponibilidade).

    Não retenta ``InvalidOrder``, ``InsufficientFunds``, erros de autenticação, etc.
    """

    tries = max(1, int(max_attempts))

    for k in range(tries):

        try:
            return fn()
        except retry_exceptions:

            if k + 1 >= tries:

                raise

            delay = float(base_sleep_sec) * float(2**k)

            time.sleep(delay)

    raise RuntimeError("unreachable")  # pragma: no cover
