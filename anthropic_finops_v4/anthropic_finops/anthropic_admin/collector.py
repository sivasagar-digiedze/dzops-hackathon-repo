"""
Collector — orchestrates every Admin API resource fetch for one
organization, runs each through its parser + normalizer, and assembles
the application's NormalizedResult.

Data flow:

    Anthropic Admin API
            |
        HTTP Client            (client.py)
            |
       Raw JSON response       (endpoints/*.py — fetch_x(), kept only
            |                   in memory for this one call, never
            |                   attached to the returned result)
          Parser                (parsers/*.py — parse_x())
            |
        Normalizer               (parsers/*.py — normalize_x())
            |
    Normalized model               (models/normalized.py — the ONLY
                                     thing NormalizedResult.to_dict()
                                     exposes; no raw Anthropic response
                                     ever appears in the final JSON)

Concurrency: organization is fetched first and alone — its `id` tags
every other record, and it's the cheapest way to fail fast on a bad
Admin key before nine more calls fail identically. Everything else that
doesn't depend on the workspace list runs concurrently via
asyncio.gather. Once the workspace list is known, per-workspace
member/rate-limit calls also run concurrently with each other, bounded
by MAX_CONCURRENT_WORKSPACE_CALLS.

Granularity: usage defaults to bucket_width="1h" (hourly). Cost stays at
Anthropic's only supported bucket_width, "1d" — see endpoints/costs.py
for why hourly cost isn't a documented capability.

Error isolation: one optional endpoint failing never discards data from
the others. Only AuthenticationError aborts the whole run.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from .client import AnthropicAdminClient
from .config import AnthropicAdminConfig
from .exceptions import AnthropicAPIError, AuthenticationError
from .endpoints import api_keys as ep_api_keys
from .endpoints import costs as ep_costs
from .endpoints import models as ep_models
from .endpoints import organization as ep_organization
from .endpoints import rate_limits as ep_rate_limits
from .endpoints import spend_limits as ep_spend_limits
from .endpoints import usage as ep_usage
from .endpoints import users as ep_users
from .endpoints import workspaces as ep_workspaces
from .models.normalized import CollectionError, CollectionMetadata, NormalizedResult
from .parsers import api_keys as p_api_keys
from .parsers import costs as p_costs
from .parsers import models as p_models
from .parsers import organization as p_organization
from .parsers import rate_limits as p_rate_limits
from .parsers import spend_limits as p_spend_limits
from .parsers import usage as p_usage
from .parsers import users as p_users
from .parsers import workspaces as p_workspaces

logger = logging.getLogger("anthropic_admin.collector")

MAX_CONCURRENT_WORKSPACE_CALLS = 5


class _ComponentOutcome:
    __slots__ = ("component", "ok", "not_supported", "error")

    def __init__(self, component: str) -> None:
        self.component = component
        self.ok = False
        self.not_supported = False
        self.error: Optional[CollectionError] = None


async def _run_component(name: str, coro) -> tuple[_ComponentOutcome, Any]:
    outcome = _ComponentOutcome(name)
    try:
        result = await coro
        outcome.ok = True
        return outcome, result
    except AnthropicAPIError as exc:
        logger.error(
            "anthropic_admin.component_failed",
            extra={"cl_component": name, "cl_status_code": exc.status_code, "cl_type": exc.error_type},
        )
        outcome.error = CollectionError(
            component=name, type=exc.error_type or "api_error", message=exc.message,
            status_code=exc.status_code, request_id=exc.request_id,
        )
        return outcome, None


async def collect_all(
    config: AnthropicAdminConfig,
    *,
    usage_starting_at: str,
    usage_ending_at: str,
    usage_bucket_width: str = "1d",
    usage_group_by: Sequence[str] = ep_usage.DEFAULT_GROUP_BY,
    cost_starting_at: Optional[str] = None,
    cost_ending_at: Optional[str] = None,
    fetch_workspace_details: bool = True,
    fetch_costs: bool = True,
) -> NormalizedResult:
    """
    Run the full organization-level collection and return a NormalizedResult.
    Raises AuthenticationError if the Admin key itself is invalid — every
    other endpoint failure is caught and recorded instead of raised.

    cost_starting_at/cost_ending_at default to the same window as usage
    if not given separately. Cost is always fetched at 1d granularity
    (see endpoints/costs.py) regardless of usage_bucket_width.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    cost_starting_at = cost_starting_at or usage_starting_at
    cost_ending_at = cost_ending_at or usage_ending_at

    outcomes: list[_ComponentOutcome] = []
    requests_made = 0
    pages_fetched = 0

    def _track_pages(raw: Optional[dict]) -> None:
        nonlocal requests_made, pages_fetched
        if raw:
            n = raw.get("pages_fetched", 0)
            requests_made += n
            pages_fetched += n

    async with AnthropicAdminClient(config) as client:
        logger.info("anthropic_admin.collection_start")
        try:
            org_raw = await ep_organization.fetch_organization(client)
        except AuthenticationError:
            logger.critical("anthropic_admin.authentication_failed")
            raise
        org_outcome = _ComponentOutcome("organization")
        org_outcome.ok = True
        outcomes.append(org_outcome)
        requests_made += 1
        organization = p_organization.normalize_organization(org_raw)
        organization_id = organization.organization_id

        # Fetch only resources required for usage + costs. We still fetch
        # workspaces/users/models optionally for in-memory normalization,
        # but per requirements we will NOT persist them to MongoDB.
        gather_tasks = [
            _run_component("workspaces", ep_workspaces.fetch_workspaces(client)),
            _run_component("users", ep_users.fetch_users(client)),
            _run_component("api_keys", ep_api_keys.fetch_api_keys(client)),
            _run_component(
                "usage",
                ep_usage.fetch_usage(
                    client, starting_at=usage_starting_at, ending_at=usage_ending_at,
                    bucket_width=usage_bucket_width, group_by=usage_group_by,
                    use_speed_beta=True,
                ),
            ),
            _run_component("rate_limits_organization", ep_rate_limits.fetch_organization_rate_limits(client)),
            _run_component("models", ep_models.fetch_models(client)),
        ]

        # Conditionally include costs fetching
        if fetch_costs:
            gather_tasks.append(
                _run_component(
                    "costs",
                    ep_costs.fetch_costs(client, starting_at=cost_starting_at, ending_at=cost_ending_at),
                )
            )

        results = await asyncio.gather(*gather_tasks)

        # Map results back depending on whether costs were requested
        idx = 0
        (ws_outcome, ws_raw) = results[idx]; idx += 1
        (users_outcome, users_raw) = results[idx]; idx += 1
        (keys_outcome, keys_raw) = results[idx]; idx += 1
        (usage_outcome, usage_raw) = results[idx]; idx += 1
        (org_rl_outcome, org_rl_raw) = results[idx]; idx += 1
        (models_outcome, models_raw) = results[idx]; idx += 1
        outcomes.extend([ws_outcome, users_outcome, keys_outcome, usage_outcome, org_rl_outcome, models_outcome])
        for raw in (ws_raw, users_raw, keys_raw, usage_raw, org_rl_raw, models_raw):
            _track_pages(raw)

        costs_raw = None
        if fetch_costs:
            (costs_outcome, costs_raw) = results[idx]
            outcomes.append(costs_outcome)
            _track_pages(costs_raw)

        spend_outcome = _ComponentOutcome("spend_limits")
        try:
            spend_raw = await ep_spend_limits.fetch_spend_limits(client)
            if spend_raw.get("supported"):
                spend_outcome.ok = True
                _track_pages(spend_raw)
            else:
                spend_outcome.not_supported = True
        except AnthropicAPIError as exc:
            spend_outcome.error = CollectionError(
                component="spend_limits", type=exc.error_type or "api_error",
                message=exc.message, status_code=exc.status_code, request_id=exc.request_id,
            )
            spend_raw = {"supported": False, "reason": str(exc)}
        outcomes.append(spend_outcome)

        workspaces = p_workspaces.normalize_workspaces(ws_raw) if ws_raw else []

        workspace_members: list = []
        rate_limits = p_rate_limits.normalize_rate_limits(org_rl_raw, workspace_id=None) if org_rl_raw else []

        if fetch_workspace_details and workspaces:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKSPACE_CALLS)

            async def _fetch_one_workspace(ws) -> tuple[str, Any, Any]:
                async with semaphore:
                    members_task = _run_component(
                        f"workspace_members[{ws.workspace_id}]",
                        ep_workspaces.fetch_workspace_members(client, ws.workspace_id),
                    )
                    rl_task = _run_component(
                        f"workspace_rate_limits[{ws.workspace_id}]",
                        ep_rate_limits.fetch_workspace_rate_limits(client, ws.workspace_id),
                    )
                    members_result, rl_result = await asyncio.gather(members_task, rl_task)
                    return ws.workspace_id, members_result, rl_result

            per_workspace_results = await asyncio.gather(*(_fetch_one_workspace(ws) for ws in workspaces))
            for ws_id, (m_outcome, m_raw), (rl_outcome, rl_raw) in per_workspace_results:
                outcomes.extend([m_outcome, rl_outcome])
                _track_pages(m_raw)
                _track_pages(rl_raw)
                if m_raw:
                    workspace_members.extend(p_workspaces.normalize_workspace_members(m_raw, ws_id))
                if rl_raw:
                    rate_limits.extend(p_rate_limits.normalize_rate_limits(rl_raw, workspace_id=ws_id))

    # --- Normalize everything collected above (raw dicts go out of scope after this) ---
    users = p_users.normalize_users(users_raw) if users_raw else []
    api_keys_normalized = p_api_keys.normalize_api_keys(keys_raw) if keys_raw else []
    usage_records = p_usage.normalize_usage(usage_raw, organization_id=organization_id) if usage_raw else []
    cost_records = p_costs.normalize_costs(costs_raw, organization_id=organization_id) if costs_raw else []
    spend_limits_result = p_spend_limits.normalize_spend_limits(spend_raw)
    models_normalized = p_models.normalize_models(models_raw) if models_raw else []

    completed_at = datetime.now(timezone.utc).isoformat()

    capabilities = {o.component: o.ok for o in outcomes if "[" not in o.component}
    errors = [o.error for o in outcomes if o.error is not None]
    partial = any((not o.ok) for o in outcomes)

    metadata = CollectionMetadata(
        started_at=started_at,
        completed_at=completed_at,
        success=True,
        partial=partial,
        date_range={
            "usage": {"starting_at": usage_starting_at, "ending_at": usage_ending_at, "bucket_width": usage_bucket_width},
            # costs removed per new requirement
            "costs": {"note": "removed_by_requirement"},
        },
        requests_made=requests_made,
        pages_fetched=pages_fetched,
        capabilities=capabilities,
    )

    logger.info(
        "anthropic_admin.collection_done",
        extra={"cl_requests_made": requests_made, "cl_pages_fetched": pages_fetched, "cl_errors": len(errors)},
    )

    return NormalizedResult(
        provider="anthropic",
        organization=organization,
        workspaces=workspaces,
        workspace_members=workspace_members,
        users=users,
        api_keys=api_keys_normalized,
        usage=usage_records,
        costs=cost_records,
        rate_limits=rate_limits,
        spend_limits=spend_limits_result,
        models=models_normalized,
        metadata=metadata,
        errors=errors,
    )
