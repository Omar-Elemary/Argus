"""Argus application settings.

All configuration is environment-driven. No secrets are hard-coded.
Values are read from environment variables and, when running from the
`backend/` directory, from a local `.env` file.
"""

from functools import lru_cache
import json
import os

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

CHAIN_IDS = {"sepolia": 11155111, "mainnet": 1}


class Settings(BaseSettings):
    """Environment-based configuration for the Argus backend."""

    model_config = SettingsConfigDict(
        env_file=(".env.example", ".env"),
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )

    # Application
    app_name: str = "argus"
    version: str = "0.1.0"
    env: str = "development"
    log_level: str = "INFO"

    # Ethereum RPC
    eth_rpc_url: str = ""
    eth_network: str = "sepolia"
    eth_chain_id: int = 0

    # Optional pluggable indexer
    etherscan_api_key: str = ""

    # RPC reliability
    rpc_timeout_seconds: int = 15
    rpc_retries: int = 3
    rpc_retry_backoff: float = 0.5
    rpc_min_interval_ms: int = 60

    # Investigation bounds
    max_transactions: int = Field(default=50, ge=1)
    max_blocks_scan: int = Field(default=200, ge=1)
    max_iterations: int = Field(default=3, ge=1, le=10)
    max_tool_calls: int = Field(default=30, ge=1, le=200)

    # LLM
    llm_provider: str = "auto"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.2

    # Cursor Cloud Agents API (alternative to OpenAI-compatible endpoints)
    cursor_api_key: str = ""
    cursor_base_url: str = "https://api.cursor.com/v1"

    # Analysis thresholds
    large_tx_threshold_eth: float = 10.0
    repeated_counterparty_min: int = Field(default=3, ge=1)

    # Persistence (Phase 2 - optional)
    database_url: str = ""

    # Frontend static dir (relative to the backend working directory)
    frontend_dir: str = "../frontend"

    # Log + guard helpers -------------------------------------------------

    @computed_field  # type: ignore[misc]
    @property
    def chain_id(self) -> int:
        """Resolve the effective chain id (auto-detection is preferred)."""
        if self.eth_chain_id:
            return self.eth_chain_id
        return CHAIN_IDS.get(self.eth_network, 0)

    @computed_field  # type: ignore[misc]
    @property
    def network(self) -> str:
        return self.eth_network

    def validate_blockchain(self) -> None:
        """Fail fast with a helpful message when RPC configuration is missing."""
        if not self.eth_rpc_url:
            raise RuntimeError(
                "ETH_RPC_URL is not set. Provide an Ethereum RPC endpoint "
                "in backend/.env (see .env.example)."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings.

    Merge repo-local `backend/config.json` with environment variables.
    Environment variables take precedence so `CURSOR_API_KEY` or other
    env settings override values in the JSON file.
    """
    # Base settings loaded from environment (and any .env files)
    env_settings = Settings()

    # Look for a repo-local config file (backend/config.json)
    cfg_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    )
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                file_data = json.load(fh) or {}
            # Merge: file values first, then overlay *only* non-empty env values
            # so that default/empty env fields don't accidentally wipe file config.
            env_values = {
                k: v
                for k, v in env_settings.model_dump().items()
                if v not in (None, "")
            }
            merged = {**file_data, **env_values}
            return Settings(**merged)
        except Exception:
            # Fall back to the environment-based Settings() if parsing fails
            return env_settings
    return env_settings


def build_settings(**overrides) -> Settings:
    """Construct settings for programmatic use (used heavily by tests)."""
    return Settings(**overrides)