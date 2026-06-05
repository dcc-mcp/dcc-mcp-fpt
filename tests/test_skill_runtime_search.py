"""Runtime tests for ShotGrid search skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-search" / "scripts"


def _load_script(name: str):
    path = SEARCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"search_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_search_entities_uses_server():
    """search_entities calls client.find with text search filters."""
    module = _load_script("search_entities")
    client = MagicMock()
    client.find.return_value = [{"id": 1, "type": "Shot", "code": "SH001"}]
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(
            entity_type="Shot",
            search_text="SH001",
            fields=["id", "code"],
        )
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.find.assert_called_once()


def test_search_by_name_uses_server():
    """search_by_name calls client.find with name filter."""
    module = _load_script("search_by_name")
    client = MagicMock()
    client.find.return_value = [{"id": 1, "type": "Asset", "code": "Tree"}]
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Asset", name="Tree")
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.find.assert_called_once()
