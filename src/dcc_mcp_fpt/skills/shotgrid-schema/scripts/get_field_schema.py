"""Get field definitions for a specific entity type."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(entity_type: str, **params):
    """Get field schema for a single entity type."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        schema = get_request_client(server, params).get_schema(entity_type)
        return skill_success(
            f"Schema for {entity_type}",
            entity_type=entity_type,
            fields=schema,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Field schema failed: {e}", "SCHEMA_ERROR")


if __name__ == "__main__":
    run_main(main)
