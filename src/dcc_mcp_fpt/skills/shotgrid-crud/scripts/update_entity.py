"""Update fields on a ShotGrid entity."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(entity_type: str, entity_id: int, data: dict, **params):
    """Update an existing entity."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        result = server.client.update(
            entity_type=entity_type,
            entity_id=entity_id,
            data=data,
        )
        return skill_success(
            f"Updated {entity_type} id={entity_id}",
            entity=result,
            entity_id=entity_id,
            entity_type=entity_type,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Update failed: {e}", code="UPDATE_ERROR")


if __name__ == "__main__":
    run_main(main)
