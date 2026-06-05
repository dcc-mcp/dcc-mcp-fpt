"""Runtime tests for ShotGrid CRUD skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
CRUD = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-crud" / "scripts"


def _load_script(name: str):
    path = CRUD / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_create_entity_uses_server():
    """create_entity calls client.create with data."""
    module = _load_script("create_entity")
    client = MagicMock()
    client.create.return_value = {"id": 99, "type": "Shot", "code": "SH_NEW"}
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Shot", data={"code": "SH_NEW"})
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.create.assert_called_once()


def test_update_entity_uses_server():
    """update_entity calls client.update with data."""
    module = _load_script("update_entity")
    client = MagicMock()
    client.update.return_value = {"id": 1, "type": "Shot", "code": "SH_MOD"}
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Shot", entity_id=1, data={"code": "SH_MOD"})
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.update.assert_called_once()


def test_delete_entity_uses_server():
    """delete_entity calls client.delete with entity_id."""
    module = _load_script("delete_entity")
    client = MagicMock()
    client.delete.return_value = True
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Shot", entity_id=1)
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.delete.assert_called_once()


def test_find_one_entity_uses_server():
    """find_one_entity calls client.find_one with filters."""
    module = _load_script("find_one_entity")
    client = MagicMock()
    client.find_one.return_value = {"id": 1, "type": "Shot", "code": "SH001"}
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(entity_type="Shot", filters=[["code", "is", "SH001"]])
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.find_one.assert_called_once()
