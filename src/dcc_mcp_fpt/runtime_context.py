"""Runtime context shared by in-process FPT skill scripts."""

from __future__ import annotations

from typing import Any, Optional

_current_server: Optional[Any] = None


def set_current_server(server: Any) -> None:
    """Register the active ShotGrid MCP server for skill scripts."""
    global _current_server
    _current_server = server


def get_current_server() -> Optional[Any]:
    """Return the active ShotGrid MCP server, if one is registered."""
    return _current_server


def clear_current_server(server: Optional[Any] = None) -> None:
    """Clear the active server context.

    When *server* is provided, the context is cleared only if it still points to
    that instance. This avoids one server shutdown accidentally clearing a newer
    server in tests or embedded runtimes.
    """
    global _current_server
    if server is None or _current_server is server:
        _current_server = None
