"""ShotGrid MCP Server — dcc-mcp-core adapter for Autodesk ShotGrid (Flow Production Tracking).

Composes a DccServerBase-based MCP server that bridges AI assistants to
ShotGrid data through typed, progressively-loaded skill tools.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    from dcc_mcp_core import DccServerBase, DccServerOptions, HostExecutionBridge, MinimalModeConfig
except ImportError:  # pragma: no cover
    DccServerBase = object  # type: ignore
    DccServerOptions = None  # type: ignore
    HostExecutionBridge = None  # type: ignore
    MinimalModeConfig = None  # type: ignore

from dcc_mcp_fpt import __version__
from dcc_mcp_fpt.access import ShotGridAccessPolicy
from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.connection_pool import ConnectionPool
from dcc_mcp_fpt.request_context import extract_agent_context, resolve_request_context
from dcc_mcp_fpt.runtime_context import clear_current_server, set_current_server
from dcc_mcp_fpt.schema_cache import SchemaCache
from dcc_mcp_fpt.utils import get_shotgrid_env

logger = logging.getLogger(__name__)


class ShotGridMcpServer(DccServerBase):
    """MCP server for ShotGrid (Flow Production Tracking).

    Provides AI assistants typed access to ShotGrid entities, schema,
    CRUD operations, batch processing, notes, playlists, and search.

    Usage:
        server = ShotGridMcpServer()
        handle = server.start()
        print(f"MCP endpoint: {handle.mcp_url()}")
        # ... use it ...
        handle.shutdown()
    """

    def __init__(
        self,
        port: Optional[int] = None,
        *,
        shotgrid_url: Optional[str] = None,
        shotgrid_script_name: Optional[str] = None,
        shotgrid_script_key: Optional[str] = None,
        shotgrid_project: Optional[str] = None,
        shotgrid_project_id: Optional[int] = None,
        access_policy: Optional[ShotGridAccessPolicy] = None,
        server_name: str = "fpt-mcp",
        server_version: Optional[str] = None,
        gateway_port: Optional[int] = None,
        registry_dir: Optional[str] = None,
        gateway_scene: Optional[str] = None,
        gateway_display_name: Optional[str] = None,
        dcc_version: Optional[str] = None,
        enable_gateway_failover: Optional[bool] = None,
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
            shotgrid_project: Default ShotGrid project name/code/tank name for scoped tools.
            shotgrid_project_id: Default ShotGrid project ID for scoped tools.
            access_policy: Optional project permission policy.
            server_name: MCP server name shown in gateway/admin surfaces.
            server_version: MCP server version shown in gateway/admin surfaces.
            gateway_port: Gateway port. Reads DCC_MCP_GATEWAY_PORT when not set.
            registry_dir: Gateway registry directory.
            gateway_scene: Gateway scene/context label; defaults to the ShotGrid project.
            gateway_display_name: Human-readable gateway instance label.
            dcc_version: Gateway version label; defaults to adapter version.
            enable_gateway_failover: Enable core gateway election/failover.
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
        self._access_policy = access_policy or ShotGridAccessPolicy.from_env()
        self._default_project = (
            shotgrid_project or os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
        )
        self._default_project_id = shotgrid_project_id or _env_int("SHOTGRID_PROJECT_ID")
        self._gateway_scene = gateway_scene or os.environ.get("DCC_MCP_FPT_GATEWAY_SCENE")
        self._gateway_display_name = gateway_display_name or os.environ.get("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME")
        self._server_version = server_version or f"dcc-mcp-fpt/{__version__}"
        self._gateway_dcc_version = dcc_version or self._server_version
        self._client: Optional[ShotGridClient] = None

        # Resolve skills directory
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "skills"

        # Build execution bridge — ShotGrid uses direct HTTP, no host dispatcher needed.
        # dispatcher=None means skill scripts run inline directly (no DCC thread affinity).
        bridge = HostExecutionBridge(dispatcher=None) if HostExecutionBridge else None

        # Resolve options via dcc-mcp-core
        if DccServerOptions is not None:
            options = DccServerOptions.from_env(
                "fpt",
                skills_dir,
                port=port,
                server_name=server_name,
                server_version=self._server_version,
                gateway_port=gateway_port,
                registry_dir=registry_dir,
                dcc_version=self._gateway_dcc_version,
                scene=self._gateway_scene_label(),
                enable_gateway_failover=_resolve_gateway_failover(
                    enable_gateway_failover,
                    gateway_port=gateway_port,
                ),
                execution_bridge=bridge,
                **kwargs,
            )
        else:
            options = None

        if DccServerBase is not object:
            super().__init__(options=options)
        self._port = options.port if options is not None else port

        # Configure minimal mode for progressive skill loading
        self._setup_minimal_mode()
        set_current_server(self)

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
                access_policy=self._access_policy,
                default_project=self._default_project,
                default_project_id=self._default_project_id,
            )
        return self._client

    def client_for_request(self, params: Optional[Dict[str, Any]] = None) -> ShotGridClient:
        """Return the effective ShotGrid client for one tool request."""
        if not params or extract_agent_context(params).is_empty:
            return self.client

        resolved = resolve_request_context(
            params,
            base_policy=self._access_policy,
            default_project=self._default_project,
            default_project_id=self._default_project_id,
        )
        return ShotGridClient(
            resolved.credentials.url,
            resolved.credentials.script_name,
            resolved.credentials.api_key,
            pool=self._connection_pool,
            schema_cache=self._schema_cache,
            access_policy=resolved.access_policy,
            default_project=resolved.default_project,
            default_project_id=resolved.default_project_id,
        )

    # --- Version ---

    def _version_string(self) -> str:
        """Return adapter version string for gateway display."""
        return self._server_version

    # --- Gateway Integration ---

    def _gateway_scene_label(self) -> Optional[str]:
        """Return the project/context label published to the gateway registry."""
        if self._gateway_scene:
            return self._gateway_scene
        if self._default_project:
            return f"project:{self._default_project}"
        if self._default_project_id is not None:
            return f"project-id:{self._default_project_id}"
        return None

    def _gateway_display_label(self) -> str:
        """Return a non-secret gateway display label."""
        if self._gateway_display_name:
            return self._gateway_display_name
        project = self._default_project or (
            f"id:{self._default_project_id}" if self._default_project_id is not None else None
        )
        if project:
            return f"FPT {project}"
        host = urlparse(self._sg_url).netloc if self._sg_url else ""
        return f"FPT {host}" if host else "FPT ShotGrid"

    def publish_gateway_metadata(self, *, reason: str = "manual") -> bool:
        """Publish current FPT context into the dcc-mcp gateway registry."""
        if DccServerBase is object:
            return False
        if not getattr(self, "is_running", False):
            return False

        gateway_port = getattr(getattr(self, "_config", None), "gateway_port", 0)
        if not gateway_port or gateway_port <= 0:
            return False

        try:
            ok = self.update_gateway_metadata(
                scene=self._gateway_scene_label(),
                version=self._gateway_dcc_version,
                documents=[],
                display_name=self._gateway_display_label(),
            )
        except Exception as exc:
            logger.debug("FPT gateway metadata publish failed (%s): %s", reason, exc)
            return False
        return bool(ok)

    def get_gateway_info(self) -> Dict[str, Any]:
        """Return gateway diagnostics without forcing a ShotGrid connection."""
        if DccServerBase is object:
            return {"enabled": False}

        config = getattr(self, "_config", None)
        gateway_port = getattr(config, "gateway_port", 0)
        try:
            is_gateway = bool(getattr(self, "is_gateway", False))
        except Exception:
            is_gateway = False
        try:
            gateway_url = getattr(self, "gateway_url", None)
        except Exception:
            gateway_url = None
        info: Dict[str, Any] = {
            "enabled": bool(gateway_port and gateway_port > 0),
            "port": gateway_port,
            "is_gateway": is_gateway,
            "gateway_url": gateway_url,
            "display_name": self._gateway_display_label(),
            "scene": self._gateway_scene_label(),
            "version": self._gateway_dcc_version,
        }
        try:
            info["election"] = self.get_gateway_election_status()
        except Exception as exc:
            info["election_error"] = str(exc)
        return info

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
                    "shotgrid-setup",
                    "shotgrid-users",
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
            set_current_server(self)
            handle = super().start()
            self.publish_gateway_metadata(reason="startup")
            return handle
        raise NotImplementedError("dcc-mcp-core is required to start the server")

    def shutdown(self) -> None:
        """Shutdown the server and release resources."""
        clear_current_server(self)
        self._connection_pool.close_all()
        if self._client is not None:
            self._client.close()
        if DccServerBase is not object and hasattr(super(), "shutdown"):
            super().shutdown()

    # --- Diagnostics ---

    def get_connection_info(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get ShotGrid connection diagnostics."""
        try:
            client = self.client_for_request(params)
            info = client.get_connection_info().model_dump()
        except Exception as e:
            info = {
                "url": self._sg_url,
                "script_name": self._sg_script_name,
                "authenticated": False,
                "error": str(e),
                "gateway": self.get_gateway_info(),
            }
            try:
                resolved = resolve_request_context(
                    params or {},
                    base_policy=self._access_policy,
                    default_project=self._default_project,
                    default_project_id=self._default_project_id,
                )
                info["request_context"] = resolved.diagnostics()
            except Exception:
                pass
            return info
        info["gateway"] = self.get_gateway_info()
        if params and not extract_agent_context(params).is_empty:
            resolved = resolve_request_context(
                params,
                base_policy=self._access_policy,
                default_project=self._default_project,
                default_project_id=self._default_project_id,
            )
            info["request_context"] = resolved.diagnostics()
        return info

    def get_schema_summary(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get a summary of available ShotGrid entity types."""
        try:
            entity_types = self.client_for_request(params).get_entity_types()
            return {
                "entity_types": entity_types,
                "count": len(entity_types),
                "cached": self._schema_cache.size > 0,
            }
        except Exception as e:
            return {"error": str(e)}


def start_server(
    port: Optional[int] = None,
    *,
    shotgrid_url: Optional[str] = None,
    shotgrid_script_name: Optional[str] = None,
    shotgrid_script_key: Optional[str] = None,
    shotgrid_project: Optional[str] = None,
    shotgrid_project_id: Optional[int] = None,
    server_name: str = "fpt-mcp",
    server_version: Optional[str] = None,
    gateway_port: Optional[int] = None,
    registry_dir: Optional[str] = None,
    gateway_scene: Optional[str] = None,
    gateway_display_name: Optional[str] = None,
    dcc_version: Optional[str] = None,
    enable_gateway_failover: Optional[bool] = None,
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
        shotgrid_project: Default ShotGrid project name/code/tank name.
        shotgrid_project_id: Default ShotGrid project ID.
        server_name: MCP server name shown in gateway/admin surfaces.
        server_version: MCP server version shown in gateway/admin surfaces.
        gateway_port: Gateway port. Reads DCC_MCP_GATEWAY_PORT when not set.
        registry_dir: Gateway registry directory.
        gateway_scene: Gateway scene/context label.
        gateway_display_name: Human-readable gateway instance label.
        dcc_version: Gateway version label.
        enable_gateway_failover: Enable core gateway election/failover.
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
        shotgrid_project=shotgrid_project,
        shotgrid_project_id=shotgrid_project_id,
        server_name=server_name,
        server_version=server_version,
        gateway_port=gateway_port,
        registry_dir=registry_dir,
        gateway_scene=gateway_scene,
        gateway_display_name=gateway_display_name,
        dcc_version=dcc_version,
        enable_gateway_failover=enable_gateway_failover,
        skills_dir=skills_dir,
        connection_pool=connection_pool,
        schema_cache=schema_cache,
    )
    return server.start()


def _env_int(name: str) -> Optional[int]:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _resolve_gateway_failover(value: Optional[bool], *, gateway_port: Optional[int] = None) -> bool:
    """Resolve FPT gateway failover from explicit option or environment."""
    if value is not None:
        return bool(value)
    if gateway_port == 0:
        return False

    raw_gateway_port = os.environ.get("DCC_MCP_GATEWAY_PORT", "").strip()
    if raw_gateway_port:
        try:
            if int(raw_gateway_port) <= 0:
                return False
        except ValueError:
            pass

    raw = os.environ.get("DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER", "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return True
