from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGRESSIVO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO")
    exchange: str = Field(default="binance")
    symbols: str = Field(default="BTC/USDT,ETH/USDT")
    timeframe: str = Field(default="1h")
    cache_dir: Path = Field(default=Path("data/cache"))
    paper_state_path: Path = Field(default=Path("data/paper_state.json"))
    order_ledger_path: Path = Field(default=Path("data/order_ledger.jsonl"))

    exchange_market_type: str = Field(
        default="spot",
        description="ccxt options.defaultType: spot | swap | future",
    )

    execute_orders: bool = Field(
        default=False,
        description="Porta mestre para ordens reais (também --execute na CLI)",
    )

    execute_order_retries: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Tentativas ccxt em falhas transitórias (create_order / fetch opcional)",
    )

    execute_order_retry_base_sec: float = Field(
        default=0.45,
        ge=0.05,
        le=30.0,
        description="Sleep base antes do backoff exponencial entre retries",
    )

    execute_order_fetch_confirm: bool = Field(
        default=False,
        description="Após create_order bem-sucedido, gravar snapshot fetch_order no ledger",
    )

    satellite_catalog_path: Path | None = Field(
        default=None,
        description="JSON opcional — calendário satélite (veto_core no Paper)",
    )

    core_trend_ma: int = Field(
        default=120,
        ge=5,
        le=500,
        description="Regime v1 Core: período MA de fecho (close > MA) quando require_above_trend",
    )

    core_require_above_trend: bool = Field(
        default=True,
        description="Regime v1 Core: exige close acima da MA (breakout_signals)",
    )

    exchange_api_key: str | None = Field(default=None, repr=False)
    exchange_api_secret: str | None = Field(default=None, repr=False)
    exchange_password: str | None = Field(default=None, repr=False)
    exchange_sandbox: bool = False

    @field_validator("log_level")
    @classmethod
    def log_level_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator(
        "exchange_api_key",
        "exchange_api_secret",
        "exchange_password",
        mode="before",
    )
    @classmethod
    def empty_str_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("exchange_market_type")
    @classmethod
    def normalize_market_type(cls, v: str) -> str:
        ok = frozenset({"spot", "swap", "future"})
        s = str(v).strip().lower()
        if s not in ok:
            raise ValueError(f"exchange_market_type deve ser um de {sorted(ok)}")
        return s

    @field_validator("satellite_catalog_path", mode="before")
    @classmethod
    def satellite_path_optional(cls, v: object) -> Path | None:
        if v is None:
            return None
        if isinstance(v, Path):
            ps = str(v).strip()
            return None if not ps else v
        s = str(v).strip()
        return None if not s else Path(s)

    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",") if s.strip()]


def get_settings() -> Settings:
    return Settings()
