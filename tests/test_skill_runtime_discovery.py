"""Runtime tests for ShotGrid discovery skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src" / "dcc_mcp_fpt" / "skills"


def _load_script(skill: str, name: str):
    path = SKILLS / skill / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{skill}_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_connection_returns_authenticated():
    """check_connection returns connection diagnostics when server is available."""
    module = _load_script("shotgrid-discovery", "check_connection")
    server = MagicMock()
    server.get_connection_info.return_value = {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "test",
        "authenticated": True,
    }

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
    assert result["message"] is not None


def test_check_connection_no_server_error():
    """check_connection returns error when no server is available."""
    module = _load_script("shotgrid-discovery", "check_connection")
    clear_current_server()

    result = module.main()

    assert result["success"] is False
    assert result["error"] == "NO_SERVER"


def test_get_server_info_returns_info():
    """get_server_info returns server metadata when connected."""
    module = _load_script("shotgrid-discovery", "get_server_info")
    server = MagicMock()
    server.get_connection_info.return_value = {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "test",
        "authenticated": True,
        "server_version": "8.0.0",
        "gateway": {},
        "request_context": {},
    }

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
    ctx = result.get("context", {})
    assert ctx.get("server_version") == "8.0.0"


def test_list_entity_types_returns_list():
    """list_entity_types returns entity types when schema is available."""
    module = _load_script("shotgrid-discovery", "list_entity_types")
    client = MagicMock()
    client.get_entity_types.return_value = ["Shot", "Asset", "Task"]
    server = MagicMock()
    # list_entity_types uses get_request_client(server, params) which calls
    # server.client_for_request() first, or falls back to server.client
    server.client_for_request.return_value = client
    server.client = client

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
    ctx = result.get("context", {})
    assert ctx.get("count") == 3
    assert ctx.get("entity_types") == ["Shot", "Asset", "Task"]
