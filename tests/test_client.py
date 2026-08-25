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


def test_user_password_auth_uses_user_credentials_only(fpt_runner):
    client = ShotGridClient(
        "https://example.shotgrid.autodesk.com",
        auth_mode="user_password",
        username="artist@example.com",
        password="secret",
        auth_token="123456",
        cli_path="fpt",
        runner=fpt_runner,
    )

    client.connect()

    assert fpt_runner.environment["FPT_AUTH_MODE"] == "user_password"
    assert fpt_runner.environment["FPT_USERNAME"] == "artist@example.com"
    assert fpt_runner.environment["FPT_PASSWORD"] == "secret"
    assert fpt_runner.environment["FPT_AUTH_TOKEN"] == "123456"
    assert "FPT_SCRIPT_KEY" not in fpt_runner.environment


def test_fpt_profile_auth_uses_only_profile_reference(monkeypatch, fpt_runner):
    monkeypatch.setenv("FPT_PASSWORD", "inherited-secret")
    client = ShotGridClient(
        "https://example.shotgrid.autodesk.com",
        auth_mode="fpt_profile",
        fpt_profile="example-user",
        cli_path="fpt",
        runner=fpt_runner,
    )

    client.connect()

    assert fpt_runner.environment["FPT_PROFILE"] == "example-user"
    assert fpt_runner.environment["FPT_SITE"] == "https://example.shotgrid.autodesk.com"
    assert "FPT_PASSWORD" not in fpt_runner.environment


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


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "expected_code"),
    [
        (1, '{"error":"token=secret https://private.example/api C:/private/file"}', "", "FPT_COMMAND_FAILED"),
        (1, "", "token=secret https://private.example/api C:/private/file", "FPT_COMMAND_FAILED"),
        (0, '{"ok":true}', "token=secret https://private.example/api C:/private/file", "FPT_COMMAND_FAILED"),
        (0, '{"error":"token=secret https://private.example/api C:/private/file"}', "", "FPT_COMMAND_FAILED"),
        (0, '{"errors":["token=secret"]}', "", "FPT_COMMAND_FAILED"),
        (0, '{"ok":false,"message":"token=secret"}', "", "FPT_COMMAND_FAILED"),
        (0, '{"status":"failed","message":"token=secret"}', "", "FPT_COMMAND_FAILED"),
        (0, '{"success":false,"message":"token=secret"}', "", "FPT_COMMAND_FAILED"),
        (0, "not-json token=secret https://private.example/api C:/private/file", "", "FPT_INVALID_RESPONSE"),
        (0, '["token=secret"]', "", "FPT_INVALID_RESPONSE"),
    ],
)
def test_cli_failures_are_stable_and_do_not_echo_process_output(returncode, stdout, stderr, expected_code):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    client = ShotGridClient("https://test.shotgrid.autodesk.com", "script", "key", cli_path="fpt", runner=runner)

    with pytest.raises(ShotGridQueryError) as error:
        client.connect()

    assert str(error.value) == expected_code
    assert "secret" not in str(error.value)
    assert "private.example" not in str(error.value)
    assert "C:/private" not in str(error.value)


def test_missing_cli_is_reported():
    def runner(*args, **kwargs):
        raise FileNotFoundError()

    client = ShotGridClient(
        "https://test.shotgrid.autodesk.com", "script", "key", cli_path="missing-fpt", runner=runner
    )

    with pytest.raises(ShotGridConnectionError, match="^FPT_CLI_UNAVAILABLE$"):
        client.connect()


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (OSError("C:/private/fpt.exe token=secret"), "FPT_CLI_UNAVAILABLE"),
        (subprocess.TimeoutExpired(["C:/private/fpt.exe"], 30, stderr="token=secret"), "FPT_COMMAND_TIMEOUT"),
    ],
)
def test_process_exceptions_do_not_expose_paths_or_credentials(failure, expected_code):
    def runner(*args, **kwargs):
        raise failure

    client = ShotGridClient("https://test.shotgrid.autodesk.com", "script", "key", cli_path="fpt", runner=runner)

    with pytest.raises(ShotGridConnectionError) as error:
        client.connect()

    assert str(error.value) == expected_code
    assert "private" not in str(error.value)
    assert "secret" not in str(error.value)


def test_bootstrap_failure_does_not_echo_resolver_details(monkeypatch):
    def fail_resolution():
        raise RuntimeError("C:/private/cache token=secret https://private.example")

    monkeypatch.setattr("dcc_mcp_fpt.client.resolve_fpt_cli", fail_resolution)
    client = ShotGridClient("https://test.shotgrid.autodesk.com", "script", "key")

    with pytest.raises(ShotGridConnectionError, match="^FPT_CLI_UNAVAILABLE$") as error:
        client.connect()

    assert "private" not in str(error.value)
    assert "secret" not in str(error.value)
