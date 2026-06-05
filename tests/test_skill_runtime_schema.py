"""Runtime tests for ShotGrid schema skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-schema" / "scripts"


def _load_script(name: str):
    path = SCHEMA / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"schema_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_schema_uses_server():
    """get_schema returns schema data from client."""
    module = _load_script("get_schema")
    client = MagicMock()
    client.get_schema.return_value = {"Shot": {"id": {"data_type": {"value": "number"}}}}
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.get_schema.assert_called_once()


def test_get_field_schema_uses_server():
    """get_field_schema returns field schema for a specific entity type."""
    module = _load_script("get_field_schema")
    client = MagicMock()
    client.get_schema.return_value = {"id": {"data_type": {"value": "number"}}}
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Shot", field_name="code")
    finally:
        clear_current_server(server)

    assert result["success"] is True


def test_list_entity_types_uses_server():
    """list_entity_types (schema variant) returns entity types from schema."""
    module = _load_script("list_entity_types")
    client = MagicMock()
    client.get_entity_types.return_value = ["Shot", "Asset", "Task"]
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main()
    finally:
        clear_current_server(server)

    assert result["success"] is True
