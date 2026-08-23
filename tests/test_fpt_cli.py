"""Tests for the pinned local fpt bootstrap."""

from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO

import pytest

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
    assert destination.with_name("fpt.exe.sha256").read_text(encoding="ascii") == hashlib.sha256(b"fpt").hexdigest()


def test_resolve_reuses_only_a_digest_verified_pinned_cache(tmp_path, monkeypatch):
    archive = "fpt-v0.2.25-x86_64-pc-windows-msvc.zip"
    destination = tmp_path / fpt_cli.FPT_VERSION / archive / "fpt.exe"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"verified fpt")
    destination.with_name("fpt.exe.sha256").write_text(hashlib.sha256(b"verified fpt").hexdigest(), encoding="ascii")
    monkeypatch.delenv("DCC_MCP_FPT_CLI_PATH", raising=False)
    monkeypatch.setattr(fpt_cli, "_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(fpt_cli, "_platform_asset", lambda: (archive, "fpt.exe"))
    monkeypatch.setattr(
        fpt_cli,
        "_download",
        lambda _url: (_ for _ in ()).throw(AssertionError("verified cache must not download")),
    )

    assert fpt_cli.resolve_fpt_cli() == str(destination)


def test_checksum_mismatch_fails_closed_without_replacing_existing_cache(tmp_path, monkeypatch):
    archive = "fpt-v0.2.25-x86_64-pc-windows-msvc.zip"
    package = BytesIO()
    with zipfile.ZipFile(package, "w") as source:
        source.writestr("fpt.exe", b"untrusted replacement")
    payload = package.getvalue()
    incorrect_checksum = f"{'0' * 64}  {archive}\n".encode()
    monkeypatch.setattr(
        fpt_cli,
        "_download",
        lambda url: incorrect_checksum if url.endswith("checksums.txt") else payload,
    )
    destination = tmp_path / "fpt.exe"
    destination.write_bytes(b"previous verified binary")

    with pytest.raises(RuntimeError, match="Checksum verification failed"):
        fpt_cli._install(archive, "fpt.exe", destination)

    assert destination.read_bytes() == b"previous verified binary"
    assert not destination.with_name("fpt.exe.sha256").exists()
