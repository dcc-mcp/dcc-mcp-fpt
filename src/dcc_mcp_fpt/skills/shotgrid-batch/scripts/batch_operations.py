"""Execute batch operations on ShotGrid entities."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(requests: list, **params):
    """Execute multiple create/update/delete operations in one call."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        results = server.client.batch(requests=requests)
        return skill_success(
            f"Batch completed: {len(requests)} requests",
            results=results,
            total=len(requests),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Batch failed: {e}", code="BATCH_ERROR")


if __name__ == "__main__":
    run_main(main)
