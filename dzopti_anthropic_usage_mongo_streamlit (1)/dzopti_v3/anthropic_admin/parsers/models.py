"""Parser + normalizer for the models list."""
from __future__ import annotations

from typing import Any

from ..models.normalized import ModelInfo


def parse_models(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("records", []) or []


def normalize_models(raw: dict[str, Any]) -> list[ModelInfo]:
    fetched_at = raw.get("requested_at")
    normalized = []
    for model in parse_models(raw):
        normalized.append(
            ModelInfo(
                provider="anthropic",
                model_id=model.get("id"),
                display_name=model.get("display_name"),
                created_at=model.get("created_at"),
                fetched_at=fetched_at,
            )
        )
    return normalized
