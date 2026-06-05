"""Report effective ShotGrid credentials without exposing secrets."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(**params):
    """Report effective ShotGrid identity, permission level, and active profile."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_connection_info

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        info = get_request_connection_info(server, params)
        request_context = info.get("request_context", {})

        return skill_success(
            "Effective credentials reported",
            script_name=info.get("script_name"),
            url=info.get("url"),
            authenticated=info.get("authenticated"),
            server_version=info.get("server_version"),
            permission_level=request_context.get("effective_permission_level"),
            read_only=request_context.get("read_only"),
            project=request_context.get("project"),
            project_id=request_context.get("project_id"),
            credential_profile=request_context.get("agent_context", {}).get("credential_profile"),
            credential_source=request_context.get("credentials", {}).get("source"),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"whoami failed: {e}", "WHOAMI_ERROR")


if __name__ == "__main__":
    run_main(main)
