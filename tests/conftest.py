"""Shared test fixtures for dcc-mcp-fpt."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List

import pytest


class FptRunner:
    """Small in-memory stand-in for the external fpt executable."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []
        self.environment: Dict[str, str] = {}

    def __call__(self, args: List[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        self.environment = kwargs["env"]
        command = args[1:4]
        if command == ["entity", "find-one", "Project"]:
            return self._result(
                {
                    "data": {
                        "type": "Project",
                        "id": 192,
                        "attributes": {"name": "demo_project", "tank_name": "demo_project"},
                    }
                }
            )
        if command[:2] == ["entity", "find"]:
            return self._result({"data": []})
        if command[:2] in (["entity", "create"], ["entity", "update"]):
            return self._result({"data": {"type": "Shot", "id": 1, "attributes": {"code": "SH001"}}})
        return self._result({"ok": True})

    @staticmethod
    def _result(payload: Dict[str, Any]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, json.dumps(payload), "")


@pytest.fixture
def fpt_runner() -> FptRunner:
    return FptRunner()


@pytest.fixture
def shotgrid_client(fpt_runner: FptRunner):
    """Create a ShotGridClient with a mocked fpt process."""
    from dcc_mcp_fpt.client import ShotGridClient

    return ShotGridClient(
        url="https://test.shotgrid.autodesk.com",
        script_name="test_script",
        api_key="test_key",
        default_project="",
        cli_path="fpt",
        runner=fpt_runner,
    )


@pytest.fixture
def schema_cache():
    """Create a fresh schema cache."""
    from dcc_mcp_fpt.schema_cache import SchemaCache

    return SchemaCache(ttl=60)
