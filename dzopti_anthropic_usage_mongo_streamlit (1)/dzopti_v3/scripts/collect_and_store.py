"""
Dzopti Anthropic Admin API collector — CLI entry point (Phase 2).

Fetches organization/workspaces/users/api_keys/usage/rate_limits/
spend_limits/models from the Anthropic Admin API (NO cost), normalizes
everything, writes the complete raw+normalized result to a local JSON
file for inspection, and upserts the normalized USAGE records into
MongoDB (dzops_core.demo_tokens_usage) — nothing else is written to Mongo.

Run:
    python3 -m scripts.collect_and_store
    python3 -m scripts.collect_and_store --days 18
    python3 -m scripts.collect_and_store --starting-at 2026-08-01T00:00:00Z --ending-at 2026-08-18T00:00:00Z
    python3 -m scripts.collect_and_store --skip-mongo   # fetch + normalize + local JSON only
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
from anthropic_admin.exceptions import AuthenticationError
from anthropic_admin.repository.mongo_repository import MongoUsageRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s")
logger = logging.getLogger("dzopti.scripts.collect_and_store")

DEFAULT_OUTPUT_PATH = "anthropic_normalized_result.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dzopti Anthropic usage collector (Phase 2, no cost)")
    parser.add_argument("--days", type=int, default=18, help="Days back from now for usage (default: 18)")
    parser.add_argument("--starting-at", type=str, default=None, help="ISO8601 override, e.g. 2026-08-01T00:00:00Z")
    parser.add_argument("--ending-at", type=str, default=None, help="ISO8601 override, e.g. 2026-08-18T00:00:00Z")
    parser.add_argument("--bucket-width", type=str, default="1d", choices=["1m", "1h", "1d"])
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_PATH, help="Local JSON output path")
    parser.add_argument("--skip-mongo", action="store_true", help="Fetch + normalize + local JSON only, no MongoDB writes")
    return parser.parse_args()


def _section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


async def _main_async(args: argparse.Namespace) -> int:
    try:
        anthropic_config = AnthropicAdminConfig.from_hardcoded()
    except ConfigurationError as exc:
        print(f"\nCONFIGURATION ERROR: {exc}\n", file=sys.stderr)
        return 1

    if args.starting_at and args.ending_at:
        starting_at, ending_at = args.starting_at, args.ending_at
    else:
        ending_dt = datetime.now(timezone.utc).replace(microsecond=0)
        starting_dt = ending_dt - timedelta(days=args.days)
        starting_at = starting_dt.isoformat().replace("+00:00", "Z")
        ending_at = ending_dt.isoformat().replace("+00:00", "Z")

    print(f"Collecting Anthropic usage for {starting_at} -> {ending_at} (bucket_width={args.bucket_width})")

    try:
        result = await collect_all(
            anthropic_config,
            usage_starting_at=starting_at,
            usage_ending_at=ending_at,
            usage_bucket_width=args.bucket_width,
        )
    except AuthenticationError as exc:
        print("\nAUTHENTICATION FAILED — check ANTHROPIC_ADMIN_API_KEY in anthropic_admin/config.py")
        print(json.dumps(exc.to_structured_error(), indent=2))
        return 1

    result_dict = result.to_dict()

    _section("SUMMARY")
    print(f"Organization: {result_dict['organization']['organization_name']} ({result_dict['organization']['organization_id']})")
    print(f"Workspaces: {len(result_dict['workspaces'])}")
    print(f"Users: {len(result_dict['users'])}")
    print(f"API keys: {len(result_dict['api_keys'])}")
    print(f"Usage records (daily x workspace x api_key x model x service_tier x context_window): {len(result_dict['usage'])}")
    print(f"Rate limit entries: {len(result_dict['rate_limits'])}")
    print(f"Spend limits supported: {result_dict['spend_limits']['supported']}")
    print(f"Models: {len(result_dict['models'])}")
    print(f"Capabilities: {json.dumps(result_dict['metadata']['capabilities'])}")
    print(f"Errors: {len(result_dict['errors'])}")
    for err in result_dict["errors"]:
        print(f"  - {err}")

    with open(args.output, "w") as f:
        json.dump(result_dict, f, indent=2, default=str)
    print(f"\nFull raw+normalized result written to: {args.output}")

    if args.skip_mongo:
        print("\n--skip-mongo set: not writing to MongoDB.")
        return 0

    _section("MONGODB")
    mongo_config = MongoConfig.from_hardcoded()
    repo = MongoUsageRepository(mongo_config)
    try:
        if not await repo.ping():
            print("MongoDB connectivity check FAILED — see log above. Usage records were NOT stored.")
            return 1
        await repo.ensure_indexes()
        counts = await repo.upsert_usage_records(result.usage)
        print(
            f"Upserted into {mongo_config.database}.{mongo_config.usage_collection}: "
            f"{counts['upserted']} new, {counts['matched']} updated (total {counts['total']})"
        )
    finally:
        await repo.close()

    return 0


def main() -> None:
    args = _parse_args()
    exit_code = asyncio.run(_main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
