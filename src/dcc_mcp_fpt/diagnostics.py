"""Secret-safe standalone doctor and verify diagnostics."""

from __future__ import annotations

import json
import os
import re
import subprocess
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, Optional, Tuple

from dcc_mcp_fpt import __version__
from dcc_mcp_fpt.fpt_cli import FPT_VERSION, inspect_fpt_cli, resolve_fpt_cli
from dcc_mcp_fpt.fpt_response import is_failure_response

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_PREFLIGHT = 10
EXIT_VERIFY = 40
MIN_CORE_VERSION = "0.19.45"

_CREDENTIAL_ENV_NAMES = {
    "FPT_SITE",
    "FPT_AUTH_MODE",
    "FPT_SCRIPT_NAME",
    "FPT_SCRIPT_KEY",
    "FPT_USERNAME",
    "FPT_PASSWORD",
    "FPT_AUTH_TOKEN",
    "FPT_SESSION_TOKEN",
    "FPT_API_VERSION",
    "FPT_PROFILE",
    "SG_SITE",
    "SG_AUTH_MODE",
    "SG_SCRIPT_NAME",
    "SG_SCRIPT_KEY",
    "SG_USERNAME",
    "SG_PASSWORD",
    "SG_AUTH_TOKEN",
    "SG_SESSION_TOKEN",
    "SG_API_VERSION",
    "SG_PROFILE",
    "SHOTGRID_URL",
    "SHOTGRID_AUTH_MODE",
    "SHOTGRID_SCRIPT_NAME",
    "SHOTGRID_SCRIPT_KEY",
    "SHOTGRID_USERNAME",
    "SHOTGRID_PASSWORD",
    "SHOTGRID_AUTH_TOKEN",
    "SHOTGRID_SESSION_TOKEN",
    "SHOTGRID_FPT_PROFILE",
}


def diagnose(operation: str) -> Tuple[Dict[str, Any], int]:
    """Inspect prerequisites and prove connectivity without exposing secrets."""
    payload = _base_payload(operation)
    local_fpt = inspect_fpt_cli()
    if operation == "verify" and local_fpt["provenance"] == "pinned_cache" and not local_fpt["checksum_verified"]:
        try:
            resolve_fpt_cli()
        except (OSError, RuntimeError):
            pass
        local_fpt = inspect_fpt_cli()
    fpt_requirement = {
        "minimum_version": FPT_VERSION,
        "expected_version": FPT_VERSION,
        "provenance": local_fpt["provenance"],
        "path_configured": local_fpt["path_configured"],
        "found": local_fpt["found"],
        "checksum_verified": local_fpt["checksum_verified"],
    }
    core_version = _package_version("dcc-mcp-core")
    payload["core_version"] = core_version
    core_compatible = core_version != "not-installed" and _version_at_least(core_version, MIN_CORE_VERSION)
    payload["requirements"] = {
        "core": {
            "minimum_version": MIN_CORE_VERSION,
            "detected_version": core_version,
            "compatible": core_compatible,
        },
        "fpt": fpt_requirement,
    }
    payload["configuration"] = _configuration_summary()

    if local_fpt.get("unsupported_platform"):
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "platform",
            "unsupported_fpt_platform",
            _binary_next_step(),
        )
    if not local_fpt["found"]:
        pinned_cache = local_fpt["provenance"] == "pinned_cache"
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "fpt_binary",
            "pinned_fpt_cache_missing" if pinned_cache else "configured_fpt_binary_not_found",
            _cache_next_step() if pinned_cache else _binary_next_step(),
        )
    if local_fpt["provenance"] == "pinned_cache" and not local_fpt["checksum_verified"]:
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "fpt_checksum",
            "cached_fpt_checksum_mismatch",
            _cache_next_step(),
        )
    if not core_compatible:
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "core_version",
            "dcc_mcp_core_version_below_floor",
            {
                "id": "upgrade_core",
                "description": "Install a compatible dcc-mcp-core release.",
                "command": [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    f"dcc-mcp-core>={MIN_CORE_VERSION},<1",
                ],
                "why": "The adapter requires the shared Core runtime contract.",
            },
        )

    detected_fpt, version_error = _detect_fpt_version(local_fpt["path"])
    fpt_requirement["detected_version"] = detected_fpt
    fpt_requirement["compatible"] = bool(detected_fpt and _version_at_least(detected_fpt, FPT_VERSION))
    if version_error or not fpt_requirement["compatible"]:
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "fpt_version",
            version_error or "fpt_version_below_floor",
            _binary_next_step(),
        )

    configuration = payload["configuration"]
    if not configuration["endpoint_configured"] or not configuration["credentials_configured"]:
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "configuration",
            "shotgrid_configuration_incomplete",
            _configuration_next_step(),
        )
    if configuration["permission_level"] not in {"read", "write", "admin"}:
        return _failure(
            payload,
            EXIT_PREFLIGHT,
            "preflight_failed",
            "permission",
            "invalid_permission_level",
            _permission_next_step(),
        )

    connected = _check_connectivity(local_fpt["path"])
    payload["checks"] = {
        "binary": "passed",
        "checksum": ("passed" if local_fpt["checksum_verified"] else "operator_managed"),
        "core_version": "passed",
        "fpt_version": "passed",
        "configuration": "passed",
        "permission": "passed",
        "connectivity": "passed" if connected else "failed",
    }
    if not connected:
        return _failure(
            payload,
            EXIT_VERIFY,
            "verify_failed",
            "connectivity",
            "fpt_auth_test_failed",
            _connectivity_next_step(configuration["auth_mode"]),
        )

    payload.update(
        {
            "status": "ok",
            "outcome": "ok",
            "directly_usable": True,
            "failure_stage": None,
            "failure_reason": None,
            "next_steps": [],
            "steps": [{"id": check_id, "status": check_status} for check_id, check_status in payload["checks"].items()],
            "verify": {
                "directly_usable": True,
                "failure_stage": None,
                "failure_reason": None,
            },
        }
    )
    return payload, EXIT_OK


