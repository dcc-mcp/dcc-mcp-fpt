"""Tests for the pinned local fpt bootstrap."""

from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO

from dcc_mcp_fpt import fpt_cli


def test_explicit_cli_path_skips_download(monkeypatch):
    monkeypatch.setenv("DCC_MCP_FPT_CLI_PATH", "C:/tools/fpt.exe")
    assert fpt_cli.resolve_fpt_cli() == "C:/tools/fpt.exe"


def test_install_verifies_checksum_and_extracts_executable(tmp_path, monkeypatch):
    archive = "fpt-v0.2.25-x86_64-pc-windows-msvc.zip"
    package = BytesIO()
    with zipfile.ZipFile(package, "w") as source:
        source.writestr("fpt.exe", b"fpt")
    payload = package.getvalue()
    checksum = f"{hashlib.sha256(payload).hexdigest()}  {archive}\n".encode()
    monkeypatch.setattr(fpt_cli, "_download", lambda url: checksum if url.endswith("checksums.txt") else payload)

    destination = tmp_path / "fpt.exe"
    fpt_cli._install(archive, "fpt.exe", destination)

    assert destination.read_bytes() == b"fpt"
