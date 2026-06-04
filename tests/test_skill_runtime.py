"""Tests for in-process skill runtime integration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]


def _load_skill_script(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_entities_uses_registered_server_context():
    """CRUD skills resolve the active FPT server from runtime context."""
    module = _load_skill_script("src/dcc_mcp_fpt/skills/shotgrid-crud/scripts/find_entities.py")
    client = MagicMock()
    client.find.return_value = [{"type": "Shot", "id": 1, "code": "SH001"}]
    server = SimpleNamespace(client=client)
    set_current_server(server)

    try:
        result = module.main(entity_type="Shot", filters=[], fields=["id", "code"], limit=10)
    finally:
        clear_current_server(server)

    assert result["success"] is True
    assert result["context"]["count"] == 1
    assert result["context"]["items"][0]["code"] == "SH001"
    client.find.assert_called_once_with(
        entity_type="Shot",
        filters=[],
        fields=["id", "code"],
        order=None,
        limit=10,
        retired_only=False,
        page=1,
        project=None,
        project_id=None,
        project_scoped=True,
    )


def test_find_entities_no_server_error_uses_current_skill_error_signature():
    """The no-server path should return a skill error, not raise TypeError."""
    module = _load_skill_script("src/dcc_mcp_fpt/skills/shotgrid-crud/scripts/find_entities.py")
    clear_current_server()

    result = module.main(entity_type="Shot")

    assert result["success"] is False
    assert result["error"] == "NO_SERVER"


def test_find_entities_forwards_meta_to_request_client():
    """CRUD skills forward MCP metadata to request-scoped server clients."""
    module = _load_skill_script("src/dcc_mcp_fpt/skills/shotgrid-crud/scripts/find_entities.py")
    client = MagicMock()
    client.find.return_value = []
    server = MagicMock()
    server.client_for_request.return_value = client
    set_current_server(server)
    meta = {"credential_profile": "sg-read-zombie", "agent_context": {"actor_id": "artist-42"}}

    try:
        result = module.main(entity_type="Shot", _meta=meta)
    finally:
        clear_current_server(server)

    assert result["success"] is True
    server.client_for_request.assert_called_once_with({"_meta": meta})
