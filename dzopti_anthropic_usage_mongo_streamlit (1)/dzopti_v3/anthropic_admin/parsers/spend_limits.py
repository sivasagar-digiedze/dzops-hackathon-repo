"""Parser + normalizer for spend limits (Claude Enterprise only)."""
from __future__ import annotations

from typing import Any

from ..models.normalized import SpendLimitEntry, SpendLimitsResult


def parse_spend_limits(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if not raw.get("supported"):
        return []
    return raw.get("records", []) or []


def normalize_spend_limits(raw: dict[str, Any]) -> SpendLimitsResult:
    fetched_at = raw.get("requested_at")
    known_fields = {"scope", "amount", "currency", "period", "spend_limit_id", "period_to_date_spend"}

    entries = []
    for item in parse_spend_limits(raw):
        provider_data = {k: v for k, v in item.items() if k not in known_fields}
        entries.append(
            SpendLimitEntry(
                provider="anthropic",
                spend_limit_id=item.get("spend_limit_id"),
                scope=item.get("scope"),
                amount=item.get("amount"),
                currency=item.get("currency"),
                period=item.get("period"),
                period_to_date_spend=item.get("period_to_date_spend"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )

    return SpendLimitsResult(
        supported=bool(raw.get("supported")),
        reason=raw.get("reason"),
        records=entries,
    )
