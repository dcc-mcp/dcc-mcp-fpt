"""Tests for ShotGrid runtime data contracts."""

from __future__ import annotations

from dcc_mcp_fpt.models import ShotGridConnectionInfo


def test_connection_info_is_serializable() -> None:
    info = ShotGridConnectionInfo(
        url="https://test.shotgrid.autodesk.com",
        script_name="test_script",
        authenticated=True,
        server_version="8.0.0",
    )

    assert info.model_dump() == {
        "url": "https://test.shotgrid.autodesk.com",
        "script_name": "test_script",
        "authenticated": True,
        "server_version": "8.0.0",
    }
