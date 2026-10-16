"""
Configuration for the Anthropic Admin API + MongoDB integration.

DEV-PHASE NOTE (explicit, temporary): both the Anthropic Admin API key
and the MongoDB connection string are hardcoded below rather than read
from environment variables, per explicit current-phase instructions.
Both secrets are isolated to this ONE file so that:
  - swapping to env vars / a secrets manager later is a one-file change.
  - this file can be excluded from version control (.gitignore) without
    touching any other module.
No other module ever imports these constants directly — everything
else receives them only via AnthropicAdminConfig / MongoConfig and
never logs, prints, or persists them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# =============================================================================
# DEV-PHASE HARDCODED SECRETS — do not commit a real key/password to
# version control. Add this file to .gitignore if this repo is tracked.
# =============================================================================


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class AnthropicAdminConfig:
    admin_api_key: str = field(repr=False)  # never printed by dataclass repr

    base_url: str = "https://api.anthropic.com"
    anthropic_version: str = "2023-06-01"
    request_timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 10.0
    max_retries: int = 5
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    user_agent: str = "Dzopti-FinOps/1.0 (+https://dzopti.example.com)"

    def __post_init__(self) -> None:
        if not self.admin_api_key or "REPLACE_ME" in self.admin_api_key:
            raise ConfigurationError(
                "ANTHROPIC_ADMIN_API_KEY in anthropic_admin/config.py is "
                "still the placeholder value. Replace it with your real "
                "Admin API key before running the collector."
            )
        if not self.admin_api_key.startswith("sk-ant-admin"):
            raise ConfigurationError(
                "The configured key does not look like an Admin API key "
                "(expected prefix 'sk-ant-admin...')."
            )

    def __repr__(self) -> str:
        return (
            "AnthropicAdminConfig(admin_api_key='***redacted***', "
            f"base_url={self.base_url!r}, anthropic_version={self.anthropic_version!r})"
        )

    @classmethod
    def from_hardcoded(cls) -> "AnthropicAdminConfig":
        return cls(admin_api_key=ANTHROPIC_ADMIN_API_KEY)


@dataclass(frozen=True)
class MongoConfig:
    uri: str = field(repr=False)  # never printed — contains the password
    database: str = MONGODB_DATABASE
    usage_collection: str = MONGODB_USAGE_COLLECTION

    def __repr__(self) -> str:
        return f"MongoConfig(uri='***redacted***', database={self.database!r}, usage_collection={self.usage_collection!r})"

    @classmethod
    def from_hardcoded(cls) -> "MongoConfig":
        if not MONGODB_URI:
            raise ConfigurationError("MONGODB_URI in anthropic_admin/config.py is empty.")
        return cls(uri=MONGODB_URI)
