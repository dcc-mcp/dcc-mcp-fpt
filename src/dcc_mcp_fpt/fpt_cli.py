"""Pinned local ``fpt`` CLI bootstrap."""

from __future__ import annotations

import hashlib
import os
import platform
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Tuple

FPT_VERSION = "0.2.25"
_RELEASE_URL = "https://github.com/loonghao/fpt-cli/releases/download/v{version}"


def resolve_fpt_cli() -> str:
    """Return an explicit override or the verified pinned local binary."""
    override = os.environ.get("DCC_MCP_FPT_CLI_PATH")
    if override:
        return override

    archive, executable = _platform_asset()
    destination = _cache_dir() / FPT_VERSION / archive / executable
    if destination.is_file():
        return str(destination)
    _install(archive, executable, destination)
    return str(destination)


def _platform_asset() -> Tuple[str, str]:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-pc-windows-msvc.zip", "fpt.exe"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return f"fpt-v{FPT_VERSION}-aarch64-apple-darwin.tar.gz", "fpt"
    if sys.platform == "darwin" and machine in {"x86_64", "amd64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-apple-darwin.tar.gz", "fpt"
    if sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
        return f"fpt-v{FPT_VERSION}-x86_64-unknown-linux-gnu.tar.gz", "fpt"
    raise RuntimeError(f"No bundled fpt release for {sys.platform}/{machine}; set DCC_MCP_FPT_CLI_PATH.")


def _cache_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") if sys.platform == "win32" else os.environ.get("XDG_CACHE_HOME")
    return Path(root) / "dcc-mcp-fpt" / "fpt" if root else Path.home() / ".cache" / "dcc-mcp-fpt" / "fpt"


def _install(archive: str, executable: str, destination: Path) -> None:
    base_url = _RELEASE_URL.format(version=FPT_VERSION)
    payload = _download(f"{base_url}/{archive}")
    expected = _checksum(_download(f"{base_url}/fpt-checksums.txt").decode("utf-8"), archive)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError(f"Checksum verification failed for {archive}.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(destination.parent), delete=False) as output:
        temporary = Path(output.name)
        output.write(_executable_bytes(archive, executable, payload))
    temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(str(temporary), str(destination))


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _checksum(contents: str, archive: str) -> str:
    for line in contents.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == archive:
            return parts[0]
    raise RuntimeError(f"Release checksum for {archive} was not found.")


def _executable_bytes(archive: str, executable: str, payload: bytes) -> bytes:
    package = BytesIO(payload)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(package) as source:
            return source.read(executable)
    with tarfile.open(fileobj=package, mode="r:gz") as source:
        extracted = source.extractfile(executable)
        if extracted is None:
            raise RuntimeError(f"Release archive did not contain {executable}.")
        return extracted.read()
