"""Runtime tests for ShotGrid batch skill script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "src" / "dcc_mcp_fpt" / "skills" / "shotgrid-batch" / "scripts"


def _load_script(name: str):
    path = BATCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"batch_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_batch_operations_uses_server():
    """batch_operations calls client.batch with request list."""
    module = _load_script("batch_operations")
    client = MagicMock()
    client.batch.return_value = [
        {"id": 1, "type": "Shot"},
        {"id": 2, "type": "Shot"},
    ]
    server = SimpleNamespace(client=client)

    set_current_server(server)
    try:
        result = module.main(
            requests=[
                {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH001"}},
                {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH002"}},
            ]
        )
    finally:
        clear_current_server(server)

    assert result["success"] is True
    client.batch.assert_called_once()
