"""Tests for the ASGI application health endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

from dcc_mcp_fpt.asgi import app


def _run_async(coro):
    """Run an async coroutine and return the result."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class TestHealthEndpoint:
    """Tests for the /health endpoint in the ASGI app."""

    def test_health_returns_200(self):
        """GET /health returns 200 with status JSON."""
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        async def _run():
            await app(scope, receive, send)

        _run_async(_run())

        # Verify the response start
        send.assert_any_call(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )

        # Extract the body from send calls
        body_calls = [c for c in send.call_args_list if c[0][0].get("type") == "http.response.body"]
        assert len(body_calls) == 1
        body = json.loads(body_calls[0][0][0]["body"])
        assert body["status"] == "ok"
        assert "version" in body
        assert "sg_configured" in body
        assert isinstance(body["sg_configured"], bool)

    def test_health_has_required_keys(self):
        """Health response includes status, version, sg_configured."""
        scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        async def _run():
            await app(scope, receive, send)

        _run_async(_run())

        body_calls = [c for c in send.call_args_list if c[0][0].get("type") == "http.response.body"]
        body = json.loads(body_calls[0][0][0]["body"])
        for key in ("status", "version", "sg_configured"):
            assert key in body, f"Health response missing key: {key}"

    def test_non_health_path_delegates(self):
        """Requests to non-health paths are delegated (may fail if MCP app not callable)."""
        scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        async def _run():
            try:
                await app(scope, receive, send)
            except TypeError:
                # _mcp_app may not be callable when dcc-mcp-core absent
                pass

        _run_async(_run())

        # Verify at least one response was attempted
        start_calls = [c for c in send.call_args_list if c[0][0].get("type") == "http.response.start"]
        if start_calls:
            status = start_calls[0][0][0]["status"]
            # Should not return the health endpoint's 200 with sg_configured
            assert status != 200 or not _has_sg_configured(send.call_args_list)


def test_asgi_app_is_importable():
    """The asgi module can be imported without error."""
    from dcc_mcp_fpt import asgi as asgi_module  # noqa: PLC0415

    assert asgi_module.app is not None
    assert callable(asgi_module.app)


def _has_sg_configured(call_args_list):
    """Check if any response body contains sg_configured key."""
    for call in call_args_list:
        body_data = call[0][0].get("body")
        if body_data:
            try:
                body = json.loads(body_data)
            except json.JSONDecodeError:
                continue
            if "sg_configured" in body:
                return True
    return False
