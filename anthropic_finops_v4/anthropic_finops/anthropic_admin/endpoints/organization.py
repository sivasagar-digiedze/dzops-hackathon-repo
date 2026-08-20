"""GET /v1/organizations/me — not paginated (single object)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..client import AnthropicAdminClient

logger = logging.getLogger("anthropic_admin.endpoints.organization")

ENDPOINT = "/v1/organizations/me"


async def fetch_organization(client: AnthropicAdminClient) -> dict[str, Any]:
    """Return the raw wrapper: {endpoint, requested_at, request_parameters, response}."""
    logger.info("anthropic_admin.endpoint.fetch_start", extra={"ep_name": "organization"})
    requested_at = datetime.now(timezone.utc).isoformat()
    response = await client.get(ENDPOINT)
    logger.info("anthropic_admin.endpoint.fetch_done", extra={"ep_name": "organization"})
    return {
        "endpoint": ENDPOINT,
        "requested_at": requested_at,
        "request_parameters": {},
        "response": response,
    }
