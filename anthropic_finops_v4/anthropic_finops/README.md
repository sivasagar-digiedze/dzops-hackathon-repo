# Anthropic FinOps Scheduler and Worker

The existing collector remains the source of truth for Anthropic API access. The scheduler only creates exact UTC windows and publishes them to RabbitMQ. The worker validates each message, calls `anthropic_admin.collector.collect_all`, writes usage and cost records through the existing MongoDB repository, and acknowledges only after both writes succeed.

## Configuration

Copy `.env.example` to `.env` and fill in `ANTHROPIC_ADMIN_API_KEY`, `MONGODB_URI`, and `RABBITMQ_URL`. Environment variables exported by the process override `.env`. Secrets are never included in logs.

`COLLECTION_INTERVAL_SECONDS` controls the window size and schedule interval. The default is 3600 seconds. `BACKFILL_START` is inclusive and `BACKFILL_END` is exclusive; when both are set, the scheduler publishes every window in that range before entering normal scheduling.

Anthropic's cost endpoint is daily-granularity in the existing collector, even when usage jobs are hourly. Historical ranges must also comply with the retention and access limits enforced by Anthropic's API; the scheduler does not fabricate older data.

## Start locally

Install dependencies from the project directory:

```bash
cd /home/tejasree/Downloads/anthropic_finops_v4/anthropic_finops
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

RabbitMQ must be running and reachable using `RABBITMQ_URL`. For a local broker, Docker is the simplest option:

```bash
docker run -d --name finops-rabbitmq -p 5672:5672 rabbitmq:3-management
```

Set `RABBITMQ_URL=amqp://guest:guest@localhost:5672/` for that container. Then use two terminals:

```bash
venv/bin/python -m worker.worker
```

```bash
venv/bin/python -m scheduler.scheduler
```

The scheduler publishes the last completed interval immediately, then publishes one completed interval at each boundary. Its `.scheduler_state.json` records the next window only after a successful RabbitMQ publish, allowing it to catch up after a scheduler restart.

## Test one job

This bypasses RabbitMQ but exercises the same worker execution and MongoDB persistence path:

```bash
venv/bin/python -m worker.worker --once \
  --starting-at 2026-08-19T09:00:00Z \
  --ending-at 2026-08-19T10:00:00Z
```

To test the full path quickly, temporarily set `COLLECTION_INTERVAL_SECONDS=60`, start the worker and scheduler, and watch for `published_collection_job`, `received_collection_job`, `collector_completed`, `mongodb_write_success`, and `collection_job_acknowledged`. Restore 3600 afterward. A normal hourly job is stored at the end of its UTC window plus API and MongoDB processing time, so the minimum scheduler-induced delay is near zero after the boundary; backlog, retries, and API duration add to it.

## Test backfill and recovery

Set the following in `.env`, restart the scheduler, and inspect RabbitMQ's queue:

```dotenv
BACKFILL_START=2026-08-01T00:00:00Z
BACKFILL_END=2026-08-01T03:00:00Z
```

Three messages should be published: `00:00 -> 01:00`, `01:00 -> 02:00`, and `02:00 -> 03:00`. Clear the two variables for normal operation.

To test MongoDB failure, stop or make the configured MongoDB endpoint unreachable, publish a job, and watch `mongodb_unavailable_retrying`. The worker retries with exponential backoff, then rejects the message to `anthropic_finops_collection.dead` without acknowledging it on the main queue. Restore MongoDB and replay the dead-letter message from RabbitMQ management tools. The existing repository uses deterministic upserts, so replaying a completed window does not create duplicate usage or cost records.

To test worker crash recovery, publish a job, stop the worker while `starting_collector` is logged, then restart it. Manual acknowledgements and a durable persistent queue allow RabbitMQ to redeliver the unacknowledged job.

## Shutdown and duplicate protection

Use `Ctrl+C` or send `SIGTERM`. The scheduler stops creating jobs and closes RabbitMQ. The worker cancels its consumer and closes RabbitMQ; a job that has not reached its ACK remains recoverable. RabbitMQ's main queue and dead-letter queue are durable. Usage and cost records are upserted by the existing deterministic IDs based on their normalized dimensions, so retries and redeliveries are safe.

The original direct collector command is still available:

```bash
venv/bin/python -m scripts.collect --starting-at 2026-08-19T00:00:00Z --ending-at 2026-08-19T01:00:00Z
```