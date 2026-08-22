"""
Configuration — loaded exclusively from environment variables (via a
`.env` file at the project root, using python-dotenv). Neither the
Anthropic Admin API key nor the MongoDB URI (which embeds the Mongo
password) is ever hardcoded in Python. Both are read here, in exactly
one place, and every other module receives them only through
`AnthropicAdminConfig` / `MongoConfig` — never by reading `os.environ`
themselves and never logged, printed, or persisted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from dotenv import dotenv_values

# Loads variables from a `.env` file in the current working directory (or
# any parent directory) into os.environ. A missing .env is not an error
# here — real deployments may set env vars directly instead of a file —
# missing required values are caught below with a clear message.



class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
ENV = dotenv_values(ENV_FILE)

def get_env(name: str, default: str = "") -> str:
    """Get a process environment value, falling back to the project .env."""
    value = os.environ.get(name, ENV.get(name))
    if value is None:
        return default
    return value
    

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
    user_agent: str = "Anthropic-FinOps-Integration/1.0"

    def __post_init__(self) -> None:
        if not self.admin_api_key:
            raise ConfigurationError(
                "ANTHROPIC_ADMIN_API_KEY is not set. Add it to your .env "
                "file (see .env.example) or export it in your shell."
            )
        if not self.admin_api_key.startswith("sk-ant-admin"):
            raise ConfigurationError(
                "ANTHROPIC_ADMIN_API_KEY does not look like an Admin API "
                "key (expected prefix 'sk-ant-admin...'). A regular "
                "'sk-ant-api...' key will not work against Admin endpoints."
            )

    def __repr__(self) -> str:
        return (
            "AnthropicAdminConfig(admin_api_key='***redacted***', "
            f"base_url={self.base_url!r}, anthropic_version={self.anthropic_version!r})"
        )

    @classmethod
    def from_env(cls) -> "AnthropicAdminConfig":
        return cls(
    admin_api_key=get_env("ANTHROPIC_ADMIN_API_KEY")
)


@dataclass(frozen=True)
class MongoConfig:
    """
    One collection per logical entity — never one blob document holding
    everything. Names default to the ones requested; each is still
    overridable via env var for a future multi-environment setup.
    """
    uri: str = field(repr=False)  # never printed — contains the password
    database: str = "dzops_core"

    organizations_collection: str = "anthropic_organizations"
    workspaces_collection: str = "anthropic_workspaces"
    workspace_members_collection: str = "anthropic_workspace_members"
    users_collection: str = "anthropic_users"
    api_keys_collection: str = "anthropic_api_keys"
    models_collection: str = "anthropic_models"
    usage_collection: str = "anthropic_usage"
    costs_collection: str = "anthropic_costs"
    rate_limits_collection: str = "anthropic_rate_limits"
    spend_limits_collection: str = "anthropic_spend_limits"

    def __post_init__(self) -> None:
        if not self.uri:
            raise ConfigurationError(
                "MONGODB_URI is not set. Add it to your .env file "
                "(see .env.example) or export it in your shell."
            )

    def __repr__(self) -> str:
        return f"MongoConfig(uri='***redacted***', database={self.database!r})"

    @classmethod
    def from_env(cls) -> "MongoConfig":
        def _e(name: str, default: str) -> str:
            return get_env(name, default)

        return cls(
            uri=get_env("MONGODB_URI", ""),
            database=get_env("MONGODB_DATABASE", "dzops_core"),
            organizations_collection=get_env("MONGODB_ORGANIZATIONS_COLLECTION", "anthropic_organizations"),
            workspaces_collection=get_env("MONGODB_WORKSPACES_COLLECTION", "anthropic_workspaces"),
            workspace_members_collection=get_env("MONGODB_WORKSPACE_MEMBERS_COLLECTION", "anthropic_workspace_members"),
            users_collection=get_env("MONGODB_USERS_COLLECTION", "anthropic_users"),
            api_keys_collection=get_env("MONGODB_API_KEYS_COLLECTION", "anthropic_api_keys"),
            models_collection=get_env("MONGODB_MODELS_COLLECTION", "anthropic_models"),
            usage_collection=get_env("MONGODB_USAGE_COLLECTION", "anthropic_usage"),
            costs_collection=get_env("MONGODB_COSTS_COLLECTION", "anthropic_costs"),
            rate_limits_collection=get_env("MONGODB_RATE_LIMITS_COLLECTION", "anthropic_rate_limits"),
            spend_limits_collection=get_env("MONGODB_SPEND_LIMITS_COLLECTION", "anthropic_spend_limits"),
        )


@dataclass(frozen=True)
class RabbitMQConfig:
    """Connection and durable topology settings for collection jobs."""

    url: str = field(repr=False)
    queue: str = "anthropic_finops_collection"
    dead_letter_exchange: str = "anthropic_finops_collection.dlx"
    dead_letter_queue: str = "anthropic_finops_collection.dead"

    def __post_init__(self) -> None:
        if not self.url:
            raise ConfigurationError(
                "RABBITMQ_URL is not set. Add it to your .env file or export it."
            )

    def __repr__(self) -> str:
        return f"RabbitMQConfig(url='***redacted***', queue={self.queue!r})"

    @classmethod
    def from_env(cls) -> "RabbitMQConfig":
        return cls(
            url=get_env("RABBITMQ_URL"),
            queue=get_env("RABBITMQ_QUEUE", "anthropic_finops_collection"),
            dead_letter_exchange=get_env(
                "RABBITMQ_DEAD_LETTER_EXCHANGE", "anthropic_finops_collection.dlx"
            ),
            dead_letter_queue=get_env(
                "RABBITMQ_DEAD_LETTER_QUEUE", "anthropic_finops_collection.dead"
            ),
        )


@dataclass(frozen=True)
class SchedulerConfig:
    interval_seconds: int = 3600
    state_file: str = ".scheduler_state.json"
    backfill_start: str = ""
    backfill_end: str = ""

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        return cls(
            interval_seconds=int(get_env("COLLECTION_INTERVAL_SECONDS", "3600")),
            state_file=get_env("SCHEDULER_STATE_FILE", ".scheduler_state.json"),
            backfill_start=get_env("BACKFILL_START"),
            backfill_end=get_env("BACKFILL_END"),
        )


@dataclass(frozen=True)
class MongoRetryConfig:
    max_retries: int = 5
    base_seconds: float = 2.0
    max_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "MongoRetryConfig":
        return cls(
            max_retries=int(get_env("MONGODB_MAX_RETRIES", "5")),
            base_seconds=float(get_env("MONGODB_RETRY_BASE_SECONDS", "2")),
            max_seconds=float(get_env("MONGODB_RETRY_MAX_SECONDS", "60")),
        )
