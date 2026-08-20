"""
Parser + normalizer for usage.

Parse step: flatten Anthropic's [{starting_at, ending_at, results:[...]}]
    bucket shape into a flat list of (bucket_window + result) dicts —
    this is the one non-trivial "parsing" step in the whole pipeline,
    since usage genuinely nests one level deeper than the other list
    endpoints.
Normalize step: map each flattened raw dict onto the application's UsageRecord.
"""
from __future__ import annotations

from typing import Any

from ..models.normalized import UsageRecord


def parse_usage(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Flatten usage buckets into one dict per (time window, dimension
    combination) result, each carrying its own period_start/period_end.
    Every field Anthropic returned is preserved unchanged.

    A bucket with an empty `results: []` (a day with zero usage) is
    intentionally skipped here — it produces NO normalized UsageRecord,
    rather than a fake dimensionless row with invented-looking None
    token counts. The empty day is still fully preserved verbatim in the
    raw response (see raw_usage in the local JSON output); a dashboard
    that wants to show "0 tokens on 2026-08-16" derives that by noticing
    the date has no usage documents in its selected range, not by
    storing a phantom record for it. The `"results" not in bucket`
    fallback below only tolerates a hypothetical flat response shape
    (all fields at the bucket's top level) — it does NOT trigger just
    because `results` happens to be empty.
    """
    flattened: list[dict[str, Any]] = []
    for bucket in raw.get("records", []) or []:
        period_start = bucket.get("starting_at")
        period_end = bucket.get("ending_at")
        if "results" in bucket:
            results = bucket["results"]  # may legitimately be [] for a no-usage hour
        else:
            results = [bucket]  # tolerate a flat shape with no "results" wrapper at all
        # If there are no results for this hour, emit a single empty result
        # placeholder so hourly gaps are represented. Each placeholder
        # must still be expanded by context_window later in normalization.
        if not results:
            flattened.append({"_period_start": period_start, "_period_end": period_end})
            continue
        for result in results:
            item = dict(result)
            item["_period_start"] = period_start
            item["_period_end"] = period_end
            flattened.append(item)
    return flattened


def normalize_usage(raw: dict[str, Any], *, organization_id: str | None = None) -> list[UsageRecord]:
    fetched_at = raw.get("requested_at")
    known_fields = {
        "workspace_id", "api_key_id", "model", "service_tier",
        "uncached_input_tokens", "cache_creation", "cache_read_input_tokens",
        "output_tokens", "context_window", "inference_geo", "speed",
        "server_tool_use", "_period_start", "_period_end",
    }
    normalized = []
    # Expand each parsed item into one or more hourly records grouped by
    # context_window and other available dimensions. For empty-hour
    # placeholders (items with only _period_start/_period_end), emit
    # zeroed records for both supported context windows.
    for item in parse_usage(raw):
        cache_creation = item.get("cache_creation") or {}
        server_tool_use = item.get("server_tool_use") or {}
        cache_creation_tokens = (
            cache_creation.get("ephemeral_1h_input_tokens", 0) + cache_creation.get("ephemeral_5m_input_tokens", 0)
            if cache_creation
            else item.get("cache_creation_input_tokens")
        )
        # pick up the canonical dimensions (may be None)
        base_dims = {
            "workspace_id": item.get("workspace_id"),
            "api_key_id": item.get("api_key_id"),
            "model": item.get("model"),
            "service_tier": item.get("service_tier"),
            "inference_geo": item.get("inference_geo"),
            "service_account_id": item.get("service_account_id"),
            "speed": item.get("speed"),
        }

        # Determine context windows to emit for this item.
        context_windows = []
        if item.get("context_window"):
            context_windows = [item.get("context_window")]
        else:
            # If this was an empty-hour placeholder, emit both supported windows
            context_windows = ["0-200k", "200k-1M"]

        for ctx in context_windows:
            provider_data = {k: v for k, v in item.items() if k not in known_fields}
            provider_data["context_window"] = ctx
            if item.get("inference_geo"):
                provider_data["inference_geo"] = item.get("inference_geo")
            if item.get("speed"):
                provider_data["speed"] = item.get("speed")
            if server_tool_use:
                provider_data["web_search_requests"] = server_tool_use.get("web_search_requests")

            normalized.append(
                UsageRecord(
                    provider="anthropic",
                    organization_id=organization_id,
                    workspace_id=base_dims["workspace_id"],
                    api_key_id=base_dims["api_key_id"],
                    model=base_dims["model"],
                    service_tier=base_dims["service_tier"],
                    input_tokens=item.get("uncached_input_tokens") or 0,
                    output_tokens=item.get("output_tokens") or 0,
                    cache_creation_input_tokens=cache_creation_tokens or 0,
                    cache_read_input_tokens=item.get("cache_read_input_tokens") or 0,
                    request_count=item.get("num_requests") or item.get("request_count") or 0,
                    period_start=item.get("_period_start"),
                    period_end=item.get("_period_end"),
                    fetched_at=fetched_at,
                    provider_data=provider_data,
                )
            )
    return normalized
