"""Parser + normalizer for organization and workspace rate limits."""
from __future__ import annotations

from typing import Any, Optional

from ..models.normalized import RateLimitEntry


def parse_rate_limits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("records", []) or []


def normalize_rate_limits(raw: dict[str, Any], *, workspace_id: Optional[str] = None) -> list[RateLimitEntry]:
    fetched_at = raw.get("requested_at")
    normalized = []
    for entry in parse_rate_limits(raw):
        normalized.append(
            RateLimitEntry(
                provider="anthropic",
                workspace_id=workspace_id,
                group_type=entry.get("group_type"),
                models=entry.get("models"),
                limits=entry.get("limits"),
                fetched_at=fetched_at,
            )
        )
    return normalized
