"""Create a new ShotGrid entity."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, data: dict, **params):
    """Create a new entity with the given field values."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        result = server.client.create(entity_type=entity_type, data=data)
        entity_id = result.get("id", "unknown")
        return skill_success(
            f"Created {entity_type} id={entity_id}",
            entity=result,
            entity_id=entity_id,
            entity_type=entity_type,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Create failed: {e}", code="CREATE_ERROR")


if __name__ == "__main__":
    run_main(main)
