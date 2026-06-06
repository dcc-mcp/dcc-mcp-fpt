"""Tests for ShotGridClient."""

from __future__ import annotations

import pytest

from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.exceptions import ShotGridQueryError
from dcc_mcp_fpt.models import ShotGridConnectionInfo


class TestShotGridClient:
    """Tests for the ShotGrid API client wrapper."""

    def test_connect(self, shotgrid_client):
        """Client connects and retrieves server info."""
        shotgrid_client.connect()
        info = shotgrid_client.get_connection_info()
        assert isinstance(info, ShotGridConnectionInfo)
        assert info.authenticated is True
        assert info.url == "https://test.shotgrid.autodesk.com"

    def test_get_connection_info_formats_list_version(self, shotgrid_client):
        """ShotGrid API list versions are normalized for diagnostics."""
        shotgrid_client._sg.server_info = {"version": [8, 86, 0]}

        info = shotgrid_client.get_connection_info()

        assert info.authenticated is True
        assert info.server_version == "8.86.0"

    def test_get_connection_info_without_connect(self):
        """get_connection_info returns not authenticated before connect."""
        client = ShotGridClient(
            url="https://test.shotgrid.autodesk.com",
            script_name="test_script",
            api_key="test_key",
        )
        info = client.get_connection_info()
        assert info.authenticated is False

    def test_find_entities(self, shotgrid_client):
        """find returns results."""
        shotgrid_client._sg.find.return_value = [
            {"id": 1, "type": "Shot", "code": "SH001"},
            {"id": 2, "type": "Shot", "code": "SH002"},
        ]
        results = shotgrid_client.find("Shot", [])
        assert len(results) == 2
        assert results[0]["code"] == "SH001"

    def test_find_entities_empty(self, shotgrid_client):
        """find returns empty list when no results."""
        results = shotgrid_client.find("Shot", [["code", "is", "NONEXISTENT"]])
        assert results == []

    def test_find_one_entity(self, shotgrid_client):
        """find_one returns single result."""
        shotgrid_client._sg.find_one.return_value = {"id": 1, "type": "Shot", "code": "SH001"}
        result = shotgrid_client.find_one("Shot", [["code", "is", "SH001"]])
        assert result is not None
        assert result["id"] == 1

    def test_find_one_not_found(self, shotgrid_client):
        """find_one returns None when not found."""
        result = shotgrid_client.find_one("Shot", [["code", "is", "NONEXISTENT"]])
        assert result is None

    def test_create_entity(self, shotgrid_client):
        """create returns the new entity."""
        result = shotgrid_client.create("Shot", {"code": "SH001", "project": {"type": "Project", "id": 1}})
        assert result["id"] == 1
        assert result["code"] == "SH001"

    def test_update_entity(self, shotgrid_client):
        """update returns the updated entity."""
        result = shotgrid_client.update("Shot", 1, {"code": "SH001_MOD"})
        assert result["id"] == 1

    def test_delete_entity(self, shotgrid_client):
        """delete returns True."""
        result = shotgrid_client.delete("Shot", 1)
        assert result is True

    def test_batch(self, shotgrid_client):
        """batch executes multiple operations."""
        shotgrid_client._sg.batch.return_value = [
            {"id": 1, "type": "Shot"},
            {"id": 2, "type": "Shot"},
            True,
        ]
        requests = [
            {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH001"}},
            {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH002"}},
            {"request_type": "delete", "entity_type": "Shot", "entity_id": 3},
        ]
        results = shotgrid_client.batch(requests)
        assert len(results) == 3

    def test_context_manager(self, mock_shotgrid):
        """Client works as context manager."""
        from unittest.mock import patch

        with patch.object(ShotGridClient, "connect", return_value=None):
            with ShotGridClient(
                url="https://test.shotgrid.autodesk.com",
                script_name="test_script",
                api_key="test_key",
            ) as client:
                client._sg = mock_shotgrid
                info = client.get_connection_info()
                assert info.authenticated is True

    def test_close(self, shotgrid_client):
        """close disconnects properly."""
        shotgrid_client.close()
        assert shotgrid_client._sg is None


class TestShotGridClientRetry:
    """Tests for retry behavior."""

    def test_find_retries_on_failure(self, shotgrid_client):
        """find retries up to MAX_RETRIES before raising."""
        shotgrid_client._sg.find.side_effect = Exception("transient error")
        with pytest.raises(ShotGridQueryError):
            shotgrid_client.find("Shot", [])
        # Should have been called MAX_RETRIES times
        assert shotgrid_client._sg.find.call_count == ShotGridClient.MAX_RETRIES

    def test_create_retries_on_failure(self, shotgrid_client):
        """create retries on failure."""
        shotgrid_client._sg.create.side_effect = Exception("transient error")
        with pytest.raises(ShotGridQueryError):
            shotgrid_client.create("Shot", {"code": "SH001"})
        assert shotgrid_client._sg.create.call_count == ShotGridClient.MAX_RETRIES
