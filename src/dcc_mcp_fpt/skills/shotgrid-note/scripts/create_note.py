"""Create a note linked to ShotGrid entities."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    subject: str,
    content: str,
    link_entity_type: str = "",
    link_entity_ids=None,
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Create a note and optionally link to entities."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server, get_request_client

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        data = {
            "subject": subject,
            "content": content,
        }
        if project_id:
            data["project"] = {"type": "Project", "id": project_id}
        if link_entity_type and link_entity_ids:
            data["note_links"] = [{"type": link_entity_type, "id": eid} for eid in link_entity_ids]

        result = get_request_client(server, params).create(
            entity_type="Note",
            data=data,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        note_id = result.get("id", "unknown")
        return skill_success(
            f"Created note id={note_id}",
            note=result,
            note_id=note_id,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Create note failed: {e}", "NOTE_ERROR")


if __name__ == "__main__":
    run_main(main)
