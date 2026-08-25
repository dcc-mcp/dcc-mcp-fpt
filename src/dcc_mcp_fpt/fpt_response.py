"""Fail-closed response classification for the external fpt process."""

from __future__ import annotations

from typing import Any, Mapping


def is_failure_response(payload: Mapping[str, Any]) -> bool:
    """Return whether an fpt JSON object explicitly describes failure."""
    status = payload.get("status")
    return (
        payload.get("success") is False
        or payload.get("ok") is False
        or "error" in payload
        or "errors" in payload
        or (isinstance(status, str) and status.lower() in {"error", "failed", "failure"})
    )
