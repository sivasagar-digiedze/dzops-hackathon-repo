"""Parser + normalizer for workspaces and workspace members."""
from __future__ import annotations

from typing import Any

from ..models.normalized import Workspace, WorkspaceMember


def parse_workspaces(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the flat list of raw workspace objects across all pages."""
    return raw.get("records", []) or []


def normalize_workspaces(raw: dict[str, Any]) -> list[Workspace]:
    fetched_at = raw.get("requested_at")
    known_fields = {"id", "name", "type", "archived_at", "created_at", "display_color"}
    normalized = []
    for ws in parse_workspaces(raw):
        provider_data = {k: v for k, v in ws.items() if k not in known_fields}
        if ws.get("display_color"):
            provider_data["display_color"] = ws["display_color"]
        normalized.append(
            Workspace(
                provider="anthropic",
                workspace_id=ws.get("id"),
                workspace_name=ws.get("name"),
                status="archived" if ws.get("archived_at") else "active",
                created_at=ws.get("created_at"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )
    return normalized


def parse_workspace_members(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("records", []) or []


def normalize_workspace_members(raw: dict[str, Any], workspace_id: str) -> list[WorkspaceMember]:
    fetched_at = raw.get("requested_at")
    known_fields = {"user_id", "workspace_role", "type"}
    normalized = []
    for member in parse_workspace_members(raw):
        provider_data = {k: v for k, v in member.items() if k not in known_fields}
        normalized.append(
            WorkspaceMember(
                provider="anthropic",
                workspace_id=workspace_id,
                user_id=member.get("user_id"),
                role=member.get("workspace_role"),
                fetched_at=fetched_at,
                provider_data=provider_data,
            )
        )
    return normalized
