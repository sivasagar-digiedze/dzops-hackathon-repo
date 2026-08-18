"""
One generic, reusable pagination mechanism shared by every endpoint
module (workspaces, users, api_keys, usage, costs, rate_limits, models,
...) — no endpoint re-implements its own page loop.

Anthropic uses two different field names for "the cursor to send back
on the next request" depending on the endpoint family (`next_page` for
Usage/Cost/Rate-Limits/Spend-Limits, `last_id` for the general resource
"list" convention used by workspaces/users/api_keys/models). Rather than
writing two near-duplicate loops, this module has ONE loop
(`paginate_all`) and takes a small `get_next_cursor(response)` function
from the caller that knows which field to read. Each endpoint module
supplies a one-line lambda for that; the loop, safety limits, and raw
page preservation live in exactly one place.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional

from .exceptions import PaginationError

logger = logging.getLogger("dzopti.anthropic_admin.pagination")

DEFAULT_MAX_PAGES = 500


@dataclass
class PageResult:
    """Aggregated result of paginating one endpoint to completion."""

    records: List[dict] = field(default_factory=list)
    raw_pages: List[dict] = field(default_factory=list)  # [{"page": n, "response": {...}}, ...]
    pages_fetched: int = 0
    truncated: bool = False  # True only if max_pages was hit before pagination naturally ended


async def paginate_all(
    fetch_page: Callable[[Optional[str]], Awaitable[dict]],
    get_next_cursor: Callable[[dict], Optional[str]],
    *,
    records_key: str = "data",
    max_pages: int = DEFAULT_MAX_PAGES,
    endpoint_name: str = "",
) -> PageResult:
    """
    Generic pagination loop.

    fetch_page(cursor): perform one HTTP GET, passing the cursor value
        (None on the first call) however that endpoint expects it, and
        return the parsed JSON body.
    get_next_cursor(response): return the cursor to use for the next
        call, or None when there are no more pages. Encapsulates the
        endpoint-specific field name (next_page / last_id / etc).

    Loops until get_next_cursor returns None, a hard max_pages safety
    cap is hit, or a repeated cursor is detected (defensive against a
    malformed response that would otherwise loop forever). Every raw
    page is preserved in `raw_pages` — no records are ever dropped.
    """
    result = PageResult()
    cursor: Optional[str] = None
    seen_cursors: set = set()

    while True:
        if result.pages_fetched >= max_pages:
            logger.warning(
                "anthropic_admin.pagination.max_pages_hit",
                extra={"pg_endpoint": endpoint_name, "max_pages": max_pages},
            )
            result.truncated = True
            break

        response = await fetch_page(cursor)
        if not isinstance(response, dict):
            raise PaginationError(f"Malformed page response for {endpoint_name}: expected dict, got {type(response)!r}")

        page_records = response.get(records_key)
        if page_records is None:
            page_records = []
        elif not isinstance(page_records, list):
            raise PaginationError(
                f"Malformed pagination response for {endpoint_name}: '{records_key}' is not a list"
            )

        result.pages_fetched += 1
        result.records.extend(page_records)
        result.raw_pages.append({"page": result.pages_fetched, "response": response})

        logger.info(
            "anthropic_admin.pagination.page_fetched",
            extra={
                "pg_endpoint": endpoint_name,
                "page": result.pages_fetched,
                "records_in_page": len(page_records),
                "total_records_so_far": len(result.records),
            },
        )

        next_cursor = get_next_cursor(response)
        if not next_cursor:
            break

        if next_cursor in seen_cursors:
            logger.error(
                "anthropic_admin.pagination.repeated_cursor",
                extra={"pg_endpoint": endpoint_name, "cursor": next_cursor},
            )
            raise PaginationError(
                f"Pagination cursor repeated for {endpoint_name}; aborting to avoid an infinite loop."
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return result


# --- Ready-made cursor extractors for Anthropic's two documented styles ---

def next_page_cursor(response: dict) -> Optional[str]:
    """For Usage / Cost / Rate Limits / Spend Limits: has_more + next_page."""
    if not response.get("has_more"):
        return None
    return response.get("next_page") or None


def last_id_cursor(response: dict) -> Optional[str]:
    """For workspaces / users / api_keys / models: has_more + last_id -> after_id."""
    if not response.get("has_more"):
        return None
    return response.get("last_id") or None
