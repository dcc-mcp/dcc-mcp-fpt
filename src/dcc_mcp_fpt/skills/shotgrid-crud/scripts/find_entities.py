"""Find ShotGrid entities with filters and pagination."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, filters=None, fields=None, order=None, limit: int = 500, page: int = 1, **params):
    """Search entities of a given type."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        results = server.client.find(
            entity_type=entity_type,
            filters=filters or [],
            fields=fields,
            order=order,
            limit=limit,
            page=page,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s)",
            items=results,
            count=len(results),
            page=page,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Find failed: {e}", code="QUERY_ERROR")


if __name__ == "__main__":
    run_main(main)
