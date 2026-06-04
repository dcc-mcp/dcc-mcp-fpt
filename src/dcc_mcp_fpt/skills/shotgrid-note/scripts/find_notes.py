"""Find notes linked to a ShotGrid entity."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(link_entity_type: str, link_entity_id: int, limit: int = 50, **params):
    """Find notes attached to a given entity."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        filters = [
            ["note_links", "in", {"type": link_entity_type, "id": link_entity_id}]
        ]
        results = server.client.find(
            entity_type="Note",
            filters=filters,
            fields=["id", "subject", "content", "created_at", "user", "note_links"],
            limit=limit,
        )
        return skill_success(
            f"Found {len(results)} notes for {link_entity_type} id={link_entity_id}",
            notes=results,
            count=len(results),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Find notes failed: {e}", code="NOTE_ERROR")


if __name__ == "__main__":
    run_main(main)
