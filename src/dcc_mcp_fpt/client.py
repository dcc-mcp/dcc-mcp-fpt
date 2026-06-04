"""ShotGrid API client with connection pooling and retry support."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from shotgun_api3 import Shotgun

from dcc_mcp_fpt.access import ProjectRef, ShotGridAccessPolicy
from dcc_mcp_fpt.connection_pool import ConnectionPool
from dcc_mcp_fpt.exceptions import (
    ShotGridConnectionError,
    ShotGridQueryError,
)
from dcc_mcp_fpt.models import ShotGridConnectionInfo
from dcc_mcp_fpt.schema_cache import SchemaCache

logger = logging.getLogger(__name__)


GLOBAL_ENTITY_TYPES = {
    "ApiUser",
    "Department",
    "EventLogEntry",
    "Group",
    "HumanUser",
    "LocalStorage",
    "Page",
    "PermissionRuleSet",
    "PipelineConfiguration",
    "Project",
    "ScriptUser",
    "Step",
    "TaskTemplate",
}


class ShotGridClient:
    """Wraps the ShotGrid API with connection pooling, retries, and schema caching.

    This is the primary entry point for all ShotGrid API interactions.
    It should be instantiated once and reused across tool calls.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(
        self,
        url: str,
        script_name: str,
        api_key: str,
        *,
        pool: Optional[ConnectionPool] = None,
        schema_cache: Optional[SchemaCache] = None,
        access_policy: Optional[ShotGridAccessPolicy] = None,
        default_project: Optional[str] = None,
        default_project_id: Optional[int] = None,
        proxy: Optional[str] = None,
    ):
        """Initialize the ShotGrid client.

        Args:
            url: ShotGrid server URL (e.g., https://mysite.shotgrid.autodesk.com).
            script_name: Script/API user name.
            api_key: Script/API user key.
            pool: Optional shared connection pool.
            schema_cache: Optional shared schema cache.
            access_policy: Optional per-project permission policy.
            default_project: Optional project name/code/tank name for scoped operations.
            default_project_id: Optional project ID for scoped operations.
            proxy: Optional HTTP proxy URL.
        """
        self._url = url.rstrip("/")
        self._script_name = script_name
        self._api_key = api_key
        self._proxy = proxy
        self._pool = pool or ConnectionPool()
        self._schema_cache = schema_cache or SchemaCache()
        self._access_policy = access_policy or ShotGridAccessPolicy.from_env()
        self._default_project = (
            default_project
            if default_project is not None
            else os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
        )
        self._default_project_id = (
            default_project_id if default_project_id is not None else _env_int("SHOTGRID_PROJECT_ID")
        )
        self._project_cache: Dict[str, ProjectRef] = {}
        self._entity_project_cache: Dict[str, Optional[ProjectRef]] = {}
        self._sg: Optional[Shotgun] = None

    # --- Connection Management ---

    @property
    def sg(self) -> Shotgun:
        """Get or create the active Shotgun connection."""
        if self._sg is None:
            self.connect()
        return self._sg  # type: ignore[return-value]

    def connect(self) -> None:
        """Establish connection to ShotGrid."""
        if self._sg is not None:
            return  # Already connected (or mock injected for testing)
        logger.info("Connecting to ShotGrid at %s", self._url)
        try:
            self._sg = self._pool.get(
                self._url,
                self._script_name,
                self._api_key,
                proxy=self._proxy,
            )
            # Verify connection by fetching server info
            _server_info = self._sg.server_info
            logger.info("Connected to ShotGrid successfully.")
        except Exception as e:
            raise ShotGridConnectionError(f"Failed to connect to ShotGrid at {self._url}: {e}") from e

    def close(self) -> None:
        """Close the ShotGrid connection."""
        if self._sg is not None:
            try:
                self._pool.release(self._url, self._script_name, self._api_key, self._proxy)
            except Exception:
                pass
            self._sg = None

    def get_connection_info(self) -> ShotGridConnectionInfo:
        """Retrieve connection metadata for diagnostics."""
        if self._sg is None:
            return ShotGridConnectionInfo(
                url=self._url,
                script_name=self._script_name,
                authenticated=False,
            )

        try:
            info = self._sg.server_info
            return ShotGridConnectionInfo(
                url=self._url,
                script_name=self._script_name,
                authenticated=True,
                server_version=_format_server_version(info.get("version") or info.get("full_version")),
            )
        except Exception:
            return ShotGridConnectionInfo(
                url=self._url,
                script_name=self._script_name,
                authenticated=False,
            )

    # --- Query Operations ---

    def find(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
        order: Optional[List[Dict[str, str]]] = None,
        limit: int = 500,
        retired_only: bool = False,
        page: int = 1,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find entities matching the given filters.

        Args:
            entity_type: The entity type to query (e.g., 'Shot', 'Asset').
            filters: ShotGrid filter expressions.
            fields: Fields to retrieve (all if None).
            order: Sort order specification.
            limit: Maximum number of results.
            retired_only: Whether to include retired entities.
            page: Page number for pagination.
            project: Optional project name/code/tank name to scope the query.
            project_id: Optional project ID to scope the query.
            project_scoped: Whether to add a project filter when a project is available.

        Returns:
            List of entity dictionaries.
        """
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        self._access_policy.require(
            "find",
            project_ref=project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        scoped_filters = self._with_project_filter(entity_type, filters, project_ref)
        for attempt in range(self.MAX_RETRIES):
            try:
                results = self.sg.find(
                    entity_type,
                    scoped_filters,
                    fields=fields,
                    order=order,
                    limit=limit,
                    retired_only=retired_only,
                    page=page,
                )
                return list(results) if results else []
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid find attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid find failed for {entity_type}: {e}") from e
        return []

    def find_one(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Find a single entity or return None.

        Args:
            entity_type: The entity type to query.
            filters: ShotGrid filter expressions.
            fields: Fields to retrieve.
            project: Optional project name/code/tank name to scope the query.
            project_id: Optional project ID to scope the query.
            project_scoped: Whether to add a project filter when a project is available.

        Returns:
            Entity dictionary or None if not found.
        """
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        self._access_policy.require(
            "find_one",
            project_ref=project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        scoped_filters = self._with_project_filter(entity_type, filters, project_ref)
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.sg.find_one(entity_type, scoped_filters, fields=fields)
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid find_one attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid find_one failed for {entity_type}: {e}") from e
        return None

    # --- CRUD Operations ---

    def create(
        self,
        entity_type: str,
        data: Dict[str, Any],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Dict[str, Any]:
        """Create a new ShotGrid entity.

        Args:
            entity_type: Entity type to create.
            data: Field values for the new entity.
            project: Optional project name/code/tank name to scope the mutation.
            project_id: Optional project ID to scope the mutation.
            project_scoped: Whether to inject project when a project is available.

        Returns:
            Created entity dictionary.
        """
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        data = self._with_project_data(entity_type, data, project_ref)
        self._access_policy.require(
            "create",
            project_ref=self._project_from_data(data) or project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        for attempt in range(self.MAX_RETRIES):
            try:
                result = self.sg.create(entity_type, data)
                logger.info("Created %s: %s", entity_type, result)
                return result
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid create attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid create failed for {entity_type}: {e}") from e
        return {}

    def update(
        self,
        entity_type: str,
        entity_id: int,
        data: Dict[str, Any],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Dict[str, Any]:
        """Update an existing ShotGrid entity.

        Args:
            entity_type: Entity type to update.
            entity_id: ID of the entity to update.
            data: Field values to update.
            project: Optional project name/code/tank name to scope the mutation.
            project_id: Optional project ID to scope the mutation.
            project_scoped: Whether to validate project ownership.

        Returns:
            Updated entity dictionary.
        """
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        data_project = self._project_from_data(data)
        target_project = data_project or project_ref or self._entity_project(entity_type, entity_id)
        self._access_policy.require(
            "update",
            project_ref=target_project,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        for attempt in range(self.MAX_RETRIES):
            try:
                result = self.sg.update(entity_type, entity_id, data)
                logger.info("Updated %s id=%d", entity_type, entity_id)
                return result
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid update attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid update failed for {entity_type} id={entity_id}: {e}") from e
        return {}

    def delete(
        self,
        entity_type: str,
        entity_id: int,
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> bool:
        """Delete a ShotGrid entity.

        Args:
            entity_type: Entity type to delete.
            entity_id: ID of the entity to delete.
            project: Optional project name/code/tank name to scope the mutation.
            project_id: Optional project ID to scope the mutation.
            project_scoped: Whether to validate project ownership.

        Returns:
            True if deleted successfully.
        """
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        target_project = project_ref or self._entity_project(entity_type, entity_id)
        self._access_policy.require(
            "delete",
            project_ref=target_project,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        for attempt in range(self.MAX_RETRIES):
            try:
                self.sg.delete(entity_type, entity_id)
                logger.info("Deleted %s id=%d", entity_type, entity_id)
                return True
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid delete attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid delete failed for {entity_type} id={entity_id}: {e}") from e
        return False

    # --- Batch Operations ---

    def batch(
        self,
        requests: List[Dict[str, Any]],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> List[Any]:
        """Execute batch operations.

        Args:
            requests: List of batch request dicts with keys:
                request_type: 'create', 'update', or 'delete'
                entity_type: Entity type
                entity_id: Entity ID (for update/delete)
                data: Field values (for create/update)
            project: Optional project name/code/tank name to scope the batch.
            project_id: Optional project ID to scope the batch.
            project_scoped: Whether to inject/validate project context.

        Returns:
            List of results matching request order.
        """
        default_project_ref = self.resolve_project(project, project_id) if project_scoped else None
        default_project_identifier = project or self._default_project
        prepared_requests = [
            self._prepare_batch_request(request, default_project_ref, default_project_identifier)
            for request in requests
        ]
        for attempt in range(self.MAX_RETRIES):
            try:
                results = self.sg.batch(prepared_requests)
                logger.info("Batch: %d requests completed", len(prepared_requests))
                return results if results else []
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid batch attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"ShotGrid batch failed: {e}") from e
        return []

    # --- Project and Access Helpers ---

    def resolve_project(
        self,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> Optional[ProjectRef]:
        """Resolve a project identifier to a cached ShotGrid project reference."""
        effective_id = project_id if project_id is not None else self._default_project_id
        effective_project = project or self._default_project

        if effective_id is None and not effective_project:
            return None

        cache_key = f"id:{effective_id}" if effective_id is not None else str(effective_project)
        cached = self._project_cache.get(cache_key.lower())
        if cached is not None:
            return cached

        if effective_id is not None:
            entity = self._find_one_raw("Project", [["id", "is", effective_id]], self._project_fields())
            if entity is None:
                raise ShotGridQueryError(f"ShotGrid Project id={effective_id} was not found")
        else:
            entity = self._find_project_by_identifier(str(effective_project))

        project_ref = ProjectRef(
            id=int(entity["id"]),
            name=entity.get("name"),
            code=entity.get("code"),
            tank_name=entity.get("tank_name"),
        )
        for key in project_ref.policy_keys():
            self._project_cache[key.lower()] = project_ref
        self._project_cache[cache_key.lower()] = project_ref
        return project_ref

    def _find_project_by_identifier(self, identifier: str) -> Dict[str, Any]:
        for field in ("name", "tank_name", "code"):
            try:
                entity = self._find_one_raw(
                    "Project",
                    [[field, "is", identifier]],
                    self._project_fields(),
                )
            except ShotGridQueryError:
                continue
            if entity is not None:
                return entity
        raise ShotGridQueryError(f"ShotGrid Project '{identifier}' was not found")

    def _project_fields(self) -> List[str]:
        return ["id", "name", "tank_name", "code"]

    def _find_one_raw(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        field_attempts = [fields, ["id", "name"], None] if fields else [None]
        last_error: Optional[Exception] = None
        for attempt_fields in field_attempts:
            for attempt in range(self.MAX_RETRIES):
                try:
                    return self.sg.find_one(entity_type, filters, fields=attempt_fields)
                except Exception as exc:
                    last_error = exc
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY * (attempt + 1))
                    else:
                        break
        raise ShotGridQueryError(f"ShotGrid find_one failed for {entity_type}: {last_error}")

    def _with_project_filter(
        self,
        entity_type: str,
        filters: List[Any],
        project_ref: Optional[ProjectRef],
    ) -> List[Any]:
        if project_ref is None or entity_type in GLOBAL_ENTITY_TYPES or _has_project_filter(filters):
            return list(filters or [])
        return list(filters or []) + [["project", "is", project_ref.as_entity_ref()]]

    def _with_project_data(
        self,
        entity_type: str,
        data: Dict[str, Any],
        project_ref: Optional[ProjectRef],
    ) -> Dict[str, Any]:
        result = dict(data)
        if project_ref is not None and entity_type not in GLOBAL_ENTITY_TYPES and "project" not in result:
            result["project"] = project_ref.as_entity_ref()
        return result

    def _project_from_data(self, data: Dict[str, Any]) -> Optional[ProjectRef]:
        value = data.get("project")
        if isinstance(value, dict) and value.get("type") == "Project" and value.get("id"):
            return ProjectRef(
                id=int(value["id"]),
                name=value.get("name"),
                code=value.get("code"),
                tank_name=value.get("tank_name"),
            )
        return None

    def _entity_project(self, entity_type: str, entity_id: int) -> Optional[ProjectRef]:
        if entity_type == "Project":
            return ProjectRef(id=entity_id)

        cache_key = f"{entity_type}:{entity_id}"
        if cache_key in self._entity_project_cache:
            return self._entity_project_cache[cache_key]

        try:
            entity = self._find_one_raw(
                entity_type,
                [["id", "is", entity_id]],
                ["id", "project"],
            )
        except ShotGridQueryError:
            self._entity_project_cache[cache_key] = None
            return None

        project_ref = None
        if entity:
            project_ref = self._project_from_data(entity)
        self._entity_project_cache[cache_key] = project_ref
        return project_ref

    def _prepare_batch_request(
        self,
        request: Dict[str, Any],
        default_project_ref: Optional[ProjectRef],
        default_project_identifier: Optional[str],
    ) -> Dict[str, Any]:
        prepared = dict(request)
        request_type = str(prepared.get("request_type", "")).lower()
        entity_type = str(prepared.get("entity_type", ""))
        request_project = prepared.pop("project", None)
        request_project_id = prepared.pop("project_id", None)
        project_ref = default_project_ref
        if request_project or request_project_id:
            project_ref = self.resolve_project(request_project, request_project_id)

        if request_type == "create":
            data = self._with_project_data(entity_type, prepared.get("data") or {}, project_ref)
            prepared["data"] = data
            target_project = self._project_from_data(data) or project_ref
            self._access_policy.require(
                "create",
                project_ref=target_project,
                project_identifier=request_project or default_project_identifier,
                entity_type=entity_type,
            )
        elif request_type == "update":
            data = prepared.get("data") or {}
            target_project = self._project_from_data(data) or project_ref
            if target_project is None and prepared.get("entity_id") is not None:
                target_project = self._entity_project(entity_type, int(prepared["entity_id"]))
            self._access_policy.require(
                "update",
                project_ref=target_project,
                project_identifier=request_project or default_project_identifier,
                entity_type=entity_type,
            )
        elif request_type == "delete":
            target_project = project_ref
            if target_project is None and prepared.get("entity_id") is not None:
                target_project = self._entity_project(entity_type, int(prepared["entity_id"]))
            self._access_policy.require(
                "delete",
                project_ref=target_project,
                project_identifier=request_project or default_project_identifier,
                entity_type=entity_type,
            )
        else:
            self._access_policy.require(
                "batch",
                project_ref=project_ref,
                project_identifier=request_project or default_project_identifier,
                entity_type=entity_type,
            )

        return prepared

    # --- Schema Operations ---

    def get_schema(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve the schema for one or all entity types.

        Args:
            entity_type: Specific entity type, or None for all.

        Returns:
            Schema dictionary.
        """
        cache_key = entity_type or "__all__"
        cached = self._schema_cache.get(cache_key)
        if cached is not None:
            return cached

        for attempt in range(self.MAX_RETRIES):
            try:
                if entity_type:
                    schema = self.sg.schema_field_read(entity_type)
                else:
                    schema = self.sg.schema_read()
                self._schema_cache.set(cache_key, schema)
                return schema
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(f"Schema read failed for {entity_type or 'all'}: {e}") from e
        return {}

    def get_entity_types(self) -> List[str]:
        """List all available entity types from schema."""
        schema = self.get_schema()
        return sorted(schema.keys()) if schema else []

    # --- Context Manager ---

    def __enter__(self) -> "ShotGridClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def _has_project_filter(filters: List[Any]) -> bool:
    for item in filters or []:
        if isinstance(item, (list, tuple)) and item and item[0] == "project":
            return True
    return False


def _env_int(name: str) -> Optional[int]:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _format_server_version(value: Any) -> Optional[str]:
    """Normalize ShotGrid API version payloads to a string."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return ".".join(str(part) for part in value)
    return str(value)
