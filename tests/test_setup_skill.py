"""Tests for the bundled ShotGrid setup skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPTS = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-setup" / "scripts"


def _load_script(name: str):
    path = SETUP_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_agent_config_uses_gateway_port_param(monkeypatch):
    """Generated env and endpoint snippets honor the requested gateway port."""
    monkeypatch.delenv("DCC_MCP_GATEWAY_PORT", raising=False)
    module = _load_script("generate_agent_config")

    result = module.main(project="demo_project", gateway_port=9777)

    assert result["success"] is True
    context = result["context"]
    assert context["start_command"] == "uvx dcc-mcp-fpt"
    assert context["environment"]["DCC_MCP_GATEWAY_PORT"] == "9777"
    assert context["endpoints"]["gateway_mcp_url"] == "http://127.0.0.1:9777/mcp"


def test_validate_runtime_config_reports_missing_credentials(monkeypatch):
    """Runtime validation reports missing credentials when requested."""
    for key in ("SHOTGRID_URL", "SHOTGRID_SCRIPT_NAME", "SHOTGRID_SCRIPT_KEY"):
        monkeypatch.delenv(key, raising=False)
    module = _load_script("validate_runtime_config")

    result = module.main(require_credentials=True)

    assert result["success"] is True
    context = result["context"]
    assert context["ready"] is False
    assert context["missing"] == ["SHOTGRID_URL", "SHOTGRID_SCRIPT_NAME", "SHOTGRID_SCRIPT_KEY"]
