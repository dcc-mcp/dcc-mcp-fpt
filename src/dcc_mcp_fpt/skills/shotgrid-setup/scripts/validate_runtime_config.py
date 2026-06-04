"""Validate local dcc-mcp-fpt runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success

REQUIRED_CREDENTIALS = ("SHOTGRID_URL", "SHOTGRID_SCRIPT_NAME", "SHOTGRID_SCRIPT_KEY")


@skill_entry
def main(**params):
    """Inspect environment variables used by the FPT adapter."""
    try:
        require_credentials = bool(params.get("require_credentials", True))
        require_project = bool(params.get("require_project", False))

        missing: List[str] = []
        warnings: List[str] = []
        if require_credentials:
            missing.extend(name for name in REQUIRED_CREDENTIALS if not os.environ.get(name))

        project = os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
        project_id = os.environ.get("SHOTGRID_PROJECT_ID")
        if require_project and not project and not project_id:
            missing.append("SHOTGRID_PROJECT or SHOTGRID_PROJECT_ID")

        gateway_port = _env_int("DCC_MCP_GATEWAY_PORT", 9765)
        permission_level = os.environ.get("SHOTGRID_PERMISSION_LEVEL", "read")
        if permission_level not in {"read", "write", "admin"}:
            warnings.append("SHOTGRID_PERMISSION_LEVEL should be read, write, or admin")
        profiles_configured = bool(
            os.environ.get("DCC_MCP_FPT_CREDENTIAL_PROFILES")
            or os.environ.get("SHOTGRID_CREDENTIAL_PROFILES")
            or os.environ.get("DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE")
            or os.environ.get("SHOTGRID_CREDENTIAL_PROFILES_FILE")
        )

        skill_paths = _split_paths(os.environ.get("DCC_MCP_FPT_SKILL_PATHS", ""))
        global_skill_paths = _split_paths(os.environ.get("DCC_MCP_SKILL_PATHS", ""))
        missing_skill_paths = [path for path in [*skill_paths, *global_skill_paths] if not Path(path).exists()]
        if missing_skill_paths:
            warnings.append("Some configured skill paths do not exist")

        context: Dict[str, Any] = {
            "ready": not missing,
            "missing": missing,
            "warnings": warnings,
            "gateway": {
                "enabled": gateway_port > 0,
                "port": gateway_port,
                "url": f"http://127.0.0.1:{gateway_port}/mcp" if gateway_port > 0 else None,
            },
            "shotgrid": {
                "url_configured": bool(os.environ.get("SHOTGRID_URL")),
                "script_name_configured": bool(os.environ.get("SHOTGRID_SCRIPT_NAME")),
                "script_key_configured": bool(os.environ.get("SHOTGRID_SCRIPT_KEY")),
                "credential_profiles_configured": profiles_configured,
                "project": project,
                "project_id": project_id,
                "permission_level": permission_level,
            },
            "request_context": {
                "meta_key": "_meta",
                "identity_key": "_meta.agent_context",
                "credential_profile_key": "_meta.credential_profile",
                "profile_env": "DCC_MCP_FPT_CREDENTIAL_PROFILES",
                "profile_file_env": "DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE",
                "inline_credentials_enabled": _env_truthy("DCC_MCP_ALLOW_INLINE_CREDENTIALS"),
            },
            "skills": {
                "dcc_mcp_fpt_skill_paths": skill_paths,
                "dcc_mcp_skill_paths": global_skill_paths,
                "missing_paths": missing_skill_paths,
            },
        }

        message = "dcc-mcp-fpt runtime config is ready" if not missing else "dcc-mcp-fpt runtime config is incomplete"
        return skill_success(message, **context)
    except Exception as exc:
        return skill_error(f"Failed to validate runtime config: {exc}", "SETUP_VALIDATE_ERROR")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _split_paths(raw: str) -> List[str]:
    if not raw:
        return []
    return [part for part in raw.split(os.pathsep) if part]


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    run_main(main)
