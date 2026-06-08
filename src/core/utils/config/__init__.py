"""配置模块 — pydantic-settings 应用配置管理。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """应用全局配置，从 .env 和环境变量加载。

    Usage:
        config = AppConfig()
        print(config.TUSHARE_TOKEN)
        print(config.LLM_MODEL)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Tushare ──
    TUSHARE_TOKEN: str = ""

    # ── LLM ──
    LLM_PROVIDER: str = "deepseek"      # deepseek / openai / anthropic
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.0

    # ── Data ──
    DATA_DIR: str = "./data_snapshots"
    CACHE_TTL_DAYS: int = 30

    # ── Report ──
    REPORT_OUTPUT_DIR: str = "./reports"
    REPORT_FORMAT: str = "html"         # html / md / both

    # ── Logging ──
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""
    LOG_JSON: bool = False

    # ── API Rate Limits ──
    TUSHARE_MAX_CALLS_PER_MINUTE: int = 150
    LLM_MAX_RETRIES: int = 3


__all__ = ["AppConfig"]
