"""Runtime tests for ShotGrid note skill scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-note" / "scripts"


def _load_script(name: str):
    path = NOTES / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"note_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_create_note_uses_server():
    """create_note calls client.create with note data."""
    module = _load_script("create_note")
    client = MagicMock()
    client.create.return_value = {"id": 1, "type": "Note", "subject": "Test"}
    server = MagicMock()
    server.client_for_request.return_value = client

    set_current_server(server)
    try:
        result = module.main(
            subject="Test Note",
            content="Note content",
            link_entity_type="Shot",
            link_entity_id=1,
        )
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.create.assert_called_once()


def test_find_notes_uses_server():
    """find_notes calls client.find for notes with required params."""
    module = _load_script("find_notes")
    client = MagicMock()
    client.find.return_value = [{"id": 1, "type": "Note", "subject": "Test"}]
    server = MagicMock()
    server.client_for_request.return_value = client

    set_current_server(server)
    try:
        result = module.main(link_entity_type="Shot", link_entity_id=1)
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.find.assert_called_once()


def test_update_note_uses_server():
    """update_note calls client.update with note data."""
    module = _load_script("update_note")
    client = MagicMock()
    client.update.return_value = {"id": 1, "type": "Note", "subject": "Updated"}
    server = MagicMock()
    server.client_for_request.return_value = client

    set_current_server(server)
    try:
        result = module.main(note_id=1, subject="Updated")
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.update.assert_called_once()
