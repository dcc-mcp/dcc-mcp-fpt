"""Tests for ConnectionPool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dcc_mcp_fpt.connection_pool import ConnectionPool


class TestConnectionPool:
    """Tests for the ShotGrid connection pool."""

    @patch("dcc_mcp_fpt.connection_pool.Shotgun")
    def test_get_creates_connection(self, mock_shotgun_cls, connection_pool):
        """get creates and returns a connection."""
        mock_sg = MagicMock()
        mock_shotgun_cls.return_value = mock_sg

        sg = connection_pool.get(
            "https://test.shotgrid.autodesk.com",
            "test_script",
            "test_key",
        )
        assert sg is mock_sg
        assert connection_pool.size == 1

    @patch("dcc_mcp_fpt.connection_pool.Shotgun")
    def test_get_reuses_connection(self, mock_shotgun_cls, connection_pool):
        """get reuses existing connection for same credentials."""
        mock_sg = MagicMock()
        mock_shotgun_cls.return_value = mock_sg

        sg1 = connection_pool.get("https://test.shotgrid.autodesk.com", "test_script", "test_key")
        sg2 = connection_pool.get("https://test.shotgrid.autodesk.com", "test_script", "test_key")
        assert sg1 is sg2
        assert connection_pool.size == 1

    @patch("dcc_mcp_fpt.connection_pool.Shotgun")
    def test_get_separates_different_api_keys(self, mock_shotgun_cls, connection_pool):
        """get does not reuse a connection across different API keys."""
        first = MagicMock()
        second = MagicMock()
        mock_shotgun_cls.side_effect = [first, second]

        sg1 = connection_pool.get("https://test.shotgrid.autodesk.com", "test_script", "test_key_1")
        sg2 = connection_pool.get("https://test.shotgrid.autodesk.com", "test_script", "test_key_2")
        assert sg1 is first
        assert sg2 is second
        assert connection_pool.size == 2

    @patch("dcc_mcp_fpt.connection_pool.Shotgun")
    def test_release_marks_unused(self, mock_shotgun_cls, connection_pool):
        """release marks connection as not in use."""
        mock_sg = MagicMock()
        mock_shotgun_cls.return_value = mock_sg

        connection_pool.get("https://test.shotgrid.autodesk.com", "test_script", "test_key")
        connection_pool.release("https://test.shotgrid.autodesk.com", "test_script")

    def test_close_all(self, connection_pool):
        """close_all cleans up all connections."""
        # pool closes cleanly even when empty
        connection_pool.close_all()
        assert connection_pool.size == 0

    def test_context_manager(self):
        """ConnectionPool works as context manager."""
        with ConnectionPool(max_size=1) as pool:
            assert pool.size == 0
        # closed on exit
