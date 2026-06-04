"""Tests for utility functions."""

from __future__ import annotations

import os

import pytest

from dcc_mcp_fpt.utils import (
    build_filters,
    get_shotgrid_env,
    parse_filters,
    to_human_readable,
)


class TestGetShotgridEnv:
    """Tests for environment variable reading."""

    def test_returns_values(self, monkeypatch):
        """Returns tuple when all vars set."""
        monkeypatch.setenv("SHOTGRID_URL", "https://test.shotgrid.autodesk.com")
        monkeypatch.setenv("SHOTGRID_SCRIPT_NAME", "test_script")
        monkeypatch.setenv("SHOTGRID_SCRIPT_KEY", "test_key")
        url, name, key = get_shotgrid_env()
        assert url == "https://test.shotgrid.autodesk.com"
        assert name == "test_script"
        assert key == "test_key"

    def test_raises_when_missing(self, monkeypatch):
        """Raises ValueError when vars are missing."""
        monkeypatch.delenv("SHOTGRID_URL", raising=False)
        monkeypatch.delenv("SHOTGRID_SCRIPT_NAME", raising=False)
        monkeypatch.delenv("SHOTGRID_SCRIPT_KEY", raising=False)
        with pytest.raises(ValueError, match="Missing ShotGrid environment variables"):
            get_shotgrid_env()

    def test_raises_when_partial(self, monkeypatch):
        """Raises when only some vars set."""
        monkeypatch.setenv("SHOTGRID_URL", "https://test.shotgrid.autodesk.com")
        monkeypatch.delenv("SHOTGRID_SCRIPT_NAME", raising=False)
        monkeypatch.delenv("SHOTGRID_SCRIPT_KEY", raising=False)
        with pytest.raises(ValueError):
            get_shotgrid_env()


class TestParseFilters:
    """Tests for filter string parsing."""

    def test_simple_filter(self):
        """Parses a single filter expression."""
        result = parse_filters("code:is:SH001")
        assert result == [["code", "is", "SH001"]]

    def test_multiple_filters(self):
        """Parses comma-separated filters."""
        result = parse_filters("code:contains:SH, sg_status:is:ip")
        assert len(result) == 2
        assert result[0] == ["code", "contains", "SH"]
        assert result[1] == ["sg_status", "is", "ip"]

    def test_empty_string(self):
        """Returns empty list for empty string."""
        assert parse_filters("") == []


class TestBuildFilters:
    """Tests for filter construction."""

    def test_project_filter(self):
        """Includes project filter when project_id given."""
        result = build_filters(project_id=123)
        assert len(result) == 1
        assert result[0] == ["project", "is", {"type": "Project", "id": 123}]

    def test_combined_filters(self):
        """Combines project and additional conditions."""
        result = build_filters(
            project_id=123,
            conditions=[["sg_status", "is", "ip"]],
        )
        assert len(result) == 2

    def test_empty(self):
        """Returns empty list with no args."""
        assert build_filters() == []


class TestToHumanReadable:
    """Tests for entity dict humanization."""

    def test_resolves_entity_ref(self):
        """Entity references become simplified dicts."""
        result = to_human_readable({
            "id": 1,
            "type": "Shot",
            "project": {"type": "Project", "id": 5, "name": "Demo"},
        })
        assert result["project"] == {"id": 5, "type": "Project", "name": "Demo"}

    def test_resolves_multi_entity(self):
        """Multi-entity fields become lists of simplified refs."""
        result = to_human_readable({
            "id": 1,
            "assets": [
                {"type": "Asset", "id": 10, "name": "Hero"},
                {"type": "Asset", "id": 11, "name": "Prop"},
            ],
        })
        assert len(result["assets"]) == 2
        assert result["assets"][0]["name"] == "Hero"

    def test_passes_through_primitives(self):
        """Primitive values pass through unchanged."""
        result = to_human_readable({
            "code": "SH001",
            "sg_status": "ip",
            "id": 1,
        })
        assert result["code"] == "SH001"
        assert result["sg_status"] == "ip"
