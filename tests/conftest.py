"""Shared test fixtures and mocks for dcc-mcp-fpt tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_shotgrid():
    """Mock Shotgun API connection."""
    from unittest.mock import MagicMock

    sg = MagicMock()
    sg.server_info = {"version": "8.0.0"}
    sg.find.return_value = []
    sg.find_one.return_value = None
    sg.create.return_value = {"id": 1, "type": "Shot", "code": "SH001"}
    sg.update.return_value = {"id": 1, "type": "Shot", "code": "SH001"}
    sg.delete.return_value = True
    sg.batch.return_value = []
    sg.schema_read.return_value = {}
    sg.schema_field_read.return_value = {}
    return sg


@pytest.fixture
def shotgrid_client(mock_shotgrid):
    """Create a ShotGridClient with a mocked connection."""
    from dcc_mcp_fpt.client import ShotGridClient

    client = ShotGridClient(
        url="https://test.shotgrid.autodesk.com",
        script_name="test_script",
        api_key="test_key",
    )
    # Inject mock
    client._sg = mock_shotgrid
    return client


@pytest.fixture
def connection_pool():
    """Create a fresh ConnectionPool."""
    from dcc_mcp_fpt.connection_pool import ConnectionPool

    pool = ConnectionPool(max_size=2, idle_timeout=60)
    yield pool
    pool.close_all()


@pytest.fixture
def schema_cache():
    """Create a fresh SchemaCache."""
    from dcc_mcp_fpt.schema_cache import SchemaCache

    return SchemaCache(ttl=60)
