"""Generate local dcc-mcp-fpt setup snippets for agents."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success

DEFAULT_ADAPTER_PORT = 8765
DEFAULT_GATEWAY_PORT = 9765


@skill_entry
def main(**params):
    """Generate local, IDE, mcpcall, Docker, and custom skill configuration."""
    try:
        target = str(params.get("target") or "all")
        host = str(params.get("host") or "127.0.0.1")
        adapter_port = _int_param(params.get("adapter_port"), DEFAULT_ADAPTER_PORT)
        gateway_port = _int_param(params.get("gateway_port"), _env_int("DCC_MCP_GATEWAY_PORT", DEFAULT_GATEWAY_PORT))
        project = str(params.get("project") or os.environ.get("SHOTGRID_PROJECT") or "")
        permission_level = str(params.get("permission_level") or os.environ.get("SHOTGRID_PERMISSION_LEVEL") or "read")
        custom_skill_paths = _string_list(params.get("custom_skill_paths"))
        include_secret_values = bool(params.get("include_secret_values", False))

        adapter_url = f"http://{host}:{adapter_port}/mcp"
        gateway_url = f"http://{host}:{gateway_port}/mcp" if gateway_port > 0 else None
        primary_url = gateway_url or adapter_url

        env = _build_env(project, permission_level, gateway_port, custom_skill_paths, include_secret_values)
        start_command = "uvx dcc-mcp-fpt" if gateway_port > 0 else "uvx dcc-mcp-fpt --no-gateway"

        context: Dict[str, Any] = {
            "target": target,
            "start_command": start_command,
            "endpoints": {
                "primary_mcp_url": primary_url,
                "gateway_mcp_url": gateway_url,
                "adapter_mcp_url": adapter_url,
            },
            "environment": env,
        }

        if target in {"all", "ide"}:
            context["ide"] = _ide_config(primary_url, env)
        if target in {"all", "mcpcall"}:
            context["mcpcall"] = _mcpcall_commands(primary_url)
        if target in {"all", "docker"}:
            context["docker"] = _docker_config(adapter_port, gateway_port, custom_skill_paths)
        if target in {"all", "env", "skills"}:
            context["skills"] = _skill_path_config(custom_skill_paths)

        return skill_success("Generated dcc-mcp-fpt setup configuration", **context)
    except Exception as exc:
        return skill_error(f"Failed to generate setup configuration: {exc}", "SETUP_CONFIG_ERROR")


def _build_env(
    project: str,
    permission_level: str,
    gateway_port: int,
    custom_skill_paths: List[str],
    include_secret_values: bool,
) -> Dict[str, str]:
    env = {
        "SHOTGRID_URL": _env_value("SHOTGRID_URL", include_secret_values),
        "SHOTGRID_SCRIPT_NAME": _env_value("SHOTGRID_SCRIPT_NAME", include_secret_values),
        "SHOTGRID_SCRIPT_KEY": _env_value("SHOTGRID_SCRIPT_KEY", include_secret_values, secret=True),
        "SHOTGRID_PROJECT": project or "my_project_code",
        "SHOTGRID_PERMISSION_LEVEL": permission_level,
        "DCC_MCP_GATEWAY_PORT": str(gateway_port),
    }
    if custom_skill_paths:
        env["DCC_MCP_FPT_SKILL_PATHS"] = os.pathsep.join(custom_skill_paths)
    elif os.environ.get("DCC_MCP_FPT_SKILL_PATHS"):
        env["DCC_MCP_FPT_SKILL_PATHS"] = os.environ["DCC_MCP_FPT_SKILL_PATHS"]
    return env


def _ide_config(primary_url: str, env: Dict[str, str]) -> Dict[str, Any]:
    return {
        "http_mcp_config": {
            "mcpServers": {
                "shotgrid": {
                    "url": primary_url,
                }
            }
        },
        "stdio_mcp_config": {
            "mcpServers": {
                "shotgrid": {
                    "command": "uvx",
                    "args": ["dcc-mcp-fpt", "stdio", "--no-gateway"],
                    "env": env,
                }
            }
        },
        "notes": [
            "Prefer the HTTP config when the IDE supports Streamable HTTP MCP.",
            "Use the stdio config only when the IDE does not support HTTP MCP endpoints.",
        ],
    }


def _mcpcall_commands(primary_url: str) -> Dict[str, str]:
    return {
        "doctor": f"mcpcall doctor --url {primary_url} --json",
        "list_tools": f"mcpcall list --url {primary_url} --json",
        "check_connection": f"mcpcall call --url {primary_url} shotgrid-discovery__check_connection",
        "server_info": f"mcpcall call --url {primary_url} shotgrid-discovery__get_server_info",
    }


def _docker_config(adapter_port: int, gateway_port: int, custom_skill_paths: List[str]) -> Dict[str, Any]:
    ports = [f"-p {adapter_port}:8765"]
    if gateway_port > 0:
        ports.append(f"-p {gateway_port}:9765")

    volumes = []
    if custom_skill_paths:
        volumes.append(f"-v {custom_skill_paths[0]}:/skills:ro")

    return {
        "run": " ".join(
            [
                "docker run --rm",
                *ports,
                "--env-file .env",
                *volumes,
                "dcc-mcp-fpt",
            ]
        ),
        "compose": {
            "services": {
                "dcc-mcp-fpt": {
                    "image": "dcc-mcp-fpt",
                    "ports": [f"{adapter_port}:8765", f"{gateway_port}:9765"]
                    if gateway_port > 0
                    else [f"{adapter_port}:8765"],
                    "env_file": [".env"],
                    "volumes": [f"{custom_skill_paths[0]}:/skills:ro"] if custom_skill_paths else [],
                }
            }
        },
    }


def _skill_path_config(custom_skill_paths: List[str]) -> Dict[str, Any]:
    env_value = os.pathsep.join(custom_skill_paths) if custom_skill_paths else "<path-to-parent-of-skill-packages>"
    return {
        "app_specific_env": "DCC_MCP_FPT_SKILL_PATHS",
        "global_env": "DCC_MCP_SKILL_PATHS",
        "path_separator": os.pathsep,
        "example": f"DCC_MCP_FPT_SKILL_PATHS={env_value}",
        "rule": "Point the env var at a skill package directory or a parent directory containing skill package folders.",
    }


def _env_value(name: str, include_secret_values: bool, *, secret: bool = False) -> str:
    value = os.environ.get(name, "")
    if not value:
        return f"<{name.lower()}>"
    if secret and not include_secret_values:
        return "<redacted>"
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _int_param(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


if __name__ == "__main__":
    run_main(main)
