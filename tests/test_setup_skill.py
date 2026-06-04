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


def test_generate_agent_config_includes_request_context(monkeypatch):
    """Generated setup documents request-scoped profile metadata."""
    monkeypatch.setenv("SHOTGRID_CREDENTIAL_PROFILE", "sg-read-zombie")
    module = _load_script("generate_agent_config")

    result = module.main(project="demo_project", target="context")

    assert result["success"] is True
    context = result["context"]["request_context"]
    meta = context["mcp_meta"]["_meta"]
    assert meta["credential_profile"] == "sg-read-zombie"
    assert meta["project_scope"] == "demo_project"
    assert "requester_id" in meta["agent_context"]
    assert context["profile_file_env"] == "DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE"


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


def test_validate_runtime_config_reports_profile_support(monkeypatch):
    """Runtime validation shows whether profile-based credentials are configured."""
    monkeypatch.setenv("DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE", "C:/secure/fpt-profiles.json")
    module = _load_script("validate_runtime_config")

    result = module.main(require_credentials=False)

    assert result["success"] is True
    context = result["context"]
    assert context["shotgrid"]["credential_profiles_configured"] is True
    assert context["request_context"]["meta_key"] == "_meta"
    assert context["request_context"]["identity_key"] == "_meta.agent_context"
    assert context["request_context"]["credential_profile_key"] == "_meta.credential_profile"
