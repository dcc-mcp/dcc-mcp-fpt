"""Tests for server lifecycle and diagnostics."""

from __future__ import annotations

from dcc_mcp_fpt.runtime_context import get_current_server
from dcc_mcp_fpt.server import ShotGridMcpServer


class TestServerLifecycle:
    """Tests for ShotGridMcpServer instantiation and lifecycle."""

    def test_server_instantiation_defaults(self):
        """Server can be instantiated without dcc-mcp-core."""
        server = ShotGridMcpServer(port=0, gateway_port=0)
        assert server._port == 0

    def test_server_connection_info_without_connect(self):
        """get_connection_info returns diagnostic dict without ShotGrid connection."""
        server = ShotGridMcpServer(
            port=0,
            shotgrid_url="https://test.shotgrid.autodesk.com",
            shotgrid_script_name="test",
            shotgrid_script_key="test",
            gateway_port=0,
        )
        info = server.get_connection_info()
        assert "url" in info
        assert "script_name" in info
        assert "authenticated" in info
        assert isinstance(info["authenticated"], bool)

    def test_server_gateway_info_without_core(self):
        """get_gateway_info returns disabled when dcc-mcp-core absent or gateway_port=0."""
        server = ShotGridMcpServer(port=0, gateway_port=0)
        info = server.get_gateway_info()
        assert "enabled" in info
        assert info["enabled"] is False

    def test_server_shutdown_clears_context(self):
        """Server.shutdown() releases pool and clears runtime context."""
        server = ShotGridMcpServer(port=0, gateway_port=0)
        assert get_current_server() is not None

        server.shutdown()
        assert get_current_server() is None


# Standalone functions using monkeypatch fixture


def test_server_connection_info_with_request_context(monkeypatch):
    """get_connection_info includes request_context when params have _meta."""
    monkeypatch.setenv(
        "DCC_MCP_FPT_CREDENTIAL_PROFILES",
        '{"sg-test": {"url": "https://test.shotgrid.autodesk.com", "script_name": "test", "script_key": "key"}}',
    )
    server = ShotGridMcpServer(
        port=0,
        shotgrid_url="https://default.shotgrid.autodesk.com",
        shotgrid_script_name="default",
        shotgrid_script_key="default-key",
        gateway_port=0,
    )
    # When ShotGrid is not reachable, get_connection_info catches the error
    # and includes request_context diagnostics in the error info dict.
    info = server.get_connection_info({"_meta": {"credential_profile": "sg-test"}})
    assert "request_context" in info, f"Expected request_context in info, got keys: {list(info.keys())}"
    ctx = info["request_context"]
    if "credentials" in ctx:
        assert "api_key" not in ctx["credentials"]


def test_server_gateway_labels_with_project(monkeypatch):
    """Gateway labels reflect ShotGrid project when set."""
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_SCENE", raising=False)
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", raising=False)
    monkeypatch.delenv("SHOTGRID_PROJECT", raising=False)
    monkeypatch.delenv("SHOTGRID_DEFAULT_PROJECT", raising=False)

    server = ShotGridMcpServer(port=0, shotgrid_project="demo", gateway_port=0)
    assert server._gateway_scene_label() == "project:demo"
    assert server._gateway_display_label() == "FPT demo"


def test_server_gateway_labels_with_project_id(monkeypatch):
    """Gateway labels use project ID when name is not set."""
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_SCENE", raising=False)
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", raising=False)
    monkeypatch.delenv("SHOTGRID_PROJECT", raising=False)
    monkeypatch.delenv("SHOTGRID_DEFAULT_PROJECT", raising=False)

    server = ShotGridMcpServer(port=0, shotgrid_project_id=192, gateway_port=0)
    assert server._gateway_scene_label() == "project-id:192"
