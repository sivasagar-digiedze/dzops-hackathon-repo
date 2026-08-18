"""
GET /v1/organizations/rate_limits
GET /v1/organizations/workspaces/{workspace_id}/rate_limits

next_page / has_more pagination style (currently always single-page per
Anthropic's docs, but the loop handles it correctly either way).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..pagination import next_page_cursor, paginate_all

logger = logging.getLogger("dzopti.anthropic_admin.endpoints.rate_limits")

ORG_ENDPOINT = "/v1/organizations/rate_limits"


def workspace_endpoint(workspace_id: str) -> str:
    return f"/v1/organizations/workspaces/{workspace_id}/rate_limits"


async def fetch_organization_rate_limits(client: AnthropicAdminClient) -> dict[str, Any]:
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "org_rate_limits"})
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(cursor: Optional[str]) -> dict:
        params: dict[str, Any] = {}
        if cursor:
            params["page"] = cursor
        return await client.get(ORG_ENDPOINT, params=params)

    page_result = await paginate_all(fetch_page, next_page_cursor, endpoint_name="org_rate_limits")

    return {
        "endpoint": ORG_ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": {},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }


async def fetch_workspace_rate_limits(client: AnthropicAdminClient, workspace_id: str) -> dict[str, Any]:
    endpoint = workspace_endpoint(workspace_id)
    logger.info(
        "anthropic_admin.endpoint.fetch_start",
        extra={"ep_name": "workspace_rate_limits", "ep_workspace_id": workspace_id},
    )
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(cursor: Optional[str]) -> dict:
        params: dict[str, Any] = {}
        if cursor:
            params["page"] = cursor
        return await client.get(endpoint, params=params)

    page_result = await paginate_all(
        fetch_page, next_page_cursor, endpoint_name=f"workspace_rate_limits[{workspace_id}]"
    )

    return {
        "endpoint": endpoint,
        "requested_at": requested_at,
        "request_parameters": {"workspace_id": workspace_id},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
