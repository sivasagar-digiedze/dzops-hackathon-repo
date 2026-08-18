"""
GET /v1/models

Technically a general Claude API endpoint (works with any valid key,
not Admin-exclusive), included because the spec asked for organization-
relevant model info and an Admin key is accepted here. last_id / has_more
pagination style.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..pagination import last_id_cursor, paginate_all

logger = logging.getLogger("dzopti.anthropic_admin.endpoints.models")

ENDPOINT = "/v1/models"


async def fetch_models(client: AnthropicAdminClient, *, limit: int = 100) -> dict[str, Any]:
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "models"})
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(after_id: Optional[str]) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if after_id:
            params["after_id"] = after_id
        return await client.get(ENDPOINT, params=params)

    page_result = await paginate_all(fetch_page, last_id_cursor, endpoint_name="models")
    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "models", "record_count": len(page_result.records)},
    )

    return {
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": {"limit": limit},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
