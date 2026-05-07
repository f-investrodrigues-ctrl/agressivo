from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import ccxt

from agressivo.config import Settings
from agressivo.exchange.factory import authenticated_exchange, has_auth_config
from agressivo.execution.ledger import append_ledger
from agressivo.execution.models import OrderRequest
from agressivo.execution.order_params import (
    client_order_tag_from_ledger_id,
    create_order_extra_params,
)
from agressivo.execution.retry import call_with_exchange_retries


def submit_order(
    settings: Settings,
    req: OrderRequest,
    *,
    ledger_path: Path,
    dry_run: bool,
    fetch_confirm: bool = False,
) -> dict[str, Any]:
    """
    Regista sempre no ledger.

    Só chama a exchange quando ``dry_run`` é falso, há credenciais e
    ``settings.execute_orders`` é verdadeiro.

    Com ``fetch_confirm`` e envio real: após ``create_order`` tenta ``fetch_order``
    e acrescenta ``exchange_fetch_confirm`` ao registo do ledger (e ao retorno).
    """

    safe = {
        "ledger_id": str(uuid.uuid4()),
        "symbol": req.symbol,
        "side": req.side,
        "kind": req.kind,
        "amount": req.amount,
        "price": req.price,
        "dry_run": dry_run,
        "live_ok": bool(settings.execute_orders and has_auth_config(settings)),
    }

    client_tag = client_order_tag_from_ledger_id(safe["ledger_id"])

    safe["client_order_tag"] = client_tag

    append_ledger(ledger_path, safe)

    if dry_run or not settings.execute_orders or not has_auth_config(settings):
        return {"status": "dry_run", "ledger_id": safe["ledger_id"], "client_order_tag": client_tag}

    ex: ccxt.Exchange = authenticated_exchange(settings)
    ex.load_markets()

    params = create_order_extra_params(settings, client_tag=client_tag)

    attempts = max(1, int(settings.execute_order_retries))

    backoff = float(settings.execute_order_retry_base_sec)

    def send() -> dict[str, Any]:
        if req.kind == "market":
            out = ex.create_order(
                req.symbol, "market", req.side, req.amount, None, params=params
            )
        else:
            if req.price is None or not (req.price > 0):

                raise ValueError("limit exige price > 0")
            out = ex.create_order(
                req.symbol, "limit", req.side, req.amount, req.price, params=params
            )

        return out

    try:
        result = call_with_exchange_retries(
            send, max_attempts=attempts, base_sleep_sec=backoff
        )
    except ccxt.BaseError as err:
        append_ledger(
            ledger_path,
            {
                "ledger_id": safe["ledger_id"],
                "client_order_tag": client_tag,
                "exchange_error": str(err),
                "exchange_error_type": type(err).__name__,
                "dry_run": False,
            },
        )

        raise

    payload: dict[str, Any] = {
        "ledger_id": safe["ledger_id"],
        "client_order_tag": client_tag,
        "exchange_response": result,
        "dry_run": False,
    }

    fetch_snap: dict[str, Any] | None = None

    if fetch_confirm:
        oid = result.get("id")
        raw_id = oid if oid is None else str(oid).strip()

        if raw_id:

            try:
                fetch_snap = call_with_exchange_retries(
                    lambda: ex.fetch_order(raw_id, req.symbol),
                    max_attempts=attempts,
                    base_sleep_sec=backoff,
                )
            except ccxt.BaseError as fe:

                fetch_snap = {
                    "_fetch_failed": True,
                    "exchange_error": str(fe),
                    "exchange_error_type": type(fe).__name__,
                }
        else:
            fetch_snap = {"_skipped": True, "reason": "missing_order_id_in_create_response"}

    if fetch_snap is not None:

        payload["exchange_fetch_confirm"] = fetch_snap

    append_ledger(ledger_path, payload)

    out_live: dict[str, Any] = {
        "status": "submitted",
        "ledger_id": safe["ledger_id"],
        "client_order_tag": client_tag,
        "result": result,
    }

    if fetch_snap is not None:
        out_live["fetch_confirm"] = fetch_snap

    return out_live
