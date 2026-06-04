"""Find ShotGrid entities by name/code."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, name: str, fields=None, limit: int = 100, **params):
    """Search entities by code or name field (partial match)."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        filters = [["code", "contains", name]]
        results = server.client.find(
            entity_type=entity_type,
            filters=filters,
            fields=fields,
            limit=limit,
        )
        return skill_success(
            f"Found {len(results)} {entity_type}(s) matching '{name}'",
            items=results,
            count=len(results),
            search_term=name,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Search by name failed: {e}", code="SEARCH_ERROR")


if __name__ == "__main__":
    run_main(main)
