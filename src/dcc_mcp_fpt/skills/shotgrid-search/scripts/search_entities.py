"""Advanced entity search in ShotGrid."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, text: str = "", filters=None, fields=None, limit: int = 500, **params):
    """Search entities with optional text filter."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        # Build filters combining text search with explicit filters
        combined_filters = list(filters or [])
        if text:
            combined_filters.append(["name", "contains", text])

        results = server.client.find(
            entity_type=entity_type,
            filters=combined_filters,
            fields=fields,
            limit=limit,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s)",
            items=results,
            count=len(results),
            text=text,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Search failed: {e}", code="SEARCH_ERROR")


if __name__ == "__main__":
    run_main(main)
