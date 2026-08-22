"""Publish exact UTC collection windows to RabbitMQ."""
from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aio_pika
from aio_pika import DeliveryMode, Message

from anthropic_admin.config import ConfigurationError, RabbitMQConfig, SchedulerConfig
from scheduler.jobs import CollectionJob, declare_topology, parse_utc, safe_job_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s")
logger = logging.getLogger("scheduler")


def _floor_utc(value: datetime, interval_seconds: int) -> datetime:
    epoch = int(value.timestamp())
    return datetime.fromtimestamp(epoch - epoch % interval_seconds, timezone.utc)


class Scheduler:
    def __init__(self, rabbit: RabbitMQConfig, settings: SchedulerConfig) -> None:
        if settings.interval_seconds <= 0:
            raise ValueError("COLLECTION_INTERVAL_SECONDS must be positive")
        self.rabbit = rabbit
        self.settings = settings
        self._stop = asyncio.Event()
        self._connection = None

    def stop(self) -> None:
        logger.info("scheduler_shutdown_requested")
        self._stop.set()

    def _load_next_start(self) -> datetime | None:
        path = Path(self.settings.state_file)
        try:
            data = json.loads(path.read_text())
            return parse_utc(data["next_start"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _save_next_start(self, value: datetime) -> None:
        path = Path(self.settings.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({"next_start": value.isoformat().replace("+00:00", "Z")}))
        temporary.replace(path)

    async def _publish(self, channel, job: CollectionJob) -> None:
        await channel.default_exchange.publish(
            Message(job.body(), delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"),
            routing_key=self.rabbit.queue,
        )
        logger.info(
            "published_collection_job",
            extra={"job_id": job.job_id, "job_digest": safe_job_digest(job), "starting_at": job.starting_at, "ending_at": job.ending_at},
        )

    async def _publish_backfill(self, channel) -> None:
        start = parse_utc(self.settings.backfill_start)
        end = parse_utc(self.settings.backfill_end)
        if start >= end:
            raise ValueError("BACKFILL_START must be before BACKFILL_END")
        interval = timedelta(seconds=self.settings.interval_seconds)
        current = start
        while current < end and not self._stop.is_set():
            window_end = min(current + interval, end)
            await self._publish(channel, CollectionJob.create(current, window_end))
            current = window_end
        logger.info("backfill_published", extra={"backfill_start": self.settings.backfill_start, "backfill_end": self.settings.backfill_end})

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(self.rabbit.url)
        channel = await self._connection.channel()
        await declare_topology(channel, self.rabbit)
        logger.info("scheduler_started", extra={"queue": self.rabbit.queue, "interval_seconds": self.settings.interval_seconds})

        if self.settings.backfill_start or self.settings.backfill_end:
            if not (self.settings.backfill_start and self.settings.backfill_end):
                raise ValueError("BACKFILL_START and BACKFILL_END must be set together")
            await self._publish_backfill(channel)

        next_start = self._load_next_start()
        interval = timedelta(seconds=self.settings.interval_seconds)
        if next_start is None:
            boundary = _floor_utc(datetime.now(timezone.utc), self.settings.interval_seconds)
            next_start = boundary - interval

        try:
            while not self._stop.is_set():
                boundary = _floor_utc(datetime.now(timezone.utc), self.settings.interval_seconds)
                while next_start + interval <= boundary and not self._stop.is_set():
                    job = CollectionJob.create(next_start, next_start + interval)
                    await self._publish(channel, job)
                    next_start += interval
                    self._save_next_start(next_start)

                wait_seconds = max(1.0, (next_start + interval - datetime.now(timezone.utc)).total_seconds())
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            await self._connection.close()
            logger.info("scheduler_stopped")


async def _main() -> None:
    try:
        scheduler = Scheduler(RabbitMQConfig.from_env(), SchedulerConfig.from_env())
    except (ConfigurationError, ValueError) as exc:
        logger.error("scheduler_configuration_error", extra={"error_type": type(exc).__name__})
        raise SystemExit(1) from exc
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, name), scheduler.stop)
        except (NotImplementedError, RuntimeError):
            pass
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(_main())