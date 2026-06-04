"""Check ShotGrid connection and return diagnostics."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(**params):
    """Verify ShotGrid credentials and connectivity."""
    try:
        # Access the server singleton (created by the adapter at startup)
        from dcc_mcp_fpt.runtime_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        info = server.get_connection_info()
        return skill_success(
            "ShotGrid connection verified"
            if info.get("authenticated")
            else "ShotGrid connection failed — check credentials",
            **info,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Connection check failed: {e}", "CONNECTION_ERROR")


if __name__ == "__main__":
    run_main(main)
