"""
GET /v1/organizations/usage_report/messages

next_page / has_more pagination style. Anthropic's per-request bucket
count limits (1m<=1440, 1h<=168, 1d<=31) govern the `limit` param, i.e.
buckets-per-page — NOT the total (starting_at, ending_at) span. A range
larger than one page's bucket capacity is covered by pagination
(has_more/next_page), which paginate_all() already walks to completion,
so no client-side date-window splitting is needed or performed.

Officially documented group_by[] dimensions (per Anthropic's Usage &
Cost API docs / API reference example request): api_key_id,
workspace_id, model, service_tier, context_window. These are the only
five used as the DEFAULT_GROUP_BY below — inference_geo and
service_account_id are NOT confirmed as group_by dimensions in the
documented API reference, so they are not requested as grouping keys
here (doing so would risk an invalid-request error). If Anthropic's
response includes inference_geo, speed, or any other field anyway, the
parser still preserves it under provider_data rather than discarding it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from ..client import AnthropicAdminClient
from ..pagination import next_page_cursor, paginate_all

logger = logging.getLogger("dzopti.anthropic_admin.endpoints.usage")

ENDPOINT = "/v1/organizations/usage_report/messages"

_MAX_LIMIT_BY_BUCKET_WIDTH = {"1m": 1440, "1h": 168, "1d": 31}

# The officially documented group_by[] dimensions, in the order Anthropic's
# own reference example uses them.
DEFAULT_GROUP_BY = ("api_key_id", "workspace_id", "model", "service_tier", "context_window")


class InvalidBucketWidthError(ValueError):
    pass


def max_limit_for(bucket_width: str) -> int:
    try:
        return _MAX_LIMIT_BY_BUCKET_WIDTH[bucket_width]
    except KeyError:
        raise InvalidBucketWidthError(
            f"Unsupported bucket_width={bucket_width!r}. Must be one of {sorted(_MAX_LIMIT_BY_BUCKET_WIDTH)}."
        ) from None


async def fetch_usage(
    client: AnthropicAdminClient,
    *,
    starting_at: str,
    ending_at: str,
    bucket_width: str = "1d",
    group_by: Optional[Sequence[str]] = None,
    models: Optional[Sequence[str]] = None,
    service_tiers: Optional[Sequence[str]] = None,
    workspace_ids: Optional[Sequence[str]] = None,
    api_key_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    logger.info(
        "anthropic_admin.endpoint.fetch_start",
        extra={"ep_name": "usage", "ep_starting_at": starting_at, "ep_ending_at": ending_at, "ep_bucket_width": bucket_width},
    )
    max_limit = max_limit_for(bucket_width)
    effective_limit = min(limit, max_limit) if limit else max_limit
    requested_at = datetime.now(timezone.utc).isoformat()

    def _params(cursor: Optional[str]) -> dict[str, Any]:
        p: dict[str, Any] = {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "bucket_width": bucket_width,
            "limit": effective_limit,
        }
        if group_by:
            p["group_by[]"] = list(group_by)
        if models:
            p["models[]"] = list(models)
        if service_tiers:
            p["service_tiers[]"] = list(service_tiers)
        if workspace_ids:
            p["workspace_ids[]"] = list(workspace_ids)
        if api_key_ids:
            p["api_key_ids[]"] = list(api_key_ids)
        if cursor:
            p["page"] = cursor
        return p

    async def fetch_page(cursor: Optional[str]) -> dict:
        return await client.get(ENDPOINT, params=_params(cursor))

    page_result = await paginate_all(fetch_page, next_page_cursor, endpoint_name="usage")
    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "usage", "record_count": len(page_result.records)},
    )

    return {
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": _params(None),
        "date_range": {"starting_at": starting_at, "ending_at": ending_at, "bucket_width": bucket_width},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
