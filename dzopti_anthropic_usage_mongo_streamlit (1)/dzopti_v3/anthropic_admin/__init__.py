"""
Dzopti — Anthropic Claude Platform Admin API integration (Phase 1:
fetch + normalize only; no database, no scheduler, no API layer).

Public entry points:
    AnthropicAdminConfig     (config.py)      — dev-phase hardcoded key loader
    AnthropicAdminClient     (client.py)      — low-level authenticated HTTP client
    collect_all()             (collector.py)   — full organization collection -> NormalizedResult
"""
from .client import AnthropicAdminClient
from .collector import collect_all
from .config import AnthropicAdminConfig

__all__ = ["AnthropicAdminClient", "AnthropicAdminConfig", "collect_all"]
