from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SatelliteEventRecord(BaseModel):
    """
    Catalisador / janela de risco registada pelo operador ou pipeline externo.

    ``veto_core``: durante o intervalo, o Core (**paper** / snapshot causal) não abre novo long.
    """

    id: str
    title: str
    start: datetime
    end: datetime | None = None
    duration_hours: float | None = Field(
        default=None,
        ge=0.0,
        description="Sem ``end``: fim em start+duration_hours (fallback 2h).",
    )
    tags: list[str] = Field(default_factory=list)
    veto_core: bool = False

    @field_validator("id", "title")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("campo obrigatório")
        return s


class SatelliteCatalogFile(BaseModel):
    version: int = 1
    events: list[SatelliteEventRecord] = Field(default_factory=list)
