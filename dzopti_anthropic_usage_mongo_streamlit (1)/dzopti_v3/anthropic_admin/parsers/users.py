"""Parser + normalizer for organization users."""
from __future__ import annotations

from typing import Any

from ..models.normalized import User


def parse_users(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("records", []) or []


def normalize_users(raw: dict[str, Any]) -> list[User]:
    fetched_at = raw.get("requested_at")
    known_fields = {"id", "email", "name", "role", "added_at", "type"}
    normalized = []
    for user in parse_users(raw):
        provider_data = {k: v for k, v in user.items() if k not in known_fields}
        normalized.append(
            User(
                provider="anthropic",
                user_id=user.get("id"),
                email=user.get("email"),
                name=user.get("name"),
                role=user.get("role"),
                added_at=user.get("added_at"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )
    return normalized
