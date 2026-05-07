from __future__ import annotations

import logging

import ccxt

from agressivo.config import Settings

logger = logging.getLogger(__name__)


def has_auth_config(settings: Settings) -> bool:
    return bool(settings.exchange_api_key and settings.exchange_api_secret)


def authenticated_exchange(
    settings: Settings,
    *,
    exchange_id: str | None = None,
) -> ccxt.Exchange:
    """
    Instância ccxt com API keys (se definidas).

    ``set_sandbox_mode`` quando ``exchange_sandbox`` e a exchange suportar.
    """

    ex_id = exchange_id if exchange_id else settings.exchange
    ex_class = getattr(ccxt, ex_id)
    opts: dict = {
        "enableRateLimit": True,
        "options": {"defaultType": settings.exchange_market_type},
    }
    if has_auth_config(settings):
        opts["apiKey"] = settings.exchange_api_key
        opts["secret"] = settings.exchange_api_secret
        if settings.exchange_password:
            opts["password"] = settings.exchange_password

    ex = ex_class(opts)
    if settings.exchange_sandbox:
        try:
            ex.set_sandbox_mode(True)
        except Exception as e:
            logger.warning("Sandbox não suportado ou falhou (%s): %s", ex_id, e)
    return ex
