"""ShotGrid MCP Server — dcc-mcp-core adapter for Autodesk ShotGrid (Flow Production Tracking).

Composes a DccServerBase-based MCP server that bridges AI assistants to
ShotGrid data through typed, progressively-loaded skill tools.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from dcc_mcp_core import DccServerBase, DccServerOptions, HostExecutionBridge, MinimalModeConfig
except ImportError:  # pragma: no cover
    DccServerBase = object  # type: ignore
    DccServerOptions = None  # type: ignore
    HostExecutionBridge = None  # type: ignore
    MinimalModeConfig = None  # type: ignore

from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.connection_pool import ConnectionPool
from dcc_mcp_fpt.schema_cache import SchemaCache
from dcc_mcp_fpt.utils import get_shotgrid_env

logger = logging.getLogger(__name__)


class ShotGridMcpServer(DccServerBase):
    """MCP server for ShotGrid (Flow Production Tracking).

    Provides AI assistants typed access to ShotGrid entities, schema,
    CRUD operations, batch processing, notes, playlists, and search.

    Usage:
        server = ShotGridMcpServer(port=8765)
        handle = server.start()
        print(f"MCP endpoint: {handle.mcp_url()}")
        # ... use it ...
        handle.shutdown()
    """

    def __init__(
        self,
        port: int = 8765,
        *,
        shotgrid_url: Optional[str] = None,
        shotgrid_script_name: Optional[str] = None,
        shotgrid_script_key: Optional[str] = None,
        skills_dir: Optional[Path] = None,
        connection_pool: Optional[ConnectionPool] = None,
        schema_cache: Optional[SchemaCache] = None,
        **kwargs,
    ):
        """Initialize the ShotGrid MCP server.

        Args:
            port: HTTP port for the MCP server.
            shotgrid_url: ShotGrid server URL. Reads from SHOTGRID_URL env if not set.
            shotgrid_script_name: Script name. Reads from SHOTGRID_SCRIPT_NAME env if not set.
            shotgrid_script_key: Script key. Reads from SHOTGRID_SCRIPT_KEY env if not set.
            skills_dir: Path to bundled skills directory.
            connection_pool: Optional shared connection pool.
            schema_cache: Optional shared schema cache.
            **kwargs: Additional options passed to DccServerOptions.
        """
        # Resolve ShotGrid credentials
        if shotgrid_url and shotgrid_script_name and shotgrid_script_key:
            self._sg_url = shotgrid_url
            self._sg_script_name = shotgrid_script_name
            self._sg_script_key = shotgrid_script_key
        else:
            try:
                self._sg_url, self._sg_script_name, self._sg_script_key = get_shotgrid_env()
            except ValueError:
                # Allow lazy initialization — tools will validate on first use
                self._sg_url = ""
                self._sg_script_name = ""
                self._sg_script_key = ""

        # Shared resources
        self._connection_pool = connection_pool or ConnectionPool()
        self._schema_cache = schema_cache or SchemaCache()
        self._client: Optional[ShotGridClient] = None

        # Resolve skills directory
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "skills"

        # Build execution bridge — ShotGrid uses direct HTTP, no host dispatcher needed.
        # We use a callable bridge that routes to the ShotGridClient methods.
        bridge = HostExecutionBridge(dispatcher=self._dispatch) if HostExecutionBridge else None

        # Resolve options via dcc-mcp-core
        if DccServerOptions is not None:
            options = DccServerOptions.from_env(
                "SHOTGRID",
                skills_dir,
                port=port,
                execution_bridge=bridge,
                **kwargs,
            )
        else:
            options = None

        if DccServerBase is not object:
            super().__init__(options=options)
        self._port = port

        # Configure minimal mode for progressive skill loading
        self._setup_minimal_mode()

    # --- ShotGrid Client Access ---

    @property
    def client(self) -> ShotGridClient:
        """Get or lazily create the ShotGrid API client."""
        if self._client is None:
            if not all([self._sg_url, self._sg_script_name, self._sg_script_key]):
                raise ValueError(
                    "ShotGrid credentials not configured. "
                    "Set SHOTGRID_URL, SHOTGRID_SCRIPT_NAME, and SHOTGRID_SCRIPT_KEY "
                    "environment variables."
                )
            self._client = ShotGridClient(
                self._sg_url,
                self._sg_script_name,
                self._sg_script_key,
                pool=self._connection_pool,
                schema_cache=self._schema_cache,
            )
        return self._client

    # --- Dispatch (host bridge) ---

    def _dispatch(self, method: str, *args, **kwargs) -> Any:
        """Route a tool call to the ShotGrid client method.

        This is the HostExecutionBridge dispatcher — each skill tool
        calls through here to reach the ShotGrid API.
        """
        client = self.client
        fn = getattr(client, method, None)
        if fn is None:
            raise AttributeError(f"ShotGridClient has no method '{method}'")
        return fn(*args, **kwargs)

    # --- Version ---

    def _version_string(self) -> str:
        """Return adapter version string for gateway display."""
        from dcc_mcp_fpt import __version__

        return f"dcc-mcp-fpt/{__version__}"

    # --- Minimal Mode ---

    def _setup_minimal_mode(self) -> None:
        """Configure progressive skill loading with MinimalModeConfig.

        Eager-loads core discovery, diagnostics, and basic CRUD skills.
        Advanced batch, schema, and pipeline skills load on demand.
        """
        if MinimalModeConfig is None:
            return

        try:
            minimal = MinimalModeConfig(
                skills=(
                    "shotgrid-discovery",
                    "shotgrid-crud",
                    "shotgrid-search",
                ),
                deactivate_groups={
                    "shotgrid-crud": ("batch",),
                },
                env_var_minimal="DCC_MCP_SHOTGRID_MINIMAL",
                env_var_default_tools="DCC_MCP_SHOTGRID_DEFAULT_TOOLS",
            )
            if hasattr(self, "register_builtin_actions"):
                self.register_builtin_actions(minimal_mode=minimal)
        except Exception as exc:
            logger.warning("Failed to configure minimal mode: %s", exc)

    # --- Lifecycle ---

    def start(self):
        """Start the ShotGrid MCP server."""
        if DccServerBase is not object:
            return super().start()
        raise NotImplementedError("dcc-mcp-core is required to start the server")

    def shutdown(self) -> None:
        """Shutdown the server and release resources."""
        self._connection_pool.close_all()
        if self._client is not None:
            self._client.close()
        if DccServerBase is not object and hasattr(super(), "shutdown"):
            super().shutdown()

    # --- Diagnostics ---

    def get_connection_info(self) -> Dict[str, Any]:
        """Get ShotGrid connection diagnostics."""
        try:
            info = self.client.get_connection_info()
            return info.model_dump()
        except Exception as e:
            return {
                "url": self._sg_url,
                "script_name": self._sg_script_name,
                "authenticated": False,
                "error": str(e),
            }

    def get_schema_summary(self) -> Dict[str, Any]:
        """Get a summary of available ShotGrid entity types."""
        try:
            entity_types = self.client.get_entity_types()
            return {
                "entity_types": entity_types,
                "count": len(entity_types),
                "cached": self._schema_cache.size > 0,
            }
        except Exception as e:
            return {"error": str(e)}


def start_server(
    port: int = 8765,
    *,
    shotgrid_url: Optional[str] = None,
    shotgrid_script_name: Optional[str] = None,
    shotgrid_script_key: Optional[str] = None,
    skills_dir: Optional[Path] = None,
    connection_pool: Optional[ConnectionPool] = None,
    schema_cache: Optional[SchemaCache] = None,
) -> Any:
    """Convenience function to create and start a ShotGrid MCP server.

    Args:
        port: HTTP port for the MCP server.
        shotgrid_url: ShotGrid server URL (or from env).
        shotgrid_script_name: Script name (or from env).
        shotgrid_script_key: Script key (or from env).
        skills_dir: Path to skills directory.
        connection_pool: Optional shared connection pool.
        schema_cache: Optional shared schema cache.

    Returns:
        Server handle with .mcp_url() and .shutdown() methods.
    """
    server = ShotGridMcpServer(
        port=port,
        shotgrid_url=shotgrid_url,
        shotgrid_script_name=shotgrid_script_name,
        shotgrid_script_key=shotgrid_script_key,
        skills_dir=skills_dir,
        connection_pool=connection_pool,
        schema_cache=schema_cache,
    )
    return server.start()
