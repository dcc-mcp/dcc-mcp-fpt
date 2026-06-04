"""ASGI application for serving the ShotGrid MCP server via uvicorn/gunicorn."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ASGI application entry point — constructed on first import.
# This module is consumed by uvicorn/gunicorn:
#   uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
#
# The actual ASGI app is provided by dcc-mcp-core's server infrastructure.
# Import here triggers the server to build its ASGI application.
try:
    from dcc_mcp_fpt.server import ShotGridMcpServer

    _server = ShotGridMcpServer(port=0)  # port handled by ASGI server
    app = getattr(_server, "asgi_app", None)
    if app is None:
        # Fallback: expose the server itself as a callable ASGI app
        # dcc-mcp-core servers typically provide .asgi_app
        logger.warning("ShotGridMcpServer does not expose asgi_app; ensure dcc-mcp-core is properly installed.")
        app = _server
except Exception as exc:
    logger.error("Failed to build ASGI application: %s", exc)
    app = None  # type: ignore[assignment]
