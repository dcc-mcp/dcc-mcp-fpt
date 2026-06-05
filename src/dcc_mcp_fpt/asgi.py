"""ASGI application for serving the ShotGrid MCP server via uvicorn/gunicorn."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


# ASGI application entry point — constructed on first import.
# This module is consumed by uvicorn/gunicorn:
#   uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
#
# The actual ASGI app is provided by dcc-mcp-core's server infrastructure.
# Import here triggers the server to build its ASGI application.
try:
    from dcc_mcp_fpt import __version__
    from dcc_mcp_fpt.server import ShotGridMcpServer

    _server = ShotGridMcpServer(port=0)  # port handled by ASGI server
    _mcp_app = getattr(_server, "asgi_app", None)
    if _mcp_app is None:
        # Fallback: expose the server itself as a callable ASGI app
        # dcc-mcp-core servers typically provide .asgi_app
        logger.warning("ShotGridMcpServer does not expose asgi_app; ensure dcc-mcp-core is properly installed.")
        _mcp_app = _server

    _sg_url = getattr(_server, "_sg_url", "")
    _server_version = getattr(_server, "_server_version", f"dcc-mcp-fpt/{__version__}")
except Exception as exc:
    logger.error("Failed to build ASGI application: %s", exc)
    _mcp_app = None  # type: ignore[assignment]
    _sg_url = ""
    _server_version = ""


async def _health_app(scope, receive, send):
    """Lightweight /health endpoint for Docker HEALTHCHECK and platform probes.

    Returns JSON with status, version, and whether ShotGrid credentials are
    configured.  Never exposes secrets — *sg_configured* is a boolean derived
    from the presence of a non-empty ShotGrid URL.
    """
    if scope.get("type") == "http" and scope.get("path") == "/health":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        body = json.dumps(
            {
                "status": "ok",
                "version": _server_version,
                "sg_configured": bool(_sg_url),
            }
        ).encode("utf-8")
        await send({"type": "http.response.body", "body": body})
        return

    # Delegate to the real MCP ASGI app
    if _mcp_app is None:
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"30"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"status":"starting","error":"ASGI app not ready"}',
            }
        )
        return

    await _mcp_app(scope, receive, send)


# Public ASGI application — uvicorn/gunicorn entry point.
app = _health_app
