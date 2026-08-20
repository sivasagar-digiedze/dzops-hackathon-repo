"""
Parser + normalizer for costs.

Anthropic returns cost as separate LINE ITEMS per cost_type (one row for
"tokens", a separate row for "web_search", etc.) within the same
(workspace_id, model, service_tier, context_window, period) combination.
To produce the requested shape — one record per dimension-combination
with token_cost / web_search_cost / code_execution_cost columns — this
normalizer groups Anthropic's raw line items by dimension-combination
and sums each cost_type into its own column. Every raw amount is still
summed into `total_cost`; nothing is dropped even if a cost_type isn't
one of the three Anthropic currently documents (an unrecognized
cost_type's amount still counts toward total_cost and is preserved
verbatim under provider_data.other_cost_types).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from ..models.normalized import CostRecord
from ..endpoints.costs import API_KEY_LIMITATION_NOTE


def parse_costs(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten cost buckets into one dict per raw (dimension-combo, cost_type) line item."""
    flattened: list[dict[str, Any]] = []
    for bucket in raw.get("records", []) or []:
        period_start = bucket.get("starting_at")
        period_end = bucket.get("ending_at")
        for result in bucket.get("results", []):  # empty results = no cost that day, correctly skipped
            item = dict(result)
            item["_period_start"] = period_start
            item["_period_end"] = period_end
            flattened.append(item)
    return flattened


_DIMENSION_KEY_FIELDS = ("workspace_id", "model", "service_tier", "context_window", "_period_start", "_period_end")


def _dimension_key(item: dict[str, Any]) -> tuple:
    return tuple(item.get(f) for f in _DIMENSION_KEY_FIELDS)


def _add_amount(total: Decimal, amount: Optional[str]) -> Decimal:
    if amount is None:
        return total
    try:
        return total + Decimal(str(amount))
    except InvalidOperation:
        return total


def normalize_costs(raw: dict[str, Any], *, organization_id: Optional[str] = None) -> list[CostRecord]:
    """
    Emit one CostRecord per raw Anthropic cost line item, preserving
    every field returned by the API inside `provider_data`. This keeps
    dimensions distinct (workspace_id, description, cost_type,
    token_type, service_account_id, context_window, etc.) and avoids
    aggregating separate cost types into a single combined row unless
    the API itself already groups them.
    """
    fetched_at = raw.get("requested_at")
    line_items = parse_costs(raw)

    # Ensure we emit at least one CostRecord per requested daily bucket
    # (Anthropic may return empty `results` for days with zero cost). Build
    # the set of expected daily period_starts from the request's date_range
    # and add placeholder line items with zero amounts for any missing day.
    date_range = raw.get("date_range") or {}
    starting_at = date_range.get("starting_at")
    ending_at = date_range.get("ending_at")
    if starting_at and ending_at:
        from datetime import datetime, timezone, timedelta

        def _parse_iso(s: str) -> datetime:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))

        start_dt = _parse_iso(starting_at)
        end_dt = _parse_iso(ending_at)
        expected_starts = set()
        cur = start_dt
        while cur < end_dt:
            expected_starts.add(cur.isoformat().replace("+00:00", "Z"))
            cur = cur + timedelta(days=1)

        seen_starts = {it.get("_period_start") for it in line_items}
        missing = expected_starts - seen_starts
        for ms in sorted(missing):
            # create a zero-amount placeholder line item preserving minimal
            # period info so normalization emits a single zero-cost record
            ms_dt = _parse_iso(ms.replace("Z", "+00:00"))
            line_items.append({
                "_period_start": ms,
                "_period_end": (ms_dt + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                "amount": "0",
                "cost_type": None,
                "workspace_id": None,
                "description": None,
                "currency": None,
            })

        # Filter out any line_items that fall outside the requested [start, end) range.
        filtered_items = []
        for it in line_items:
            ps = it.get("_period_start")
            if not ps:
                continue
            try:
                ps_dt = _parse_iso(ps)
            except Exception:
                # If parsing fails, conservatively skip the item
                continue
            # Include only if period_start is within [start_dt, end_dt)
            if ps_dt >= start_dt and ps_dt < end_dt:
                filtered_items.append(it)
        line_items = filtered_items

    normalized: list[CostRecord] = []
    for item in line_items:
        # Preserve all raw fields under provider_data, plus a note about
        # the API limitation for api_key_id.
        provider_data: dict[str, Any] = dict(item)
        provider_data.setdefault("api_key_id_limitation", API_KEY_LIMITATION_NOTE)

        # Amounts are per-line; map known cost_type placements to the
        # correct top-level columns and keep the raw amount in provider_data.
        amount = item.get("amount")
        cost_type = item.get("cost_type")
        token_cost = web_search_cost = code_execution_cost = session_runtime_cost = None
        if cost_type == "tokens":
            token_cost = str(Decimal(str(amount))) if amount is not None else None
        elif cost_type == "web_search":
            web_search_cost = str(Decimal(str(amount))) if amount is not None else None
        elif cost_type == "code_execution":
            code_execution_cost = str(Decimal(str(amount))) if amount is not None else None
        elif cost_type == "session_runtime":
            session_runtime_cost = str(Decimal(str(amount))) if amount is not None else None

        normalized.append(
            CostRecord(
                provider="anthropic",
                organization_id=organization_id,
                workspace_id=item.get("workspace_id"),
                api_key_id=None,
                model=item.get("model"),
                service_tier=item.get("service_tier"),
                token_cost=token_cost,
                web_search_cost=web_search_cost,
                code_execution_cost=code_execution_cost,
                session_runtime_cost=session_runtime_cost,
                total_cost=str(Decimal(str(amount))) if amount is not None else str(Decimal("0")),
                currency=item.get("currency"),
                period_start=item.get("_period_start"),
                period_end=item.get("_period_end"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )
    return normalized
