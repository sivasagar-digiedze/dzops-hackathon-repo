"""
MongoDB repository — one collection per logical entity, never one blob
document. Writes ONLY to the ten `anthropic_*` collections inside the
`dzops_core` database (both configurable via .env / MongoConfig).
Nothing else on the shared Mongo server — no other collection, no other
database — is ever read, written, dropped, or reindexed by this module.

Collections and their _id strategy (all deterministic, so re-running the
collector upserts instead of duplicating):

    anthropic_organizations       _id = organization_id
    anthropic_workspaces           _id = workspace_id
    anthropic_workspace_members     _id = f"{workspace_id}:{user_id}"
    anthropic_users                  _id = user_id
    anthropic_api_keys                _id = api_key_id
    anthropic_models                   _id = model_id
    anthropic_usage                     _id = sha256(provider, organization_id,
                                            period_start, period_end, workspace_id,
                                            api_key_id, model, service_tier, context_window)
    anthropic_costs                      _id = sha256(provider, organization_id,
                                            period_start, period_end, workspace_id,
                                            model, service_tier, context_window)
                                            — no api_key_id: Anthropic's Cost API
                                            never returns that dimension.
    anthropic_rate_limits                 _id = sha256(workspace_id or "organization",
                                            group_type) — a point-in-time
                                            configuration snapshot, overwritten in
                                            place rather than accumulated as a
                                            time series (rate limits aren't
                                            dated events, they're current config).
    anthropic_spend_limits                  _id = spend_limit_id when supported,
                                            else the fixed id "_status" holding
                                            {"supported": false, "reason": "..."}
                                            so the collection still documents WHY
                                            it's empty rather than looking broken.

`None` fields (Anthropic genuinely returned no workspace/key/etc.) hash
to a stable, distinct value and are stored as `null` — never coerced to
a placeholder string here. The `null -> "Default"` translation happens
only in the Streamlit presentation layer (see streamlit_app/app.py),
never in this repository or in MongoDB itself.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Iterable

from ..config import MongoConfig
from ..models.normalized import (
    ApiKeyMetadata,
    CostRecord,
    ModelInfo,
    Organization,
    RateLimitEntry,
    SpendLimitsResult,
    UsageRecord,
    User,
    Workspace,
    WorkspaceMember,
)

logger = logging.getLogger("anthropic_admin.repository.mongo")

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
except ImportError:  # pragma: no cover - motor is an optional dependency until this repo is used
    AsyncIOMotorClient = Any  # type: ignore
    AsyncIOMotorDatabase = Any  # type: ignore


def _stable_hash(*parts: Any) -> str:
    normalized = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def usage_record_id(record: UsageRecord) -> str:
    # Include provider_data to ensure records differing only by provider-specific
    # dimensions (service_account_id, inference_geo, context_window, etc.)
    # hash to distinct IDs.
    provider_data = record.provider_data or {}
    return _stable_hash(
        record.provider, record.organization_id, record.period_start, record.period_end,
        record.workspace_id, record.api_key_id, record.model, record.service_tier,
        json.dumps(provider_data, sort_keys=True, default=str),
    )


def cost_record_id(record: CostRecord) -> str:
    # Include provider_data (cost_type, token_type, service_account_id, etc.)
    # so that separate line-items returned by Anthropic remain distinct.
    provider_data = record.provider_data or {}
    return _stable_hash(
        record.provider, record.organization_id, record.period_start, record.period_end,
        record.workspace_id, record.model, record.service_tier,
        json.dumps(provider_data, sort_keys=True, default=str),
    )


def rate_limit_id(record: RateLimitEntry) -> str:
    return _stable_hash(record.workspace_id or "organization", record.group_type)


class MongoAnthropicRepository:
    """Async repository scoped to exactly the ten anthropic_* collections."""

    def __init__(self, config: MongoConfig) -> None:
        self._config = config
        self._client: "AsyncIOMotorClient" = AsyncIOMotorClient(config.uri)
        self._db: "AsyncIOMotorDatabase" = self._client[config.database]

        self._organizations = self._db[config.organizations_collection]
        self._workspaces = self._db[config.workspaces_collection]
        self._workspace_members = self._db[config.workspace_members_collection]
        self._users = self._db[config.users_collection]
        self._api_keys = self._db[config.api_keys_collection]
        self._models = self._db[config.models_collection]
        self._usage = self._db[config.usage_collection]
        self._costs = self._db[config.costs_collection]
        self._rate_limits = self._db[config.rate_limits_collection]
        self._spend_limits = self._db[config.spend_limits_collection]

    async def close(self) -> None:
        self._client.close()

    async def ping(self) -> bool:
        """Connectivity check — never logs the connection string."""
        try:
            await self._client.admin.command("ping")
            logger.info("anthropic_admin.mongo.ping_ok", extra={"mg_database": self._config.database})
            return True
        except Exception as exc:  # noqa: BLE001 - report, don't leak the URI
            logger.error("anthropic_admin.mongo.ping_failed", extra={"mg_error_type": type(exc).__name__})
            return False

    async def ensure_indexes(self) -> None:
        """
        provider / organization_id / workspace_id / api_key_id / model /
        period_start indexes on the time-series collections (usage, costs)
        — every dashboard query filters on a date range first, then
        optionally narrows by workspace/key/model, so those are the
        columns that need to resist a full collection scan. A compound
        (organization_id, period_start, workspace_id) index on both
        matches the dashboard's actual default query shape.
        """
        await self._usage.create_index("provider")
        await self._usage.create_index("organization_id")
        await self._usage.create_index("workspace_id")
        await self._usage.create_index("api_key_id")
        await self._usage.create_index("model")
        await self._usage.create_index("period_start")
        await self._usage.create_index([("organization_id", 1), ("period_start", -1), ("workspace_id", 1)])

        await self._costs.create_index("provider")
        await self._costs.create_index("organization_id")
        await self._costs.create_index("workspace_id")
        await self._costs.create_index("model")
        await self._costs.create_index("period_start")
        await self._costs.create_index([("organization_id", 1), ("period_start", -1), ("workspace_id", 1)])

        # Do NOT create indexes for non-usage/non-cost collections since
        # we no longer persist those entities to MongoDB per requirements.

        logger.info("anthropic_admin.mongo.indexes_ensured")

    async def _upsert_one(self, collection, doc_id: Any, doc: dict[str, Any]) -> bool:
        """Returns True if this was a new insert, False if it updated an existing document."""
        result = await collection.update_one({"_id": doc_id}, {"$set": doc}, upsert=True)
        return result.upserted_id is not None

    async def _upsert_many(self, collection, items: Iterable[tuple[Any, dict[str, Any]]], label: str) -> dict[str, int]:
        matched, upserted = 0, 0
        for doc_id, doc in items:
            # Ensure every record has created_at/deleted_at as required by storage schema
            if "created_at" not in doc:
                from datetime import datetime, timezone
                doc["created_at"] = datetime.now(timezone.utc).isoformat()
            if "deleted_at" not in doc:
                doc["deleted_at"] = None
            is_new = await self._upsert_one(collection, doc_id, doc)
            upserted += 1 if is_new else 0
            matched += 0 if is_new else 1
        logger.info(
            f"anthropic_admin.mongo.{label}_upsert_done",
            extra={"mg_matched": matched, "mg_upserted": upserted, "mg_total": matched + upserted},
        )
        return {"matched": matched, "upserted": upserted, "total": matched + upserted}

    # -- one method per entity -------------------------------------------------

    async def upsert_organization(self, record: Organization) -> None:
        # Persisting organizations is disabled per requirement (only usage and costs stored).
        return None

    async def upsert_workspaces(self, records: Iterable[Workspace]) -> dict[str, int]:
        # Disabled: do not persist workspaces to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_workspace_members(self, records: Iterable[WorkspaceMember]) -> dict[str, int]:
        # Disabled: do not persist workspace members to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_users(self, records: Iterable[User]) -> dict[str, int]:
        # Disabled: do not persist users to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_api_keys(self, records: Iterable[ApiKeyMetadata]) -> dict[str, int]:
        # Disabled: do not persist API keys to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_models(self, records: Iterable[ModelInfo]) -> dict[str, int]:
        # Disabled: do not persist models to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_usage_records(self, records: Iterable[UsageRecord]) -> dict[str, int]:
        items = []
        for r in records:
            doc = r.to_dict()
            doc["total_tokens"] = (
                (r.input_tokens or 0) + (r.output_tokens or 0)
                + (r.cache_creation_input_tokens or 0) + (r.cache_read_input_tokens or 0)
            )
            items.append((usage_record_id(r), doc))
        return await self._upsert_many(self._usage, items, "usage")

    async def upsert_cost_records(self, records: Iterable[CostRecord]) -> dict[str, int]:
        items = [(cost_record_id(r), r.to_dict()) for r in records]
        return await self._upsert_many(self._costs, items, "costs")

    async def upsert_rate_limits(self, records: Iterable[RateLimitEntry]) -> dict[str, int]:
        # Disabled: do not persist rate limits to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}

    async def upsert_spend_limits(self, result: SpendLimitsResult) -> dict[str, int]:
        # Disabled: do not persist spend limits to MongoDB.
        return {"matched": 0, "upserted": 0, "total": 0}
