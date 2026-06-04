"""Return ShotGrid server version and metadata."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(**params):
    """Retrieve ShotGrid server information."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        info = server.get_connection_info()
        return skill_success(
            f"ShotGrid server at {info.get('url', 'unknown')}",
            server_version=info.get("server_version", "unknown"),
            api_version=info.get("server_version", "unknown"),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Failed to get server info: {e}", code="SERVER_ERROR")


if __name__ == "__main__":
    run_main(main)
