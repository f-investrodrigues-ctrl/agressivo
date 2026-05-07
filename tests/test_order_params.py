from __future__ import annotations

import uuid

from agressivo.config import Settings
from agressivo.execution.order_params import (
    client_order_tag_from_ledger_id,
    create_order_extra_params,
)


def test_client_order_tag_is_32_chars_upper_hex_like() -> None:
    lid = str(uuid.uuid4())

    tag = client_order_tag_from_ledger_id(lid)

    assert len(tag) == 32

    assert tag.upper() == tag

    assert all(c in "0123456789ABCDEF" for c in tag)


def test_create_order_extra_params_binance() -> None:
    cfg = Settings.model_construct(exchange="binance")

    p = create_order_extra_params(cfg, client_tag="A" * 32)

    assert p.get("newClientOrderId")


def test_create_order_extra_params_default_client_order_id() -> None:

    cfg = Settings.model_construct(exchange="kraken")

    p = create_order_extra_params(cfg, client_tag="B" * 20)

    assert p.get("clientOrderId")
