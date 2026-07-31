"""Tests for the fpt CLI-backed ShotGrid client."""

from __future__ import annotations

import json
import subprocess

import pytest

from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.exceptions import ShotGridConnectionError, ShotGridQueryError


def _input(call):
    args = call
    return json.loads(args[args.index("--input") + 1])


def test_connect_uses_fpt_auth_and_secret_environment(shotgrid_client, fpt_runner):
    shotgrid_client.connect()

    assert fpt_runner.calls == [["fpt", "auth", "test", "--output", "json"]]
    assert fpt_runner.environment["FPT_SCRIPT_KEY"] == "test_key"
    assert "test_key" not in fpt_runner.calls[0]
    assert shotgrid_client.get_connection_info().authenticated is True


def test_find_translates_filters_and_rest_entities(shotgrid_client, fpt_runner):
    fpt_runner._result = lambda payload: subprocess.CompletedProcess(
        [], 0, json.dumps({"data": [{"type": "Shot", "id": 1, "attributes": {"code": "SH001"}}]}), ""
    )

    results = shotgrid_client.find("Shot", [["code", "is", "SH001"]], fields=["code"], limit=10)

    assert results == [{"code": "SH001", "id": 1, "type": "Shot"}]
    payload = _input(fpt_runner.calls[-1])
    assert payload["search"]["filters"] == [["code", "is", "SH001"]]
    assert payload["page"] == {"size": 10, "number": 1}


def test_delete_requires_fpt_confirmation(shotgrid_client, fpt_runner):
    assert shotgrid_client.delete("Project", 1) is True

    assert fpt_runner.calls[-1][:5] == ["fpt", "entity", "delete", "Project", "1"]
    assert "--yes" in fpt_runner.calls[-1]


def test_cli_errors_are_adapter_errors():
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess([], 1, '{"error":"denied"}', "")

    client = ShotGridClient("https://test.shotgrid.autodesk.com", "script", "key", cli_path="fpt", runner=runner)

    with pytest.raises(ShotGridQueryError, match="denied"):
        client.connect()


def test_missing_cli_is_reported():
    def runner(*args, **kwargs):
        raise FileNotFoundError()

    client = ShotGridClient(
        "https://test.shotgrid.autodesk.com", "script", "key", cli_path="missing-fpt", runner=runner
    )

    with pytest.raises(ShotGridConnectionError, match="DCC_MCP_FPT_CLI_PATH"):
        client.connect()
