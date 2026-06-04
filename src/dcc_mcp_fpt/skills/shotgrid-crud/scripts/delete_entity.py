"""Delete (retire) a ShotGrid entity."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(entity_type: str, entity_id: int, project=None, project_id=None, project_scoped: bool = True, **params):
    """Retire (soft-delete) an entity."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        result = get_request_client(server, params).delete(
            entity_type=entity_type,
            entity_id=entity_id,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Deleted {entity_type} id={entity_id}",
            deleted=result,
            entity_id=entity_id,
            entity_type=entity_type,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Delete failed: {e}", "DELETE_ERROR")


if __name__ == "__main__":
    run_main(main)
