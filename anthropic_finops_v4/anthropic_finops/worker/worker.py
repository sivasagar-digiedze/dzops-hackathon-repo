"""Consume collection jobs and persist results before acknowledging them."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
from datetime import datetime

import aio_pika

from anthropic_admin.collector import collect_all
from anthropic_admin.config import (
    AnthropicAdminConfig,
    ConfigurationError,
    MongoConfig,
    MongoRetryConfig,
    RabbitMQConfig,
)
from anthropic_admin.repository.mongo_repository import MongoAnthropicRepository
from scheduler.jobs import CollectionJob, declare_topology, safe_job_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s")
logger = logging.getLogger("worker")


async def _persist_result(repo: MongoAnthropicRepository, result, retry: MongoRetryConfig, job: CollectionJob) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retry.max_retries + 1):
        try:
            if not await repo.ping():
                raise ConnectionError("MongoDB ping failed")
            await repo.ensure_indexes()
            await repo.upsert_usage_records(result.usage)
            await repo.upsert_cost_records(result.costs)
            logger.info("mongodb_write_success", extra={"job_id": job.job_id})
            return
        except Exception as exc:  # noqa: BLE001 - retry transient database failures
            last_error = exc
            if attempt == retry.max_retries:
                break
            delay = min(retry.base_seconds * (2 ** (attempt - 1)), retry.max_seconds)
            logger.warning(
                "mongodb_unavailable_retrying",
                extra={"job_id": job.job_id, "job_digest": safe_job_digest(job), "retry_attempt": attempt, "retry_limit": retry.max_retries, "delay_seconds": delay, "error_type": type(exc).__name__},
            )
            await asyncio.sleep(delay)
    raise RuntimeError(f"MongoDB persistence failed after {retry.max_retries} attempts") from last_error


async def execute_collection_job(
    job: CollectionJob,
    anthropic_config: AnthropicAdminConfig,
    mongo_config: MongoConfig,
    retry: MongoRetryConfig,
) -> None:
    job.validate()
    logger.info("starting_collector", extra={"job_id": job.job_id, "starting_at": job.starting_at, "ending_at": job.ending_at})
    result = await collect_all(
        anthropic_config,
        usage_starting_at=job.starting_at,
        usage_ending_at=job.ending_at,
        usage_bucket_width="1h",
    )
    if result.errors:
        raise RuntimeError(f"collector returned {len(result.errors)} component errors")
    logger.info("collector_completed", extra={"job_id": job.job_id, "usage_records": len(result.usage), "cost_records": len(result.costs)})
    repo = MongoAnthropicRepository(mongo_config)
    try:
        logger.info("writing_mongodb", extra={"job_id": job.job_id})
        await _persist_result(repo, result, retry, job)
    finally:
        await repo.close()


class Worker:
    def __init__(self, rabbit: RabbitMQConfig, anthropic: AnthropicAdminConfig, mongo: MongoConfig, retry: MongoRetryConfig) -> None:
        self.rabbit = rabbit
        self.anthropic = anthropic
        self.mongo = mongo
        self.retry = retry
        self._stop = asyncio.Event()
        self._connection = None

    def stop(self) -> None:
        logger.info("worker_shutdown_requested")
        self._stop.set()

    async def _handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode("utf-8"))
            job = CollectionJob.from_dict(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error("invalid_collection_job", extra={"error_type": type(exc).__name__})
            await message.reject(requeue=False)
            return

        logger.info("received_collection_job", extra={"job_id": job.job_id, "starting_at": job.starting_at, "ending_at": job.ending_at})
        try:
            await execute_collection_job(job, self.anthropic, self.mongo, self.retry)
        except Exception as exc:  # noqa: BLE001 - dead-letter any unsuccessful job
            logger.error("collection_job_failed", extra={"job_id": job.job_id, "error_type": type(exc).__name__})
            await message.reject(requeue=False)
            return
        await message.ack()
        logger.info("collection_job_acknowledged", extra={"job_id": job.job_id})

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(self.rabbit.url)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await declare_topology(channel, self.rabbit)
        logger.info("worker_started", extra={"queue": self.rabbit.queue})
        consumer_tag = await queue.consume(self._handle_message, no_ack=False)
        try:
            await self._stop.wait()
            await queue.cancel(consumer_tag)
        finally:
            await self._connection.close()
            logger.info("worker_stopped")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anthropic FinOps RabbitMQ worker")
    parser.add_argument("--once", action="store_true", help="execute one exact job directly, without RabbitMQ")
    parser.add_argument("--starting-at", help="ISO8601 UTC job start for --once")
    parser.add_argument("--ending-at", help="ISO8601 UTC job end for --once")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    try:
        anthropic = AnthropicAdminConfig.from_env()
        mongo = MongoConfig.from_env()
        retry = MongoRetryConfig.from_env()
        if args.once:
            if not args.starting_at or not args.ending_at:
                raise ValueError("--once requires --starting-at and --ending-at")
            await execute_collection_job(CollectionJob.create(
                datetime.fromisoformat(args.starting_at.replace("Z", "+00:00")),
                datetime.fromisoformat(args.ending_at.replace("Z", "+00:00")),
            ), anthropic, mongo, retry)
            return
        rabbit = RabbitMQConfig.from_env()
        worker = Worker(rabbit, anthropic, mongo, retry)
    except (ConfigurationError, ValueError) as exc:
        logger.error("worker_configuration_error", extra={"error_type": type(exc).__name__})
        raise SystemExit(1) from exc

    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, name), worker.stop)
        except (NotImplementedError, RuntimeError):
            pass
    await worker.run()


if __name__ == "__main__":
    asyncio.run(_main())