"""Schema cache for ShotGrid entity schemas."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


class SchemaCache:
    """Thread-safe in-memory cache for ShotGrid schema data.

    Reduces API calls by caching entity schemas with configurable TTL.
    """

    def __init__(self, ttl: float = 3600.0):
        """Initialize the schema cache.

        Args:
            ttl: Time-to-live in seconds for cached entries (default 1 hour).
        """
        self._ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a cached schema entry.

        Args:
            key: Cache key (usually entity type name).

        Returns:
            Cached data or None if expired/missing.
        """
        with self._lock:
            if key not in self._cache:
                return None
            timestamp = self._timestamps.get(key, 0)
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None
            return self._cache[key]

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Store data in the schema cache.

        Args:
            key: Cache key.
            data: Schema data to cache.
        """
        with self._lock:
            self._cache[key] = data
            self._timestamps[key] = time.time()

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate cached entries.

        Args:
            key: Specific key to invalidate, or all if None.
        """
        with self._lock:
            if key is None:
                self._cache.clear()
                self._timestamps.clear()
            else:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)

    @property
    def size(self) -> int:
        """Number of cached entries."""
        return len(self._cache)

    def keys(self):
        """List cached keys."""
        with self._lock:
            return list(self._cache.keys())
