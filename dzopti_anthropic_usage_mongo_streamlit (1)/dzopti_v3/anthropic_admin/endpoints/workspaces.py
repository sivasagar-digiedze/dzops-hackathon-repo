"""
GET /v1/organizations/workspaces
GET /v1/organizations/workspaces/{workspace_id}/members

Both use the last_id / has_more pagination style, via the shared
paginate_all() + last_id_cursor() from pagination.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..pagination import last_id_cursor, paginate_all

logger = logging.getLogger("dzopti.anthropic_admin.endpoints.workspaces")

WORKSPACES_ENDPOINT = "/v1/organizations/workspaces"


def _members_endpoint(workspace_id: str) -> str:
    return f"/v1/organizations/workspaces/{workspace_id}/members"


async def fetch_workspaces(client: AnthropicAdminClient, *, limit: int = 100) -> dict[str, Any]:
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "workspaces"})
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(after_id: Optional[str]) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if after_id:
            params["after_id"] = after_id
        return await client.get(WORKSPACES_ENDPOINT, params=params)

    page_result = await paginate_all(
        fetch_page, last_id_cursor, endpoint_name="workspaces"
    )
    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "workspaces", "record_count": len(page_result.records)},
    )

    return {
        "endpoint": WORKSPACES_ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": {"limit": limit},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }


async def fetch_workspace_members(
    client: AnthropicAdminClient, workspace_id: str, *, limit: int = 100
) -> dict[str, Any]:
    endpoint = _members_endpoint(workspace_id)
    logger.info(
        "anthropic_admin.endpoint.fetch_start",
        extra={"ep_name": "workspace_members", "ep_workspace_id": workspace_id},
    )
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(after_id: Optional[str]) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if after_id:
            params["after_id"] = after_id
        return await client.get(endpoint, params=params)

    page_result = await paginate_all(
        fetch_page, last_id_cursor, endpoint_name=f"workspace_members[{workspace_id}]"
    )

    return {
        "endpoint": endpoint,
        "requested_at": requested_at,
        "request_parameters": {"workspace_id": workspace_id, "limit": limit},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
