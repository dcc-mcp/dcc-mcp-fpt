"""Find a single ShotGrid entity by filters."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, filters, fields=None, **params):
    """Find one entity or return None."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        result = server.client.find_one(
            entity_type=entity_type,
            filters=filters,
            fields=fields,
        )
        if result is None:
            return skill_success(f"No {entity_type} found matching filters", found=False, entity=None)
        return skill_success(f"Found {entity_type}", found=True, entity=result)
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Find one failed: {e}", code="QUERY_ERROR")


if __name__ == "__main__":
    run_main(main)
