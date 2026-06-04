"""Tests for request-scoped ShotGrid context resolution."""

from __future__ import annotations

import json

import pytest

from dcc_mcp_fpt.access import PermissionLevel, ShotGridAccessPolicy
from dcc_mcp_fpt.exceptions import ShotGridPermissionError
from dcc_mcp_fpt.request_context import extract_agent_context, resolve_request_context
from dcc_mcp_fpt.server import ShotGridMcpServer


def test_extract_agent_context_accepts_mcp_meta():
    context = extract_agent_context(
        {
            "_meta": {
                "agent_context": {
                    "requester_id": "hallong",
                    "requester_type": "human",
                    "credential_profile": "sg-read-zombie",
                    "permission_hint": "read",
                    "project_scope": "demo",
                    "project_id": "192",
                }
            }
        }
    )

    assert context.requester_id == "hallong"
    assert context.credential_profile == "sg-read-zombie"
    assert context.project_id == 192


def test_extract_agent_context_accepts_core_pip520_meta_shape():
    context = extract_agent_context(
        {
            "_meta": {
                "agent_context": {
                    "actor_id": "artist-42",
                    "agent_name": "codex",
                    "session_id": "session-1",
                },
                "credential_profile": "sg-read-zombie",
                "permission_hint": "read-only",
                "project_scope": "movie-42",
                "project_id": "192",
            }
        }
    )

    assert context.requester_id == "artist-42"
    assert context.credential_profile == "sg-read-zombie"
    assert context.permission_hint == "read-only"
    assert context.project_scope == "movie-42"
    assert context.project_id == 192


def test_top_level_meta_overrides_legacy_nested_controls():
    context = extract_agent_context(
        {
            "_meta": {
                "agent_context": {
                    "requester_id": "artist-42",
                    "credential_profile": "legacy-profile",
                    "permission_hint": "admin",
                    "project_scope": "legacy_project",
                },
                "credential_profile": "sg-read-zombie",
                "permission_hint": "read-only",
                "project_scope": "movie-42",
            }
        }
    )

    assert context.credential_profile == "sg-read-zombie"
    assert context.permission_hint == "read-only"
    assert context.project_scope == "movie-42"


def test_resolve_request_context_uses_profile_and_caps_policy(monkeypatch):
    monkeypatch.setenv(
        "DCC_MCP_FPT_CREDENTIAL_PROFILES",
        json.dumps(
            {
                "sg-read-zombie": {
                    "url": "https://profile.shotgrid.autodesk.com",
                    "script_name": "zombie_reader",
                    "script_key": "secret",
                    "permission_level": "read",
                    "read_only": True,
                    "project": "profile_project",
                }
            }
        ),
    )

    resolved = resolve_request_context(
        {
            "_meta": {
                "agent_context": {"actor_id": "hallong"},
                "credential_profile": "sg-read-zombie",
                "permission_hint": "admin",
                "project_scope": "request_project",
            }
        },
        base_policy=ShotGridAccessPolicy(default_level=PermissionLevel.ADMIN),
    )

    assert resolved.credentials.source == "credential_profile"
    assert resolved.credentials.script_name == "zombie_reader"
    assert resolved.access_policy.default_level == PermissionLevel.READ
    assert resolved.access_policy.read_only is True
    assert resolved.default_project == "request_project"
    assert "api_key" not in resolved.diagnostics()["credentials"]
    with pytest.raises(ShotGridPermissionError, match="read-only"):
        resolved.access_policy.require("update")


def test_resolve_request_context_rejects_unknown_profile(monkeypatch):
    monkeypatch.setenv("DCC_MCP_FPT_CREDENTIAL_PROFILES", "{}")

    with pytest.raises(ValueError, match="Unknown ShotGrid credential_profile"):
        resolve_request_context({"agent_context": {"credential_profile": "missing"}})


def test_resolve_request_context_rejects_inline_credentials_by_default(monkeypatch):
    monkeypatch.delenv("DCC_MCP_ALLOW_INLINE_CREDENTIALS", raising=False)
    params = {
        "agent_context": {
            "credentials": {
                "url": "https://inline.shotgrid.autodesk.com",
                "script_name": "inline",
                "script_key": "secret",
            }
        }
    }

    with pytest.raises(ValueError, match="Inline ShotGrid credentials are disabled"):
        resolve_request_context(params)


def test_resolve_request_context_allows_inline_credentials_for_dev(monkeypatch):
    monkeypatch.setenv("DCC_MCP_ALLOW_INLINE_CREDENTIALS", "1")

    resolved = resolve_request_context(
        {
            "agent_context": {
                "credentials": {
                    "url": "https://inline.shotgrid.autodesk.com",
                    "script_name": "inline",
                    "script_key": "secret",
                }
            }
        }
    )

    assert resolved.credentials.source == "inline_credentials"
    assert resolved.credentials.script_name == "inline"


def test_server_client_for_request_uses_profile(monkeypatch):
    monkeypatch.setenv(
        "DCC_MCP_FPT_CREDENTIAL_PROFILES",
        json.dumps(
            {
                "sg-write-user": {
                    "url": "https://profile.shotgrid.autodesk.com",
                    "script_name": "writer",
                    "script_key": "secret",
                    "permission_level": "write",
                }
            }
        ),
    )
    server = ShotGridMcpServer(
        port=0,
        shotgrid_url="https://default.shotgrid.autodesk.com",
        shotgrid_script_name="default",
        shotgrid_script_key="default-secret",
        gateway_port=0,
        access_policy=ShotGridAccessPolicy(default_level=PermissionLevel.ADMIN),
    )

    client = server.client_for_request({"_meta": {"credential_profile": "sg-write-user"}})

    info = client.get_connection_info().model_dump()
    assert info["url"] == "https://profile.shotgrid.autodesk.com"
    assert info["script_name"] == "writer"
    assert client._access_policy.default_level == PermissionLevel.WRITE
