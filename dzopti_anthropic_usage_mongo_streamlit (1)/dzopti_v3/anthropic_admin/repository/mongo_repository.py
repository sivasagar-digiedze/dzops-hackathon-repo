"""
MongoDB repository for Anthropic daily token usage — Motor (async).

Writes ONLY to `{database}.{usage_collection}` (dzops_core.demo_tokens_usage
by default). Nothing else on the shared Mongo server is ever touched:
no other collection is read, written, dropped, or have its indexes
changed by this module.

Idempotency
-----------
A usage record is uniquely identified by the combination of every
dimension Anthropic grouped the bucket by, plus the time window itself.
Two collector runs over overlapping date ranges (e.g. the daily job
re-covering "yesterday" for safety) must resolve to the SAME MongoDB
document, not a duplicate — so `_id` is a deterministic SHA-256 hash of:

    provider, organization_id, period_start, period_end,
    workspace_id, api_key_id, model, service_tier, context_window

context_window is included because it's one of the requested group_by
dimensions (a `0-200k` vs `200k-1M` request are genuinely different
usage rows for the same workspace/key/model/day, not duplicates of each
other) — it currently lives inside `provider_data`, so it's read from
there. api_key_id/workspace_id are preserved as `None` exactly when
Anthropic itself returned no value for them (see parsers/usage.py) —
None hashes to a stable, distinct value, it is never coerced into a
placeholder string.

Every write is `update_one(_id=..., $set=record, upsert=True)` — re-running
the collector overwrites the existing document with the latest values
instead of creating a duplicate.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Iterable

from ..config import MongoConfig
from ..models.normalized import UsageRecord

logger = logging.getLogger("dzopti.anthropic_admin.repository.mongo")

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
except ImportError:  # pragma: no cover - motor is an optional dependency until this repo is used
    AsyncIOMotorClient = Any  # type: ignore
    AsyncIOMotorDatabase = Any  # type: ignore


def usage_record_id(record: UsageRecord) -> str:
    """Deterministic, stable _id for one usage record. See module docstring."""
    context_window = (record.provider_data or {}).get("context_window")
    parts = (
        record.provider,
        record.organization_id,
        record.period_start,
        record.period_end,
        record.workspace_id,
        record.api_key_id,
        record.model,
        record.service_tier,
        context_window,
    )
    normalized = json.dumps(parts, sort_keys=False, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def usage_record_to_document(record: UsageRecord) -> dict[str, Any]:
    """Flat MongoDB document for one usage record — see README field-by-field explanation."""
    doc = record.to_dict()
    doc["_id"] = usage_record_id(record)
    doc["total_tokens"] = (
        (record.input_tokens or 0)
        + (record.output_tokens or 0)
        + (record.cache_creation_input_tokens or 0)
        + (record.cache_read_input_tokens or 0)
    )
    return doc


class MongoUsageRepository:
    """Async repository scoped to exactly one collection: usage_collection."""

    def __init__(self, config: MongoConfig) -> None:
        self._config = config
        self._client: "AsyncIOMotorClient" = AsyncIOMotorClient(config.uri)
        self._db: "AsyncIOMotorDatabase" = self._client[config.database]
        self._collection = self._db[config.usage_collection]

    async def close(self) -> None:
        self._client.close()

    async def ping(self) -> bool:
        """Connectivity check — never logs the connection string."""
        try:
            await self._client.admin.command("ping")
            logger.info(
                "dzopti.mongo.ping_ok",
                extra={"mg_database": self._config.database, "mg_collection": self._config.usage_collection},
            )
            return True
        except Exception as exc:  # noqa: BLE001 - report, don't leak the URI
            logger.error("dzopti.mongo.ping_failed", extra={"mg_error_type": type(exc).__name__})
            return False

    async def ensure_indexes(self) -> None:
        """
        Recommended indexes for demo_tokens_usage:

          period_start (descending)
            Every dashboard query starts with a date-range filter
            ("last 7 days", "this month") — this is the single most
            common query pattern and needs to be fast on its own.

          workspace_id
            Powers "usage by workspace" filtering/aggregation without a
            full collection scan.

          api_key_id
            Powers "usage by API key" the same way.

          model
            Powers "usage by model" the same way.

          organization_id
            Scopes queries to one org — relevant once Dzopti tracks more
            than one Anthropic organization.

          compound (organization_id, period_start, workspace_id)
            The actual shape of the dashboard's default query: "give me
            this org's usage in this date range, optionally filtered to
            one workspace" — a compound index lets Mongo satisfy the
            whole filter from the index instead of scanning + filtering.
        """
        await self._collection.create_index("period_start")
        await self._collection.create_index("workspace_id")
        await self._collection.create_index("api_key_id")
        await self._collection.create_index("model")
        await self._collection.create_index("organization_id")
        await self._collection.create_index(
            [("organization_id", 1), ("period_start", -1), ("workspace_id", 1)]
        )
        logger.info("dzopti.mongo.indexes_ensured", extra={"mg_collection": self._config.usage_collection})

    async def upsert_usage_records(self, records: Iterable[UsageRecord]) -> dict[str, int]:
        """
        Idempotently upsert every usage record. Returns counts, never the
        documents themselves (caller already has those in memory).
        """
        matched = 0
        upserted = 0
        for record in records:
            doc = usage_record_to_document(record)
            doc_id = doc.pop("_id")
            result = await self._collection.update_one(
                {"_id": doc_id}, {"$set": doc}, upsert=True
            )
            if result.upserted_id is not None:
                upserted += 1
            else:
                matched += 1

        logger.info(
            "dzopti.mongo.usage_upsert_done",
            extra={"mg_matched": matched, "mg_upserted": upserted, "mg_total": matched + upserted},
        )
        return {"matched": matched, "upserted": upserted, "total": matched + upserted}
