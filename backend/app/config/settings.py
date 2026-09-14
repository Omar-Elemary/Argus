"""Fellows application settings.

All configuration is environment-driven. No secrets are hard-coded.
Values are read from environment variables and, when running from the
`backend/` directory, from a local `.env` file.

Evolved from the Argus Settings object: same load/merge rules, Fellows domain.
"""

import json
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based configuration for the Fellows backend."""

    model_config = SettingsConfigDict(
        env_file=(".env.example", ".env"),
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )

    app_name: str = "fellows"
    version: str = "0.1.0"
    env: str = "development"
    log_level: str = "INFO"

    secret_key: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, ge=5)
    jwt_algorithm: str = "HS256"

    database_url: str = "sqlite+aiosqlite:///./fellows.db"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000"

    # Orchestration budgets (enforced when Phase 4 executes graphs)
    max_iterations: int = Field(default=8, ge=1, le=50)
    max_tool_calls: int = Field(default=40, ge=1, le=200)

    # LLM — reused provider switch from Argus
    llm_provider: str = "auto"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.2

    cursor_api_key: str = ""
    cursor_base_url: str = "https://api.cursor.com/v0"
    cursor_repository: str = ""

    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings.

    Merge repo-local `backend/config.json` with environment variables.
    Environment variables take precedence so API keys override the JSON file.
    """
    env_settings = Settings()

    cfg_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    )
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                file_data = json.load(fh) or {}
            env_values = {
                k: v for k, v in env_settings.model_dump().items() if v not in (None, "")
            }
            merged = {**file_data, **env_values}
            return Settings(**merged)
        except Exception:  # noqa: BLE001
            return env_settings
    return env_settings


def build_settings(**overrides: object) -> Settings:
    """Construct settings for programmatic use (used heavily by tests)."""
    return Settings(**overrides)  # type: ignore[arg-type]
