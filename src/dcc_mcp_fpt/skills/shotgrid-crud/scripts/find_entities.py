"""Find ShotGrid entities with filters and pagination."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    entity_type: str,
    filters=None,
    fields=None,
    order=None,
    limit: int = 500,
    page: int = 1,
    retired_only: bool = False,
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Search entities of a given type."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        results = get_request_client(server, params).find(
            entity_type=entity_type,
            filters=filters or [],
            fields=fields,
            order=order,
            limit=limit,
            retired_only=retired_only,
            page=page,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s)",
            items=results,
            count=len(results),
            page=page,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Find failed: {e}", "QUERY_ERROR")


if __name__ == "__main__":
    run_main(main)
