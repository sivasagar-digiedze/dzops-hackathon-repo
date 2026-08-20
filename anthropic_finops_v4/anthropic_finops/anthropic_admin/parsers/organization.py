"""
Parser + normalizer for the organization resource.

Parse step: extract the single raw object from the endpoint wrapper.
Normalize step: map Anthropic's field names onto the application's Organization
    model, moving anything Anthropic-specific into provider_data.
"""
from __future__ import annotations

from typing import Any, Optional

from ..models.normalized import Organization


def parse_organization(raw: dict[str, Any]) -> dict[str, Any]:
    """Pull the raw Anthropic organization object out of the endpoint wrapper."""
    return raw.get("response", {}) or {}


def normalize_organization(raw: dict[str, Any]) -> Organization:
    parsed = parse_organization(raw)
    known_fields = {"id", "name", "type"}
    provider_data = {k: v for k, v in parsed.items() if k not in known_fields}

    return Organization(
        provider="anthropic",
        organization_id=parsed.get("id"),
        organization_name=parsed.get("name"),
        fetched_at=raw.get("requested_at"),
        provider_data=provider_data,
    )
