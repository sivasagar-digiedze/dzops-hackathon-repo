"""Parser + normalizer for API key metadata. Never touches secret material."""
from __future__ import annotations

from typing import Any

from ..models.normalized import ApiKeyMetadata


def parse_api_keys(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("records", []) or []


def normalize_api_keys(raw: dict[str, Any]) -> list[ApiKeyMetadata]:
    fetched_at = raw.get("requested_at")
    known_fields = {"id", "name", "status", "workspace_id", "created_by", "created_at", "type"}
    normalized = []
    for key in parse_api_keys(raw):
        provider_data = {k: v for k, v in key.items() if k not in known_fields}
        # partial_key_hint / expires_at (non-secret metadata) surface via provider_data
        normalized.append(
            ApiKeyMetadata(
                provider="anthropic",
                api_key_id=key.get("id"),
                name=key.get("name"),
                status=key.get("status"),
                workspace_id=key.get("workspace_id"),
                created_by_user_id=(key.get("created_by") or {}).get("id"),
                created_at=key.get("created_at"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )
    return normalized