def _base_payload(operation: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "dcc_type": "fpt",
        "adapter_version": __version__,
        "core_version": "not-installed",
        "steps": [],
        "next_steps": [],
        "receipt_path": None,
        "verify": {
            "directly_usable": False,
            "failure_stage": None,
            "failure_reason": None,
        },
        "operation": operation,
        "dcc": "fpt",
        "standalone": True,
        "checks": {},
    }


def _failure(
    payload: Dict[str, Any],
    exit_code: int,
    status: str,
    stage: str,
    reason: str,
    next_step: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    payload.update(
        {
            "status": "failed",
            "outcome": status,
            "directly_usable": False,
            "failure_stage": stage,
            "failure_reason": reason,
            "next_steps": [next_step],
            "steps": [*payload.get("steps", []), {"id": stage, "status": "failed"}],
            "verify": {
                "directly_usable": False,
                "failure_stage": stage,
                "failure_reason": reason,
            },
        }
    )
    return payload, exit_code


def _configuration_summary() -> Dict[str, Any]:
    profile = bool(os.environ.get("SHOTGRID_FPT_PROFILE"))
    auth_mode = "fpt_profile" if profile else os.environ.get("SHOTGRID_AUTH_MODE", "script")
    auth_mode = auth_mode.replace("-", "_").lower()
    required = {
        "script": ("SHOTGRID_SCRIPT_NAME", "SHOTGRID_SCRIPT_KEY"),
        "user_password": ("SHOTGRID_USERNAME", "SHOTGRID_PASSWORD"),
        "session_token": ("SHOTGRID_SESSION_TOKEN",),
        "fpt_profile": ("SHOTGRID_FPT_PROFILE",),
    }.get(auth_mode, ())
    return {
        "endpoint_configured": bool(os.environ.get("SHOTGRID_URL")),
        "auth_mode": auth_mode,
        "credentials_configured": bool(required) and all(os.environ.get(name) for name in required),
        "profile_configured": profile,
        "permission_level": os.environ.get("SHOTGRID_PERMISSION_LEVEL", "read").lower(),
        "project_configured": bool(os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_PROJECT_ID")),
    }


def _detect_fpt_version(executable: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=_fpt_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "fpt_version_command_failed"
    if completed.returncode or completed.stderr.strip():
        return None, "fpt_version_command_failed"
    match = re.search(r"\d+\.\d+\.\d+", completed.stdout)
    return (match.group(0), None) if match else (None, "fpt_version_unparseable")


def _check_connectivity(executable: str) -> bool:
    try:
        completed = subprocess.run(
            [executable, "auth", "test", "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_fpt_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if completed.returncode or completed.stderr.strip():
        return False
    try:
        response = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(response, dict) and response.get("success") is True and not is_failure_response(response)


def _fpt_environment() -> Dict[str, str]:
    environment = os.environ.copy()
    for name in _CREDENTIAL_ENV_NAMES:
        environment.pop(name, None)
    environment["FPT_SITE"] = os.environ.get("SHOTGRID_URL", "")
    profile = os.environ.get("SHOTGRID_FPT_PROFILE")
    auth_mode = "fpt_profile" if profile else os.environ.get("SHOTGRID_AUTH_MODE", "script")
    auth_mode = auth_mode.replace("-", "_").lower()
    environment["FPT_AUTH_MODE"] = auth_mode
    if auth_mode == "fpt_profile":
        environment["FPT_PROFILE"] = profile or ""
    elif auth_mode == "script":
        environment["FPT_SCRIPT_NAME"] = os.environ.get("SHOTGRID_SCRIPT_NAME", "")
        environment["FPT_SCRIPT_KEY"] = os.environ.get("SHOTGRID_SCRIPT_KEY", "")
    elif auth_mode == "user_password":
        environment["FPT_USERNAME"] = os.environ.get("SHOTGRID_USERNAME", "")
        environment["FPT_PASSWORD"] = os.environ.get("SHOTGRID_PASSWORD", "")
        environment["FPT_AUTH_TOKEN"] = os.environ.get("SHOTGRID_AUTH_TOKEN", "")
    elif auth_mode == "session_token":
        environment["FPT_SESSION_TOKEN"] = os.environ.get("SHOTGRID_SESSION_TOKEN", "")
    return environment


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not-installed"


def _version_at_least(detected: str, required: str) -> bool:
    return _version_tuple(detected) >= _version_tuple(required)


def _version_tuple(value: str) -> Tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)+", value)
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def _binary_next_step() -> Dict[str, Any]:
    return {
        "id": "configure_fpt_binary",
        "description": "Configure a supported fpt executable and rerun doctor.",
        "command": ["dcc-mcp-fpt", "doctor", "--json"],
        "why": (
            "Unset an invalid DCC_MCP_FPT_CLI_PATH to use the immutable pinned cache, "
            "or configure an operator-managed executable."
        ),
    }


def _cache_next_step() -> Dict[str, Any]:
    return {
        "id": "provision_verified_cache",
        "description": "Provision or repair the immutable pinned cache.",
        "command": ["dcc-mcp-fpt", "verify", "--json"],
        "why": ("Verify downloads only the fixed release asset and accepts it after SHA-256 validation."),
    }


def _configuration_next_step() -> Dict[str, Any]:
    return {
        "id": "configure_shotgrid",
        "description": "Configure the endpoint and one supported credential mode.",
        "file_edit": {
            "path": ".env",
            "action": "update",
            "content": ("SHOTGRID_URL=https://example.shotgrid.autodesk.com\nSHOTGRID_FPT_PROFILE=<profile-name>\n"),
        },
        "why": "Diagnostics report only credential presence; secret values remain operator-owned.",
    }


def _permission_next_step() -> Dict[str, Any]:
    return {
        "id": "set_bounded_permission",
        "description": "Select read, write, or admin as the adapter policy ceiling.",
        "file_edit": {
            "path": ".env",
            "action": "update",
            "content": "SHOTGRID_PERMISSION_LEVEL=read\n",
        },
        "why": "An invalid permission ceiling cannot be enforced safely.",
    }


def _connectivity_next_step(auth_mode: str) -> Dict[str, Any]:
    if auth_mode == "fpt_profile":
        return {
            "id": "refresh_profile_credentials",
            "description": "Refresh the configured profile in the OS credential store.",
            "command": ["fpt", "auth", "login", "--profile", "<configured-profile>"],
            "why": "The profile or endpoint did not pass the bounded fpt auth test.",
        }
    return {
        "id": "verify_credentials",
        "description": "Verify the operator-owned credentials and endpoint, then retry.",
        "command": ["dcc-mcp-fpt", "verify", "--json"],
        "why": "The bounded fpt auth test could not authenticate or reach the endpoint.",
    }
