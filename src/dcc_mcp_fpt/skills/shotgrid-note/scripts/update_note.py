"""Update a ShotGrid note."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_error, skill_success


@skill_entry
def main(
    note_id: int,
    subject: str = "",
    content: str = "",
    project=None,
    project_id=None,
    project_scoped: bool = True,
    **params,
):
    """Update a note's subject or content."""
    try:
        from dcc_mcp_fpt.runtime_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", "NO_SERVER")

        data = {}
        if subject:
            data["subject"] = subject
        if content:
            data["content"] = content

        if not data:
            return skill_error("No subject or content provided for update", "INVALID_PARAMS")

        result = server.client.update(
            entity_type="Note",
            entity_id=note_id,
            data=data,
            project=project,
            project_id=project_id,
            project_scoped=project_scoped,
        )
        return skill_success(
            f"Updated note id={note_id}",
            note=result,
            note_id=note_id,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", "IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Update note failed: {e}", "NOTE_ERROR")


if __name__ == "__main__":
    run_main(main)
