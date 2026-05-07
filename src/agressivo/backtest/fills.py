from __future__ import annotations

from typing import Literal

"""Modelo de preenchimento (alinhado ao plano mestre — evitar lookahead otimista)."""

FillTiming = Literal["close_same_bar", "next_bar_open"]
