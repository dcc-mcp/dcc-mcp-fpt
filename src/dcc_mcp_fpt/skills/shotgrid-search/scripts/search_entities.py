"""Advanced entity search in ShotGrid."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    entity_type: str,
    text: str = "",
    filters=None,
    fields=None,
    limit: int = 500,
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Search entities with optional text filter."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        # Build filters combining text search with explicit filters
        combined_filters = list(filters or [])
        if text:
            combined_filters.append(["name", "contains", text])

        results = server.client.find(
            entity_type=entity_type,
            filters=combined_filters,
            fields=fields,
            limit=limit,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s)",
            items=results,
            count=len(results),
            text=text,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Search failed: {e}", "SEARCH_ERROR")


if __name__ == "__main__":
    run_main(main)
