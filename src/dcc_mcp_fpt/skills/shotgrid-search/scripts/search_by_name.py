"""Find ShotGrid entities by name/code."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    entity_type: str,
    name: str,
    fields=None,
    limit: int = 100,
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Search entities by code or name field (partial match)."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        filters = [["code", "contains", name]]
        results = get_request_client(server, params).find(
            entity_type=entity_type,
            filters=filters,
            fields=fields,
            limit=limit,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s) matching '{name}'",
            items=results,
            count=len(results),
            search_term=name,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Search by name failed: {e}", "SEARCH_ERROR")


if __name__ == "__main__":
    run_main(main)
