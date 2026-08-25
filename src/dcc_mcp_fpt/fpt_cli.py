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
from typing import Any, Dict, Tuple

FPT_VERSION = "0.2.25"
_RELEASE_URL = "https://github.com/dcc-mcp/fpt-cli/releases/download/v{version}"
_ASSET_SHA256 = {
    "fpt-v0.2.25-aarch64-apple-darwin.tar.gz": "159be8939aa6fbd83ca218db2a20bacbed695fc1186aa27710c2c361a57c69b8",
    "fpt-v0.2.25-x86_64-apple-darwin.tar.gz": "ba15521fb9027600771ef2bb68c26d66ee62157560ecfb7464ba924caedb4544",
    "fpt-v0.2.25-x86_64-pc-windows-msvc.zip": "cded86dc1bf754944b5c8bf7825004a1af37bda5feae149085f6085073606964",
    "fpt-v0.2.25-x86_64-unknown-linux-gnu.tar.gz": "fe5e197a3be1ce0e98c14665128a19d6b8f4fb7462a38483a2f10c7d3cc349f0",
}


def resolve_fpt_cli() -> str:
    """Return an explicit override or the verified pinned local binary."""
    override = os.environ.get("DCC_MCP_FPT_CLI_PATH")
    if override:
        return override

    archive, executable = _platform_asset()
    destination = _cache_dir() / FPT_VERSION / archive / executable
    if inspect_fpt_cli()["checksum_verified"]:
        return str(destination)
    _install(archive, executable, destination)
    return str(destination)


def inspect_fpt_cli() -> Dict[str, Any]:
    """Describe local binary provenance without downloading or executing it."""
    override = os.environ.get("DCC_MCP_FPT_CLI_PATH")
    if override:
        path = Path(override).expanduser()
        return {
            "path": str(path),
            "provenance": "explicit_override",
            "path_configured": True,
            "found": path.is_file(),
            "checksum_verified": False,
        }

    try:
        archive, executable = _platform_asset()
    except RuntimeError:
        return {
            "path": "",
            "provenance": "pinned_cache",
            "path_configured": False,
            "found": False,
            "checksum_verified": False,
            "unsupported_platform": True,
        }
    destination = _cache_dir() / FPT_VERSION / archive / executable
    recorded = _read_recorded_checksum(destination)
    verified = bool(recorded and destination.is_file() and _file_sha256(destination) == recorded)
    return {
        "path": str(destination),
        "provenance": "pinned_cache",
        "path_configured": False,
        "found": destination.is_file(),
        "checksum_verified": verified,
    }


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
    expected = _ASSET_SHA256.get(archive)
    if expected is None:
        raise RuntimeError("The requested fpt release asset is not package-trusted.")
    base_url = _RELEASE_URL.format(version=FPT_VERSION)
    payload = _download(f"{base_url}/{archive}")
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError(f"Checksum verification failed for {archive}.")

    executable_payload = _executable_bytes(archive, executable, payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _write_temporary(destination.parent, executable_payload)
    checksum_temporary = _write_temporary(
        destination.parent,
        hashlib.sha256(executable_payload).hexdigest().encode("ascii"),
    )
    try:
        temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(str(temporary), str(destination))
        os.replace(str(checksum_temporary), str(_checksum_path(destination)))
    finally:
        temporary.unlink(missing_ok=True)
        checksum_temporary.unlink(missing_ok=True)


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _executable_bytes(archive: str, executable: str, payload: bytes) -> bytes:
    package = BytesIO(payload)
    try:
        if archive.endswith(".zip"):
            with zipfile.ZipFile(package) as source:
                return source.read(executable)
        with tarfile.open(fileobj=package, mode="r:gz") as source:
            extracted = source.extractfile(executable)
            if extracted is None:
                raise RuntimeError(f"Release archive did not contain {executable}.")
            return extracted.read()
    except (KeyError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"Pinned fpt release archive was invalid or missing {executable}.") from exc


def _checksum_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".sha256")


def _read_recorded_checksum(destination: Path) -> str:
    try:
        value = _checksum_path(destination).read_text(encoding="ascii").strip().lower()
    except OSError:
        return ""
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        return ""
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _write_temporary(directory: Path, contents: bytes) -> Path:
    with tempfile.NamedTemporaryFile(dir=str(directory), delete=False) as output:
        temporary = Path(output.name)
        output.write(contents)
    return temporary
