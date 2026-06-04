"""Get full schema for all ShotGrid entity types."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(**params):
    """Retrieve the full ShotGrid schema."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        schema = server.client.get_schema()
        entity_count = len(schema) if isinstance(schema, dict) else 0
        return skill_success(
            f"Schema loaded: {entity_count} entity types",
            schema=schema,
            entity_count=entity_count,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Schema read failed: {e}", code="SCHEMA_ERROR")


if __name__ == "__main__":
    run_main(main)
