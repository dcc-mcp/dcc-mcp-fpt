"""Public doctor and verify CLI contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

from dcc_mcp_fpt import fpt_cli
from dcc_mcp_fpt.diagnostics import diagnose

ROOT = Path(__file__).parents[1]
FPT_VERSION = "0.2.25"


def test_doctor_reports_missing_fpt_binary_as_secret_safe_json(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "DCC_MCP_FPT_CLI_PATH": str(tmp_path / "missing-fpt"),
            "SHOTGRID_URL": "https://example.shotgrid.autodesk.com",
            "SHOTGRID_SCRIPT_NAME": "example-script",
            "SHOTGRID_SCRIPT_KEY": "must-never-be-printed",
        }
    )

    completed = subprocess.run(
        [sys.executable, "-m", "dcc_mcp_fpt", "doctor", "--json"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 10
    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == 1
    assert payload["operation"] == "doctor"
    assert payload["status"] == "failed"
    assert payload["outcome"] == "preflight_failed"
    assert payload["directly_usable"] is False
    assert payload["failure_stage"] == "fpt_binary"
    assert payload["requirements"]["fpt"]["provenance"] == "explicit_override"
    assert payload["requirements"]["fpt"]["checksum_verified"] is False
    assert payload["next_steps"][0]["command"] == [
        "dcc-mcp-fpt",
        "doctor",
        "--json",
    ]
    combined_output = completed.stdout + completed.stderr
    assert "must-never-be-printed" not in combined_output


def test_doctor_rejects_a_tampered_pinned_cache_without_executing_it(
    tmp_path: Path,
) -> None:
    archive, executable = _platform_asset()
    cache_root = tmp_path / "cache"
    binary = cache_root / "dcc-mcp-fpt" / "fpt" / FPT_VERSION / archive / executable
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"tampered executable")
    binary.with_name(binary.name + ".sha256").write_text("0" * 64, encoding="ascii")

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "LOCALAPPDATA": str(cache_root),
            "XDG_CACHE_HOME": str(cache_root),
            "SHOTGRID_URL": "https://example.shotgrid.autodesk.com",
            "SHOTGRID_SCRIPT_NAME": "example-script",
            "SHOTGRID_SCRIPT_KEY": "must-never-be-printed",
        }
    )
    env.pop("DCC_MCP_FPT_CLI_PATH", None)

    completed = subprocess.run(
        [sys.executable, "-m", "dcc_mcp_fpt", "doctor", "--json"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 10
    payload = json.loads(completed.stdout)
    assert payload["failure_stage"] == "fpt_checksum"
    assert payload["requirements"]["fpt"] == {
        "minimum_version": FPT_VERSION,
        "expected_version": FPT_VERSION,
        "provenance": "pinned_cache",
        "path_configured": False,
        "found": True,
        "checksum_verified": False,
    }
    assert "must-never-be-printed" not in completed.stdout + completed.stderr


def test_verify_reports_versions_configuration_and_connectivity_without_secrets(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", sys.executable)
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_FPT_PROFILE", "example-profile")
    monkeypatch.setenv("SHOTGRID_PERMISSION_LEVEL", "read")
    monkeypatch.setenv("SHOTGRID_SCRIPT_KEY", "must-never-be-printed")

    def run_fpt(command, **kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "fpt 0.2.25\n", "")
        return subprocess.CompletedProcess(command, 0, '{"success":true}\n', "")

    monkeypatch.setattr("dcc_mcp_fpt.diagnostics.subprocess.run", run_fpt)

    payload, exit_code = diagnose("verify")

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["directly_usable"] is True
    assert payload["requirements"]["core"]["compatible"] is True
    assert payload["requirements"]["fpt"]["detected_version"] == FPT_VERSION
    assert payload["requirements"]["fpt"]["compatible"] is True
    assert payload["configuration"] == {
        "endpoint_configured": True,
        "auth_mode": "fpt_profile",
        "credentials_configured": True,
        "profile_configured": True,
        "permission_level": "read",
        "project_configured": False,
    }
    assert payload["checks"]["connectivity"] == "passed"
    assert payload["next_steps"] == []
    assert {
        "schema_version",
        "status",
        "dcc_type",
        "adapter_version",
        "core_version",
        "steps",
        "next_steps",
        "receipt_path",
        "verify",
    } <= payload.keys()
    assert payload["dcc_type"] == "fpt"
    assert payload["receipt_path"] is None
    assert payload["verify"] == {
        "directly_usable": True,
        "failure_stage": None,
        "failure_reason": None,
    }
    assert "must-never-be-printed" not in json.dumps(payload)


def test_verify_maps_auth_failure_to_exit_40_without_returning_process_output(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", sys.executable)
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_FPT_PROFILE", "example-profile")
    monkeypatch.setenv("SHOTGRID_PERMISSION_LEVEL", "read")

    def run_fpt(command, **kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "fpt 0.2.25\n", "")
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "authentication rejected: must-never-be-printed",
        )

    monkeypatch.setattr("dcc_mcp_fpt.diagnostics.subprocess.run", run_fpt)

    payload, exit_code = diagnose("verify")

    assert exit_code == 40
    assert payload["status"] == "failed"
    assert payload["outcome"] == "verify_failed"
    assert payload["directly_usable"] is False
    assert payload["failure_stage"] == "connectivity"
    assert payload["failure_reason"] == "fpt_auth_test_failed"
    assert payload["checks"]["connectivity"] == "failed"
    assert payload["next_steps"][0]["id"] == "refresh_profile_credentials"
    assert "must-never-be-printed" not in json.dumps(payload)


def test_verify_safely_provisions_the_immutable_pinned_cache(tmp_path: Path, monkeypatch) -> None:
    archive, executable = _platform_asset()
    cache_root = tmp_path / "cache"
    payload = _archive_payload(archive, executable, b"verified executable")
    checksums = f"{hashlib.sha256(payload).hexdigest()}  {archive}\n".encode()
    monkeypatch.delenv("DCC_MCP_FPT_CLI_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(cache_root))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_FPT_PROFILE", "example-profile")
    monkeypatch.setenv("SHOTGRID_PERMISSION_LEVEL", "read")
    monkeypatch.setattr(
        fpt_cli,
        "_download",
        lambda url: checksums if url.endswith("checksums.txt") else payload,
    )

    def run_fpt(command, **kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "fpt 0.2.25\n", "")
        return subprocess.CompletedProcess(command, 0, '{"success":true}\n', "")

    monkeypatch.setattr("dcc_mcp_fpt.diagnostics.subprocess.run", run_fpt)

    result, exit_code = diagnose("verify")

    assert exit_code == 0
    assert result["requirements"]["fpt"]["checksum_verified"] is True
    installed = cache_root / "dcc-mcp-fpt" / "fpt" / FPT_VERSION / archive / executable
    assert installed.read_bytes() == b"verified executable"
    assert installed.with_name(installed.name + ".sha256").is_file()


def test_doctor_enforces_the_fpt_version_floor_before_connectivity(monkeypatch) -> None:
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", sys.executable)
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_FPT_PROFILE", "example-profile")
    calls = []

    def run_fpt(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "fpt 0.2.24\n", "")

    monkeypatch.setattr("dcc_mcp_fpt.diagnostics.subprocess.run", run_fpt)

    payload, exit_code = diagnose("doctor")

    assert exit_code == 10
    assert payload["failure_stage"] == "fpt_version"
    assert payload["failure_reason"] == "fpt_version_below_floor"
    assert payload["requirements"]["fpt"]["detected_version"] == "0.2.24"
    assert payload["requirements"]["fpt"]["compatible"] is False
    assert calls == [[sys.executable, "--version"]]


def test_doctor_reports_missing_credentials_only_as_presence_booleans(monkeypatch) -> None:
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", sys.executable)
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    for name in (
        "SHOTGRID_FPT_PROFILE",
        "SHOTGRID_SCRIPT_NAME",
        "SHOTGRID_SCRIPT_KEY",
        "SHOTGRID_USERNAME",
        "SHOTGRID_PASSWORD",
        "SHOTGRID_SESSION_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "dcc_mcp_fpt.diagnostics.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "fpt 0.2.25\n", ""),
    )

    payload, exit_code = diagnose("doctor")

    assert exit_code == 10
    assert payload["failure_stage"] == "configuration"
    assert payload["configuration"]["endpoint_configured"] is True
    assert payload["configuration"]["credentials_configured"] is False
    assert payload["configuration"]["profile_configured"] is False
    file_edit = payload["next_steps"][0]["file_edit"]
    assert file_edit["path"] == ".env"
    assert file_edit["action"] == "update"
    assert "SHOTGRID_URL=" in file_edit["content"]
    assert "SHOTGRID_FPT_PROFILE=" in file_edit["content"]


def test_verify_drops_stale_fpt_credentials_before_mapping_the_selected_mode(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", sys.executable)
    monkeypatch.setenv("SHOTGRID_URL", "https://example.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_AUTH_MODE", "script")
    monkeypatch.setenv("SHOTGRID_SCRIPT_NAME", "example-script")
    monkeypatch.setenv("SHOTGRID_SCRIPT_KEY", "selected-secret")
    monkeypatch.delenv("SHOTGRID_FPT_PROFILE", raising=False)
    monkeypatch.setenv("FPT_PROFILE", "stale-profile")
    monkeypatch.setenv("FPT_SESSION_TOKEN", "stale-secret")
    observed_environments = []

    def run_fpt(command, **kwargs):
        observed_environments.append(kwargs["env"])
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "fpt 0.2.25\n", "")
        return subprocess.CompletedProcess(command, 0, '{"success":true}\n', "")

    monkeypatch.setattr("dcc_mcp_fpt.diagnostics.subprocess.run", run_fpt)

    payload, exit_code = diagnose("verify")

    assert exit_code == 0
    assert payload["configuration"]["auth_mode"] == "script"
    for environment in observed_environments:
        assert "FPT_PROFILE" not in environment
        assert "FPT_SESSION_TOKEN" not in environment
        assert environment["FPT_SCRIPT_NAME"] == "example-script"
        assert environment["FPT_SCRIPT_KEY"] == "selected-secret"


def _platform_asset() -> tuple[str, str]:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-pc-windows-msvc.zip", "fpt.exe"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return f"fpt-v{FPT_VERSION}-aarch64-apple-darwin.tar.gz", "fpt"
    if sys.platform == "darwin" and machine in {"x86_64", "amd64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-apple-darwin.tar.gz", "fpt"
    if sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-unknown-linux-gnu.tar.gz", "fpt"
    raise AssertionError(f"Unsupported CI platform: {sys.platform}/{machine}")


def _archive_payload(archive: str, executable: str, contents: bytes) -> bytes:
    package = BytesIO()
    if archive.endswith(".zip"):
        with zipfile.ZipFile(package, "w") as output:
            output.writestr(executable, contents)
        return package.getvalue()
    with tarfile.open(fileobj=package, mode="w:gz") as output:
        member = tarfile.TarInfo(executable)
        member.size = len(contents)
        output.addfile(member, BytesIO(contents))
    return package.getvalue()
