"""Find notes linked to a ShotGrid entity."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    link_entity_type: str,
    link_entity_id: int,
    limit: int = 50,
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Find notes attached to a given entity."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        filters = [["note_links", "in", {"type": link_entity_type, "id": link_entity_id}]]
        results = get_request_client(server, params).find(
            entity_type="Note",
            filters=filters,
            fields=["id", "subject", "content", "created_at", "user", "note_links"],
            limit=limit,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Found {len(results)} notes for {link_entity_type} id={link_entity_id}",
            notes=results,
            count=len(results),
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Find notes failed: {e}", "NOTE_ERROR")


if __name__ == "__main__":
    run_main(main)
