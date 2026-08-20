"""
GET /v1/organizations/cost_report

Verified against Anthropic's official Cost API reference:
  - group_by[] supports ONLY "workspace_id" and "description". There is
    no api_key_id grouping option — it does not exist in this endpoint's
    schema at all, at any granularity.
  - bucket_width accepts ONLY "1d" (the API reference lists exactly one
    enum value). Requesting anything else is not a documented capability,
    so this module does not expose a bucket_width parameter — cost stays
    daily even when usage is collected hourly. This is a genuine
    Anthropic API limitation, not an implementation choice.
  - When grouped by "description", each row additionally includes model,
    service_tier, context_window, cost_type, and token_type — that's the
    only way to get model/service-tier-level cost attribution, since
    there's no direct group_by=model option either.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..pagination import next_page_cursor, paginate_all

logger = logging.getLogger("anthropic_admin.endpoints.costs")

ENDPOINT = "/v1/organizations/cost_report"
MAX_LIMIT = 31  # daily buckets per page — the only granularity this endpoint supports

# The only two group_by[] values Anthropic's Cost API documents.
DEFAULT_GROUP_BY = ("workspace_id", "description")

BUCKET_WIDTH_LIMITATION_NOTE = (
    "Anthropic's Cost API (/v1/organizations/cost_report) only supports "
    "bucket_width=1d — there is no hourly cost granularity, unlike the "
    "Usage API. Cost data in this integration is therefore always daily "
    "even when usage is collected hourly. This is a documented Anthropic "
    "API limitation, not a limitation of this integration."
)

API_KEY_LIMITATION_NOTE = (
    "Anthropic's Cost API has no api_key_id dimension at any granularity "
    "— group_by[] only supports workspace_id and description. Per-API-key "
    "cost is therefore not obtainable from Anthropic's Admin API; "
    "api_key_id is always null on every CostRecord, not a missing value "
    "we failed to capture."
)


async def fetch_costs(
    client: AnthropicAdminClient,
    *,
    starting_at: str,
    ending_at: str,
    limit: int = MAX_LIMIT,
) -> dict[str, Any]:
    logger.info(
        "anthropic_admin.endpoint.fetch_start",
        extra={"ep_name": "costs", "ep_starting_at": starting_at, "ep_ending_at": ending_at},
    )
    effective_limit = min(limit, MAX_LIMIT)
    requested_at = datetime.now(timezone.utc).isoformat()

    def _params(cursor: Optional[str]) -> dict[str, Any]:
        p: dict[str, Any] = {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "limit": effective_limit,
            "group_by[]": list(DEFAULT_GROUP_BY),
        }
        if cursor:
            p["page"] = cursor
        return p

    async def fetch_page(cursor: Optional[str]) -> dict:
        return await client.get(ENDPOINT, params=_params(cursor))

    page_result = await paginate_all(fetch_page, next_page_cursor, endpoint_name="costs")
    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "costs", "record_count": len(page_result.records)},
    )

    return {
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": _params(None),
        "date_range": {"starting_at": starting_at, "ending_at": ending_at, "bucket_width": "1d"},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
