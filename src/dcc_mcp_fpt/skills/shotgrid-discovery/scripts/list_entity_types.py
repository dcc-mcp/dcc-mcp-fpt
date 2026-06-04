"""List all available ShotGrid entity types."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(**params):
    """Return all visible ShotGrid entity types."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        entity_types = server.client.get_entity_types()
        return skill_success(
            f"Found {len(entity_types)} entity types",
            entity_types=entity_types,
            count=len(entity_types),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Failed to list entity types: {e}", "SCHEMA_ERROR")


if __name__ == "__main__":
    run_main(main)
