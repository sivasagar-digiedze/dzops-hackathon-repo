"""
Normalized, provider-independent FinOps data model.

Design principle: fields that are meaningful across ANY LLM provider
(Anthropic, OpenAI, Azure OpenAI, Bedrock, Vertex, ...) are promoted to
top-level, common-name fields. Fields that are Anthropic-specific (e.g.
`inference_geo`, `context_window` bucketing, `partial_key_hint`) live
inside a `provider_data` dict on the record instead of being invented
as if every provider had them — a future OpenAI provider module will
populate the same top-level fields plus its own, different
`provider_data`.

Every dataclass has `.to_dict()` for JSON serialization. None of these
classes ever hold the API key.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


def _to_dict(obj: Any) -> dict:
    return asdict(obj)


# --------------------------------------------------------------------------
# Core resources
# --------------------------------------------------------------------------

@dataclass
class Organization:
    provider: str
    organization_id: Optional[str]
    organization_name: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class Workspace:
    provider: str
    workspace_id: Optional[str]
    workspace_name: Optional[str]
    status: str  # "active" | "archived"
    created_at: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class WorkspaceMember:
    provider: str
    workspace_id: Optional[str]
    user_id: Optional[str]
    role: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class User:
    provider: str
    user_id: Optional[str]
    email: Optional[str]
    name: Optional[str]
    role: Optional[str]
    added_at: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class ApiKeyMetadata:
    provider: str
    api_key_id: Optional[str]
    name: Optional[str]
    status: Optional[str]
    workspace_id: Optional[str]
    created_by_user_id: Optional[str]
    created_at: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)  # e.g. partial_key_hint, expires_at

    def to_dict(self) -> dict:
        return _to_dict(self)


# --------------------------------------------------------------------------
# Usage
# --------------------------------------------------------------------------

@dataclass
class UsageRecord:
    provider: str
    organization_id: Optional[str]
    workspace_id: Optional[str]
    api_key_id: Optional[str]
    model: Optional[str]
    service_tier: Optional[str]

    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cache_creation_input_tokens: Optional[int]
    cache_read_input_tokens: Optional[int]
    request_count: Optional[int]

    period_start: Optional[str]
    period_end: Optional[str]

    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)  # context_window, inference_geo, speed, web_search_requests

    def to_dict(self) -> dict:
        return _to_dict(self)


# NOTE: Cost (CostRecord / CalculatedCostTotal / the Cost API) is
# intentionally NOT implemented in this phase. See collector.py and the
# project README for why — it will be re-added as its own phase later.

# --------------------------------------------------------------------------
# Cost
#
# Verified against Anthropic's official Cost API reference
# (GET /v1/organizations/cost_report):
#   - group_by[] supports ONLY "workspace_id" and "description" — there is
#     NO api_key_id dimension anywhere in the Cost API. api_key_id is
#     therefore ALWAYS None on a CostRecord, not because we failed to
#     capture it, but because Anthropic's Cost API does not expose it at
#     any granularity. This is documented, not invented.
#   - bucket_width for cost_report accepts ONLY "1d" — there is no hourly
#     cost granularity. Cost stays daily even though usage is hourly.
#   - When grouped by "description", each row includes model,
#     service_tier, context_window, cost_type, and token_type inline —
#     that's how model/service_tier attribution becomes possible for cost
#     despite there being no explicit group_by=model option.
#   - "session_runtime_cost" is NOT a confirmed Anthropic cost_type in the
#     public API reference. The field exists on CostRecord for schema
#     symmetry with the requested output shape, but is always None/0
#     unless a future Anthropic response actually returns that category —
#     it is never fabricated.
# --------------------------------------------------------------------------

@dataclass
class CostRecord:
    provider: str
    organization_id: Optional[str]
    workspace_id: Optional[str]
    api_key_id: Optional[str]  # ALWAYS None — Anthropic's Cost API has no api_key_id dimension (see note above)
    model: Optional[str]
    service_tier: Optional[str]

    token_cost: Optional[str]           # sum of cost_type == "tokens" line items, decimal string, USD
    web_search_cost: Optional[str]      # sum of cost_type == "web_search" line items
    code_execution_cost: Optional[str]  # sum of cost_type == "code_execution" line items
    session_runtime_cost: Optional[str] # always None unless Anthropic returns this cost_type (not currently documented)
    total_cost: Optional[str]           # sum of every cost_type for this dimension combination

    currency: Optional[str]

    period_start: Optional[str]
    period_end: Optional[str]

    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)  # context_window, token_type breakdown, per-cost_type raw amounts

    def to_dict(self) -> dict:
        return _to_dict(self)


# --------------------------------------------------------------------------
# Rate limits / spend limits / models
# --------------------------------------------------------------------------

@dataclass
class RateLimitEntry:
    provider: str
    workspace_id: Optional[str]  # None => organization-level
    group_type: Optional[str]
    models: Optional[list]
    limits: Optional[list]
    fetched_at: Optional[str]

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class SpendLimitEntry:
    provider: str
    spend_limit_id: Optional[str]
    scope: Optional[dict]
    amount: Optional[str]
    currency: Optional[str]
    period: Optional[str]
    period_to_date_spend: Optional[str]
    fetched_at: Optional[str]
    provider_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class SpendLimitsResult:
    supported: bool
    reason: Optional[str]
    records: list  # list[SpendLimitEntry]

    def to_dict(self) -> dict:
        return {
            "supported": self.supported,
            "reason": self.reason,
            "records": [r.to_dict() for r in self.records],
        }


@dataclass
class ModelInfo:
    provider: str
    model_id: Optional[str]
    display_name: Optional[str]
    created_at: Optional[str]
    fetched_at: Optional[str]

    def to_dict(self) -> dict:
        return _to_dict(self)


# --------------------------------------------------------------------------
# Collection-level metadata
# --------------------------------------------------------------------------

@dataclass
class CollectionError:
    component: str
    type: str
    message: str
    status_code: Optional[int] = None
    request_id: Optional[str] = None

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class CollectionMetadata:
    started_at: str
    completed_at: str
    success: bool  # False only if an AuthenticationError aborted the whole run
    partial: bool  # True if any optional component failed or is unsupported
    date_range: dict
    requests_made: int
    pages_fetched: int
    capabilities: dict  # {"organization": True, "spend_limits": False, ...}

    def to_dict(self) -> dict:
        return _to_dict(self)


@dataclass
class NormalizedResult:
    """Top-level normalized structure for one provider collection run."""

    provider: str
    organization: Optional[Organization]
    workspaces: list  # list[Workspace]
    workspace_members: list  # list[WorkspaceMember]
    users: list  # list[User]
    api_keys: list  # list[ApiKeyMetadata]
    usage: list  # list[UsageRecord]
    costs: list  # list[CostRecord]
    rate_limits: list  # list[RateLimitEntry]
    spend_limits: SpendLimitsResult
    models: list  # list[ModelInfo]
    metadata: CollectionMetadata
    errors: list  # list[CollectionError]

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "organization": self.organization.to_dict() if self.organization else None,
            "workspaces": [w.to_dict() for w in self.workspaces],
            "workspace_members": [m.to_dict() for m in self.workspace_members],
            "users": [u.to_dict() for u in self.users],
            "api_keys": [k.to_dict() for k in self.api_keys],
            "usage": [u.to_dict() for u in self.usage],
            "costs": [c.to_dict() for c in self.costs],
            "rate_limits": [r.to_dict() for r in self.rate_limits],
            "spend_limits": self.spend_limits.to_dict(),
            "models": [m.to_dict() for m in self.models],
            "metadata": self.metadata.to_dict(),
            "errors": [e.to_dict() for e in self.errors],
        }
