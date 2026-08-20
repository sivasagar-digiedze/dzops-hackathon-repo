"""
GET /v1/organizations/spend_limits/effective

Available to Claude Enterprise organizations only — NOT Claude Platform
(Console) organizations, which have no spend-limit read endpoint at all.
This module never lets that turn into a fatal collection failure: it
catches the expected 404/403 and returns a structured "not supported"
result instead of raising.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..client import AnthropicAdminClient
from ..exceptions import NotFoundError, PermissionDeniedError
from ..pagination import next_page_cursor, paginate_all

logger = logging.getLogger("anthropic_admin.endpoints.spend_limits")

ENDPOINT = "/v1/organizations/spend_limits/effective"


async def fetch_spend_limits(client: AnthropicAdminClient) -> dict[str, Any]:
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "spend_limits"})
    requested_at = datetime.now(timezone.utc).isoformat()

    async def fetch_page(cursor: Optional[str]) -> dict:
        params: dict[str, Any] = {"limit": 1000}
        if cursor:
            params["page"] = cursor
        return await client.get(ENDPOINT, params=params)

    try:
        page_result = await paginate_all(fetch_page, next_page_cursor, endpoint_name="spend_limits")
    except NotFoundError:
        logger.info("anthropic_admin.endpoint.not_supported", extra={"ep_name": "spend_limits", "ep_reason": "404"})
        return {
            "supported": False,
            "reason": (
                "Endpoint not supported for this organization type. The "
                "Spend Limits API is available to Claude Enterprise "
                "organizations only; Claude Platform (Console) "
                "organizations have no spend-limit read endpoint."
            ),
            "endpoint": ENDPOINT,
            "requested_at": requested_at,
        }
    except PermissionDeniedError:
        logger.info("anthropic_admin.endpoint.not_supported", extra={"ep_name": "spend_limits", "ep_reason": "403"})
        return {
            "supported": False,
            "reason": (
                "Access denied. If on Claude Enterprise, the Admin key is "
                "missing the 'read:spend_limits' scope. If on Claude "
                "Platform (Console), spend limits are not exposed via the "
                "Admin API at all."
            ),
            "endpoint": ENDPOINT,
            "requested_at": requested_at,
        }

    logger.info(
        "anthropic_admin.endpoint.fetch_done",
        extra={"ep_name": "spend_limits", "record_count": len(page_result.records)},
    )
    return {
        "supported": True,
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": {"limit": 1000},
        "pages": page_result.raw_pages,
        "records": page_result.records,
        "pages_fetched": page_result.pages_fetched,
        "truncated": page_result.truncated,
    }
