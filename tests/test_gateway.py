"""Tests for dcc-mcp gateway integration."""

from __future__ import annotations

import os
from types import SimpleNamespace

from dcc_mcp_fpt import DEFAULT_PORT
from dcc_mcp_fpt import server as server_module
from dcc_mcp_fpt.cli import _apply_skill_paths, _normalize_gateway_port, build_arg_parser
from dcc_mcp_fpt.server import ShotGridMcpServer, _resolve_gateway_failover


def test_gateway_labels_default_to_project(monkeypatch):
    """Gateway scene and display labels default to the configured project."""
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_SCENE", raising=False)
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", raising=False)

    server = ShotGridMcpServer(port=0, shotgrid_project="demo_project", gateway_port=0)

    assert server._gateway_scene_label() == "project:demo_project"
    assert server._gateway_display_label() == "FPT demo_project"
    info = server.get_gateway_info()
    assert info["enabled"] is False
    assert info["scene"] == "project:demo_project"
    assert info["display_name"] == "FPT demo_project"


def test_gateway_labels_accept_explicit_overrides(monkeypatch):
    """Explicit gateway metadata wins over derived project labels."""
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_SCENE", raising=False)
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", raising=False)

    server = ShotGridMcpServer(
        port=0,
        shotgrid_project="demo_project",
        gateway_port=0,
        gateway_scene="project:custom",
        gateway_display_name="FPT Custom",
        dcc_version="dcc-mcp-fpt/custom",
    )

    assert server._gateway_scene_label() == "project:custom"
    assert server._gateway_display_label() == "FPT Custom"
    assert server.get_gateway_info()["version"] == "dcc-mcp-fpt/custom"


def test_gateway_info_reports_enabled_port_without_starting_gateway(monkeypatch):
    """Gateway diagnostics can be inspected without starting a server."""
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_SCENE", raising=False)
    monkeypatch.delenv("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", raising=False)

    server = ShotGridMcpServer(port=0, shotgrid_project_id=192, gateway_port=0)
    server._config = SimpleNamespace(gateway_port=9765)

    info = server.get_gateway_info()

    assert info["enabled"] is True
    assert info["port"] == 9765
    assert info["scene"] == "project-id:192"
    assert info["display_name"] == "FPT id:192"


def test_resolve_gateway_failover_from_env(monkeypatch):
    """Gateway failover supports explicit values and env overrides."""
    assert _resolve_gateway_failover(False) is False
    assert _resolve_gateway_failover(True) is True
    assert _resolve_gateway_failover(None, gateway_port=0) is False

    monkeypatch.setenv("DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER", "0")
    assert _resolve_gateway_failover(None) is False

    monkeypatch.setenv("DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER", "yes")
    assert _resolve_gateway_failover(None) is True


def test_cli_parser_accepts_gateway_options():
    """CLI exposes gateway join options for local and CI usage."""
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "http",
            "--gateway-port",
            "9765",
            "--registry-dir",
            "C:/tmp/dcc-mcp-registry",
            "--gateway-scene",
            "project:demo_project",
            "--gateway-display-name",
            "FPT Demo",
            "--disable-gateway-failover",
        ]
    )

    assert args.gateway_port == 9765
    assert args.registry_dir == "C:/tmp/dcc-mcp-registry"
    assert args.gateway_scene == "project:demo_project"
    assert args.gateway_display_name == "FPT Demo"
    assert args.disable_gateway_failover is True


def test_cli_defaults_to_local_gateway(monkeypatch):
    """Running dcc-mcp-fpt with no args starts with the local gateway port."""
    monkeypatch.delenv("DCC_MCP_GATEWAY_PORT", raising=False)

    args = build_arg_parser().parse_args([])

    assert args.mode == "http"
    assert DEFAULT_PORT == 0
    assert args.port is None
    assert args.gateway_port == 9765
    assert _normalize_gateway_port(args) == 9765


def test_cli_no_gateway_overrides_default(monkeypatch):
    """--no-gateway is the short local standalone escape hatch."""
    monkeypatch.delenv("DCC_MCP_GATEWAY_PORT", raising=False)

    args = build_arg_parser().parse_args(["--no-gateway"])

    assert args.gateway_port == 9765
    assert _normalize_gateway_port(args) == 0


def test_apply_skill_paths_merges_fpt_env(monkeypatch):
    """Repeatable --skill-path values are merged into DCC_MCP_FPT_SKILL_PATHS."""
    monkeypatch.setenv("DCC_MCP_FPT_SKILL_PATHS", "C:/studio/fpt-skills")

    _apply_skill_paths(["C:/show/fpt-skills", "C:/studio/fpt-skills"])

    assert "C:/studio/fpt-skills" in os.environ["DCC_MCP_FPT_SKILL_PATHS"]
    assert "C:/show/fpt-skills" in os.environ["DCC_MCP_FPT_SKILL_PATHS"]


def test_start_server_passes_gateway_options(monkeypatch):
    """start_server forwards gateway options into ShotGridMcpServer."""
    captured = {}

    class FakeServer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def start(self):
            return "handle"

    monkeypatch.setattr(server_module, "ShotGridMcpServer", FakeServer)

    handle = server_module.start_server(
        port=8765,
        gateway_port=9765,
        registry_dir="C:/tmp/dcc-mcp-registry",
        gateway_scene="project:demo_project",
        gateway_display_name="FPT Demo",
        enable_gateway_failover=False,
    )

    assert handle == "handle"
    assert captured["gateway_port"] == 9765
    assert captured["registry_dir"] == "C:/tmp/dcc-mcp-registry"
    assert captured["gateway_scene"] == "project:demo_project"
    assert captured["gateway_display_name"] == "FPT Demo"
    assert captured["enable_gateway_failover"] is False
