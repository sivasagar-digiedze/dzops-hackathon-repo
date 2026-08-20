"""
GET /v1/organizations/api_keys — last_id / has_more pagination style.

Returns METADATA ONLY. Anthropic never returns a plaintext secret for an
existing key through any endpoint (it's shown once, at creation, in the
Console) — there is no secret in this response to accidentally leak.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..pagination import last_id_cursor, paginate_all

logger = logging.getLogger("anthropic_admin.endpoints.api_keys")

ENDPOINT = "/v1/organizations/api_keys"


async def fetch_api_keys(
    client: AnthropicAdminClient,
    *,
    limit: int = 100,
    status: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "api_keys"})
    requested_at = datetime.now(timezone.utc).isoformat()
    request_parameters: dict[str, Any] = {"limit": limit}
    if status:
        request_parameters["status"] = status
    if workspace_id:
        request_parameters["workspace_id"] = workspace_id

    async def fetch_page(after_id: Optional[str]) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if workspace_id:
            params["workspace_id"] = workspace_id
        if after_id:
            params["after_id"] = after_id
        return await client.get(ENDPOINT, params=params)

    page_result = await paginate_all(fetch_page, last_id_cursor, endpoint_name="api_keys")
    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "api_keys", "record_count": len(page_result.records)},
    )

    return {
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": request_parameters,
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
