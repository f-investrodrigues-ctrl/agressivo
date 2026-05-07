from __future__ import annotations

from agressivo.config import Settings


def client_order_tag_from_ledger_id(ledger_id: str) -> str:
    """Tag ASCII derivada do ``ledger_id`` (UUID hex 32 chars) para idempotência na exchange."""

    h = "".join(c for c in ledger_id if c != "-")

    if len(h) >= 16:
        return h[:32].upper()

    fallback = "".join(c if c.isalnum() else "x" for c in ledger_id)

    return (fallback or "agressivoledger")[:32]


def create_order_extra_params(settings: Settings, *, client_tag: str) -> dict[str, str]:
    """
    Params opcionais no ``create_order`` do ccxt para rastrear a mesma intenção (ledger ↔ exchange).

    Chaves são exchange-específicas; parâmetros desconhecidos costumam ser ignorados pelo ccxt.
    """

    cid = settings.exchange.strip().lower()

    tag = client_tag[:36]

    if "binance" in cid:

        return {"newClientOrderId": tag[:36]}

    return {"clientOrderId": tag[:36]}
