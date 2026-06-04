"""Connection pool for ShotGrid API sessions."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Dict, Optional

from shotgun_api3 import Shotgun

logger = logging.getLogger(__name__)


class PooledConnection:
    """A Shotgun connection in the pool with metadata."""

    def __init__(self, sg: Shotgun):
        self.sg = sg
        self.created_at = time.time()
        self.last_used = time.time()
        self.in_use = False

    def mark_used(self) -> None:
        self.last_used = time.time()


class ConnectionPool:
    """Thread-safe connection pool for ShotGrid API sessions.

    Reuses authenticated sessions to avoid repeated handshakes.
    Connections are created lazily and evicted after idle timeout.
    """

    def __init__(
        self,
        max_size: int = 5,
        idle_timeout: float = 300.0,  # 5 minutes
    ):
        """Initialize the connection pool.

        Args:
            max_size: Maximum number of concurrent connections.
            idle_timeout: Seconds before idle connections are evicted.
        """
        self._max_size = max_size
        self._idle_timeout = idle_timeout
        self._connections: Dict[str, PooledConnection] = {}
        self._lock = threading.RLock()

    def get(
        self,
        url: str,
        script_name: str,
        api_key: str,
        proxy: Optional[str] = None,
    ) -> Shotgun:
        """Get or create a Shotgun connection.

        Args:
            url: ShotGrid server URL.
            script_name: Script/API user name.
            api_key: Script/API user key.
            proxy: Optional HTTP proxy URL.

        Returns:
            An authenticated Shotgun instance.
        """
        conn_key = _connection_key(url, script_name, api_key, proxy)
        with self._lock:
            # Evict stale connections
            self._evict_idle()

            # Return existing connection if available
            pooled = self._connections.get(conn_key)
            if pooled is not None:
                pooled.mark_used()
                pooled.in_use = True
                return pooled.sg

            # Create new connection
            if len(self._connections) >= self._max_size:
                self._evict_oldest_available()
            if len(self._connections) >= self._max_size:
                raise RuntimeError("ShotGrid connection pool is at capacity")

            sg = Shotgun(url, script_name, api_key, http_proxy=proxy)
            pooled = PooledConnection(sg)
            pooled.in_use = True
            self._connections[conn_key] = pooled
            return sg

    def release(
        self,
        url: str,
        script_name: str,
        api_key: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> None:
        """Release a connection back to the pool."""
        conn_key = _connection_key(url, script_name, api_key, proxy) if api_key is not None else None
        with self._lock:
            if conn_key is not None:
                pooled = self._connections.get(conn_key)
                if pooled is not None:
                    pooled.in_use = False
                return

            prefix = f"{url.rstrip('/')}:{script_name}:"
            for key, pooled in self._connections.items():
                if key.startswith(prefix):
                    pooled.in_use = False

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for key, pooled in list(self._connections.items()):
                try:
                    pooled.sg.close()
                except Exception:
                    pass
                del self._connections[key]

    def _evict_idle(self) -> None:
        """Remove connections that have been idle too long."""
        now = time.time()
        stale_keys = []
        for key, pooled in self._connections.items():
            if not pooled.in_use and (now - pooled.last_used) > self._idle_timeout:
                stale_keys.append(key)
        for key in stale_keys:
            try:
                self._connections[key].sg.close()
            except Exception:
                pass
            del self._connections[key]
            logger.debug("Evicted idle connection: %s", key)

    def _evict_oldest_available(self) -> None:
        """Evict the oldest idle connection when the pool reaches capacity."""
        available = [(key, pooled) for key, pooled in self._connections.items() if not pooled.in_use]
        if not available:
            return
        key, pooled = min(available, key=lambda item: item[1].last_used)
        try:
            pooled.sg.close()
        except Exception:
            pass
        del self._connections[key]
        logger.debug("Evicted oldest available connection: %s", key)

    @property
    def size(self) -> int:
        """Number of active connections."""
        return len(self._connections)

    def __enter__(self) -> "ConnectionPool":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close_all()


def _connection_key(
    url: str,
    script_name: str,
    api_key: str,
    proxy: Optional[str],
) -> str:
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
    proxy_key = proxy or ""
    return f"{url.rstrip('/')}:{script_name}:{key_hash}:{proxy_key}"
