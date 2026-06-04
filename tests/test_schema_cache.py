"""Tests for SchemaCache."""

from __future__ import annotations

import time

from dcc_mcp_fpt.schema_cache import SchemaCache


class TestSchemaCache:
    """Tests for the ShotGrid schema cache."""

    def test_set_and_get(self, schema_cache):
        """Data is retrievable after set."""
        data = {"Shot": {"fields": {"code": {"data_type": "text"}}}}
        schema_cache.set("Shot", data)
        result = schema_cache.get("Shot")
        assert result is not None
        assert result["Shot"]["fields"]["code"]["data_type"] == "text"

    def test_get_missing(self, schema_cache):
        """get returns None for missing keys."""
        assert schema_cache.get("nonexistent") is None

    def test_get_expired(self, schema_cache):
        """get returns None for expired entries."""
        schema_cache._ttl = 0.01  # 10ms TTL
        schema_cache.set("Shot", {"data": "test"})
        time.sleep(0.02)
        assert schema_cache.get("Shot") is None

    def test_invalidate_key(self, schema_cache):
        """invalidate removes a specific key."""
        schema_cache.set("Shot", {"test": True})
        schema_cache.set("Asset", {"test": True})
        schema_cache.invalidate("Shot")
        assert schema_cache.get("Shot") is None
        assert schema_cache.get("Asset") is not None

    def test_invalidate_all(self, schema_cache):
        """invalidate with no key clears everything."""
        schema_cache.set("Shot", {"test": True})
        schema_cache.set("Asset", {"test": True})
        schema_cache.invalidate()
        assert schema_cache.size == 0

    def test_size(self, schema_cache):
        """size reflects number of cached entries."""
        assert schema_cache.size == 0
        schema_cache.set("Shot", {})
        assert schema_cache.size == 1

    def test_keys(self, schema_cache):
        """keys returns list of cache keys."""
        schema_cache.set("Shot", {})
        schema_cache.set("Asset", {})
        keys = schema_cache.keys()
        assert "Shot" in keys
        assert "Asset" in keys
