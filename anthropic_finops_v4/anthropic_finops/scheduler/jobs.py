"""Collection job validation, serialization, and RabbitMQ topology."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika import ExchangeType

from anthropic_admin.config import RabbitMQConfig


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CollectionJob:
    job_id: str
    provider: str
    job_type: str
    starting_at: str
    ending_at: str

    @classmethod
    def create(cls, starting_at: datetime, ending_at: datetime) -> "CollectionJob":
        start = format_utc(starting_at)
        end = format_utc(ending_at)
        job_id = f"anthropic:{start}:{end}"
        return cls(job_id, "anthropic", "collect_usage_cost", start, end)

    def validate(self) -> None:
        if self.provider != "anthropic":
            raise ValueError("unsupported provider")
        if self.job_type != "collect_usage_cost":
            raise ValueError("unsupported job type")
        start = parse_utc(self.starting_at)
        end = parse_utc(self.ending_at)
        if start >= end:
            raise ValueError("starting_at must be before ending_at")
        expected_id = f"anthropic:{format_utc(start)}:{format_utc(end)}"
        if self.job_id != expected_id:
            raise ValueError("job_id does not match the collection window")

    def to_dict(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "provider": self.provider,
            "job_type": self.job_type,
            "starting_at": self.starting_at,
            "ending_at": self.ending_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CollectionJob":
        required = {"job_id", "provider", "job_type", "starting_at", "ending_at"}
        if not isinstance(value, dict) or not required.issubset(value):
            raise ValueError("collection job is missing required fields")
        if any(not isinstance(value[field], str) for field in required):
            raise ValueError("collection job fields must be strings")
        job = cls(*(value[field] for field in ("job_id", "provider", "job_type", "starting_at", "ending_at")))
        job.validate()
        return job

    def body(self) -> bytes:
        self.validate()
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")


async def declare_topology(channel: aio_pika.abc.AbstractChannel, config: RabbitMQConfig):
    dead_exchange = await channel.declare_exchange(
        config.dead_letter_exchange, ExchangeType.DIRECT, durable=True
    )
    dead_queue = await channel.declare_queue(config.dead_letter_queue, durable=True)
    await dead_queue.bind(dead_exchange, routing_key=config.dead_letter_queue)

    queue = await channel.declare_queue(
        config.queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange": config.dead_letter_exchange,
            "x-dead-letter-routing-key": config.dead_letter_queue,
        },
    )
    return queue


def safe_job_digest(job: CollectionJob) -> str:
    """Short non-secret identifier useful in logs and diagnostics."""
    return hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:12]