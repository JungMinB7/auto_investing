"""Application settings via pydantic-settings.

All values are read from environment variables (or .env file).
Defaults are safe for development; override in production via environment.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API auth ────────────────────────────────────────────
    api_key: str = Field(default="dev-key", alias="API_KEY")

    # ── Kiwoom ──────────────────────────────────────────────
    kiwoom_app_key: str = Field(default="", alias="KIWOOM_APP_KEY")
    kiwoom_secret_key: str = Field(default="", alias="KIWOOM_SECRET_KEY")
    kiwoom_account_no: str = Field(default="", alias="KIWOOM_ACCOUNT_NO")
    kiwoom_is_paper: bool = Field(default=True, alias="KIWOOM_IS_PAPER")

    # ── Claude ──────────────────────────────────────────────
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # ── Discord ─────────────────────────────────────────────
    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")

    # ── Database ─────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://trading:trading@localhost:5432/trading",
        alias="DATABASE_URL",
    )

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Risk limits ─────────────────────────────────────────
    max_daily_loss_pct: float = Field(default=3.0, alias="MAX_DAILY_LOSS_PCT")
    max_position_count: int = Field(default=10, alias="MAX_POSITION_COUNT")
    max_position_size_pct: float = Field(default=10.0, alias="MAX_POSITION_SIZE_PCT")
    min_confidence: str = Field(default="MEDIUM", alias="MIN_CONFIDENCE")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
