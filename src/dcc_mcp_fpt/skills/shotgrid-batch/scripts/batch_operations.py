"""Execute batch operations on ShotGrid entities."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(requests: list, project=None, project_id=None, project_scoped: bool = True, **params):
    """Execute multiple create/update/delete operations in one call."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        results = server.client.batch(
            requests=requests,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Batch completed: {len(requests)} requests",
            results=results,
            total=len(requests),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Batch failed: {e}", "BATCH_ERROR")


if __name__ == "__main__":
    run_main(main)
