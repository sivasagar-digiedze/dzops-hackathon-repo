"""
Anthropic Admin API collector — CLI entry point.

Fetches organization/workspaces/users/api_keys/usage/costs/rate_limits/
spend_limits/models, normalizes everything, prints a summary, writes the
normalized (NOT raw) result to a local JSON file, and upserts usage +
cost records into MongoDB.

Run:
    python3 -m scripts.collect
    python3 -m scripts.collect --hours 48
    python3 -m scripts.collect --starting-at 2026-08-17T00:00:00Z --ending-at 2026-08-18T00:00:00Z
    python3 -m scripts.collect --skip-mongo             # fetch + normalize + local JSON only
    python3 -m scripts.collect --show-parsing-trace      # print raw->normalized for 3 sample usage rows (proof of transformation, printed only, never persisted)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

from anthropic_admin.collector import collect_all
from anthropic_admin.config import AnthropicAdminConfig, ConfigurationError, MongoConfig
from anthropic_admin.endpoints import usage as ep_usage
from anthropic_admin.exceptions import AuthenticationError
from anthropic_admin.parsers import usage as p_usage
from anthropic_admin.repository.mongo_repository import MongoAnthropicRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s")
logger = logging.getLogger("scripts.collect")

DEFAULT_OUTPUT_PATH = "anthropic_normalized_result.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anthropic Admin API usage + cost collector")
    parser.add_argument("--hours", type=int, default=48, help="Hours back from now for usage (default: 48)")
    parser.add_argument("--starting-at", type=str, default=None, help="ISO8601 override, e.g. 2026-08-17T00:00:00Z")
    parser.add_argument("--ending-at", type=str, default=None, help="ISO8601 override, e.g. 2026-08-18T00:00:00Z")
    parser.add_argument("--bucket-width", type=str, default="1h", choices=["1m", "1h", "1d"], help="Usage bucket width (cost is always 1d — see endpoints/costs.py)")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_PATH, help="Local normalized JSON output path")
    parser.add_argument("--skip-mongo", action="store_true", help="Fetch + normalize + local JSON only, no MongoDB writes")
    parser.add_argument("--show-parsing-trace", action="store_true", help="Print raw Anthropic bucket -> normalized record for a few sample usage rows (proof of transformation; printed only, never saved)")
    return parser.parse_args()


def _section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


async def _print_parsing_trace(anthropic_config: AnthropicAdminConfig, starting_at: str, ending_at: str, bucket_width: str, sample_size: int = 3) -> None:
    """
    Fetches ONE extra usage page directly (bypassing the collector) purely
    to print raw -> normalized side by side. Nothing here is stored
    anywhere — it exists only so you can visually confirm parsing/
    normalization actually transforms the data instead of copying it.
    """
    from anthropic_admin.client import AnthropicAdminClient

    _section("PARSING TRACE (raw Anthropic bucket -> normalized record)")
    async with AnthropicAdminClient(anthropic_config) as client:
        raw = await ep_usage.fetch_usage(
            client, starting_at=starting_at, ending_at=ending_at, bucket_width=bucket_width, limit=1
        )
    flattened = p_usage.parse_usage(raw)[:sample_size]
    normalized = p_usage.normalize_usage(raw)[:sample_size]
    for i, (raw_item, norm_item) in enumerate(zip(flattened, normalized), start=1):
        print(f"\n--- sample {i} ---")
        print("RAW (as Anthropic returned it, flattened out of its time bucket):")
        print(json.dumps(raw_item, indent=2, default=str))
        print("\nNORMALIZED (what this application actually stores):")
        print(json.dumps(norm_item.to_dict(), indent=2, default=str))
    if not flattened:
        print("(No usage in this window to sample — try a wider --hours range.)")


async def _main_async(args: argparse.Namespace) -> int:
    try:
        anthropic_config = AnthropicAdminConfig.from_env()
    except ConfigurationError as exc:
        print(f"\nCONFIGURATION ERROR: {exc}\n", file=sys.stderr)
        return 1

    if args.starting_at and args.ending_at:
        starting_at, ending_at = args.starting_at, args.ending_at
    else:
        now_dt = datetime.now(timezone.utc)
        if args.bucket_width == "1d":
            # Align to UTC midnight boundaries for daily buckets. Use
            # whole days computed from the requested hours window.
            ending_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            # Convert hours to full days (round up) so `--hours 48` => 2 days
            import math
            days = max(1, math.ceil(args.hours / 24))
            starting_dt = ending_dt - timedelta(days=days)
        else:
            # Hourly/minute buckets: align to start of current hour
            ending_dt = now_dt.replace(minute=0, second=0, microsecond=0)
            starting_dt = ending_dt - timedelta(hours=args.hours)
        starting_at = starting_dt.isoformat().replace("+00:00", "Z")
        ending_at = ending_dt.isoformat().replace("+00:00", "Z")

    if args.show_parsing_trace:
        try:
            await _print_parsing_trace(anthropic_config, starting_at, ending_at, args.bucket_width)
        except AuthenticationError as exc:
            print("\nAUTHENTICATION FAILED — check ANTHROPIC_ADMIN_API_KEY in .env")
            print(json.dumps(exc.to_structured_error(), indent=2))
            return 1

    print(f"\nCollecting Anthropic usage ({args.bucket_width}) and cost (1d) for {starting_at} -> {ending_at}")

    try:
        result = await collect_all(
            anthropic_config,
            usage_starting_at=starting_at,
            usage_ending_at=ending_at,
            usage_bucket_width=args.bucket_width,
        )
    except AuthenticationError as exc:
        print("\nAUTHENTICATION FAILED — check ANTHROPIC_ADMIN_API_KEY in .env")
        print(json.dumps(exc.to_structured_error(), indent=2))
        return 1

    result_dict = result.to_dict()

    _section("SUMMARY")
    print(f"Organization: {result_dict['organization']['organization_name']} ({result_dict['organization']['organization_id']})")
    print(f"Workspaces: {len(result_dict['workspaces'])} | Users: {len(result_dict['users'])} | API keys: {len(result_dict['api_keys'])}")
    print(f"Usage records ({args.bucket_width} buckets): {len(result_dict['usage'])}")
    print(f"Cost records (1d buckets): {len(result_dict['costs'])}")
    print(f"Rate limit entries: {len(result_dict['rate_limits'])} | Models: {len(result_dict['models'])}")
    print(f"Spend limits supported: {result_dict['spend_limits']['supported']}")
    print(f"Capabilities: {json.dumps(result_dict['metadata']['capabilities'])}")
    print(f"Errors: {len(result_dict['errors'])}")
    for err in result_dict["errors"]:
        print(f"  - {err}")

    with open(args.output, "w") as f:
        json.dump(result_dict, f, indent=2, default=str)
    print(f"\nNormalized result (no raw Anthropic response included) written to: {args.output}")

    if args.skip_mongo:
        print("\n--skip-mongo set: not writing to MongoDB.")
        return 0

    _section("MONGODB")
    try:
        mongo_config = MongoConfig.from_env()
    except ConfigurationError as exc:
        print(f"CONFIGURATION ERROR: {exc}")
        return 1

    repo = MongoAnthropicRepository(mongo_config)
    try:
        if not await repo.ping():
            print("MongoDB connectivity check FAILED — see log above. Nothing was stored.")
            return 1
        await repo.ensure_indexes()

        # Only persist usage and costs per requirements
        usage_counts = await repo.upsert_usage_records(result.usage)
        cost_counts = await repo.upsert_cost_records(result.costs)

        def _line(label: str, collection: str, counts: dict) -> str:
            if counts.get("status_doc"):
                return f"{label:24s} -> {mongo_config.database}.{collection}: status document only (not supported for this org)"
            return (
                f"{label:24s} -> {mongo_config.database}.{collection}: "
                f"{counts['upserted']} new, {counts['matched']} updated (total {counts['total']})"
            )

        # Summary printout required by the user
        print(f"Usage records fetched: {len(result.usage)}")
        print(f"Usage records stored: {usage_counts['total']}\n")

        print(f"Cost records fetched: {len(result.costs)}")
        print(f"Cost records stored: {cost_counts['total']}\n")

        print("Other records stored: 0")
    finally:
        await repo.close()

    return 0


def main() -> None:
    args = _parse_args()
    exit_code = asyncio.run(_main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
