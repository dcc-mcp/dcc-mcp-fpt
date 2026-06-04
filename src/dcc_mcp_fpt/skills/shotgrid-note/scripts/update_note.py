"""Update a ShotGrid note."""

from __future__ import annotations

from dcc_mcp_core.skills_helper import run_main, skill_entry, skill_success, skill_error


@skill_entry
def main(note_id: int, subject: str = "", content: str = "", **params):
    """Update a note's subject or content."""
    try:
        from dcc_mcp_core.server_context import get_current_server

        server = get_current_server()
        if server is None:
            return skill_error("No ShotGrid server instance available", code="NO_SERVER")

        data = {}
        if subject:
            data["subject"] = subject
        if content:
            data["content"] = content

        if not data:
            return skill_error("No subject or content provided for update", code="INVALID_PARAMS")

        result = server.client.update(entity_type="Note", entity_id=note_id, data=data)
        return skill_success(
            f"Updated note id={note_id}",
            note=result,
            note_id=note_id,
        )
    except ImportError as e:
        return skill_error(f"dcc-mcp-fpt not installed: {e}", code="IMPORT_ERROR")
    except Exception as e:
        return skill_error(f"Update note failed: {e}", code="NOTE_ERROR")


if __name__ == "__main__":
    run_main(main)
