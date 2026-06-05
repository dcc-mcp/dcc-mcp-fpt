"""Runtime tests for ShotGrid users skill script (whoami)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
USERS = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-users" / "scripts"


def _load_script(name: str):
    path = USERS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_whoami_returns_effective_credentials():
    """whoami reports non-secret credentials when server is available."""
    module = _load_script("whoami")
    server = MagicMock()
    server.get_connection_info.return_value = {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "test_script",
        "authenticated": True,
        "server_version": "8.0.0",
        "request_context": {
            "effective_permission_level": "admin",
            "read_only": False,
            "project": "demo",
            "agent_context": {"credential_profile": None},
            "credentials": {"source": "env_default"},
        },
    }

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
    # Values are in result context per the whoami implementation
    ctx = result.get("context", {})
    assert ctx.get("script_name") == "test_script"
    assert ctx.get("authenticated") is True
    # Secrets must not appear in whoami output
    assert "api_key" not in str(result)


def test_whoami_no_server_error():
    """whoami returns error when no server is available."""
    module = _load_script("whoami")
    clear_current_server()

    result = module.main()

    assert result["success"] is False
    assert result["error"] == "NO_SERVER"


def test_whoami_with_request_context(monkeypatch):
    """whoami forwards _meta for request-scoped client resolution."""
    monkeypatch.setenv(
        "DCC_MCP_FPT_CREDENTIAL_PROFILES",
        '{"sg-read": {"url": "https://test.shotgrid.autodesk.com", "script_name": "reader", "script_key": "key", "permission_level": "read"}}',
    )
    module = _load_script("whoami")

    server = MagicMock()
    server.get_connection_info.return_value = {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "reader",
        "authenticated": True,
        "request_context": {
            "effective_permission_level": "read",
            "read_only": False,
            "agent_context": {"credential_profile": "sg-read"},
            "credentials": {"source": "credential_profile"},
        },
    }

    set_current_server(server)
    try:
        result = module.main(_meta={"credential_profile": "sg-read"})
    finally:
        clear_current_server(server)

    assert result["success"] is True
    server.get_connection_info.assert_called_once()
    ctx = result.get("context", {})
    assert ctx.get("credential_profile") == "sg-read"
    assert ctx.get("credential_source") == "credential_profile"


def test_whoami_does_not_leak_secrets(monkeypatch):
    """whoami output must never contain the API key."""
    module = _load_script("whoami")

    server = MagicMock()
    server.get_connection_info.return_value = {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "test_script",
        "authenticated": True,
        "request_context": {
            "credentials": {
                "source": "env_default",
                "script_name": "test_script",
                "url": "https://test.shotgrid.autodesk.com",
            },
            "effective_permission_level": "read",
        },
    }

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    ctx = result.get("context", {})
    assert "api_key" not in str(result)
    # script_key is never present in diagnostics
    assert ctx.get("api_key") is None
