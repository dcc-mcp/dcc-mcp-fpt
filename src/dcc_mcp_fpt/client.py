"""ShotGrid API client with connection pooling and retry support."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from shotgun_api3 import Shotgun

from dcc_mcp_fpt.connection_pool import ConnectionPool
from dcc_mcp_fpt.exceptions import (
    ShotGridAuthenticationError,
    ShotGridConnectionError,
    ShotGridEntityNotFoundError,
    ShotGridQueryError,
)
from dcc_mcp_fpt.models import ShotGridConnectionInfo
from dcc_mcp_fpt.schema_cache import SchemaCache

logger = logging.getLogger(__name__)


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
        proxy: Optional[str] = None,
    ):
        """Initialize the ShotGrid client.

        Args:
            url: ShotGrid server URL (e.g., https://mysite.shotgrid.autodesk.com).
            script_name: Script/API user name.
            api_key: Script/API user key.
            pool: Optional shared connection pool.
            schema_cache: Optional shared schema cache.
            proxy: Optional HTTP proxy URL.
        """
        self._url = url.rstrip("/")
        self._script_name = script_name
        self._api_key = api_key
        self._proxy = proxy
        self._pool = pool or ConnectionPool()
        self._schema_cache = schema_cache or SchemaCache()
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
            self._sg = Shotgun(
                self._url,
                self._script_name,
                self._api_key,
                http_proxy=self._proxy,
            )
            # Verify connection by fetching server info
            self._sg.server_info
            logger.info("Connected to ShotGrid successfully.")
        except Exception as e:
            raise ShotGridConnectionError(
                f"Failed to connect to ShotGrid at {self._url}: {e}"
            ) from e

    def close(self) -> None:
        """Close the ShotGrid connection."""
        if self._sg is not None:
            try:
                self._sg.close()
            except Exception:
                pass
            self._sg = None

    def get_connection_info(self) -> ShotGridConnectionInfo:
        """Retrieve connection metadata for diagnostics."""
        try:
            info = self.sg.server_info
            return ShotGridConnectionInfo(
                url=self._url,
                script_name=self._script_name,
                authenticated=True,
                server_version=info.get("version"),
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

        Returns:
            List of entity dictionaries.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                results = self.sg.find(
                    entity_type,
                    filters,
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
                    raise ShotGridQueryError(
                        f"ShotGrid find failed for {entity_type}: {e}"
                    ) from e
        return []

    def find_one(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find a single entity or return None.

        Args:
            entity_type: The entity type to query.
            filters: ShotGrid filter expressions.
            fields: Fields to retrieve.

        Returns:
            Entity dictionary or None if not found.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.sg.find_one(entity_type, filters, fields=fields)
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "ShotGrid find_one attempt %d failed: %s, retrying...",
                        attempt + 1,
                        e,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise ShotGridQueryError(
                        f"ShotGrid find_one failed for {entity_type}: {e}"
                    ) from e
        return None

    # --- CRUD Operations ---

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ShotGrid entity.

        Args:
            entity_type: Entity type to create.
            data: Field values for the new entity.

        Returns:
            Created entity dictionary.
        """
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
                    raise ShotGridQueryError(
                        f"ShotGrid create failed for {entity_type}: {e}"
                    ) from e
        return {}

    def update(self, entity_type: str, entity_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing ShotGrid entity.

        Args:
            entity_type: Entity type to update.
            entity_id: ID of the entity to update.
            data: Field values to update.

        Returns:
            Updated entity dictionary.
        """
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
                    raise ShotGridQueryError(
                        f"ShotGrid update failed for {entity_type} id={entity_id}: {e}"
                    ) from e
        return {}

    def delete(self, entity_type: str, entity_id: int) -> bool:
        """Delete a ShotGrid entity.

        Args:
            entity_type: Entity type to delete.
            entity_id: ID of the entity to delete.

        Returns:
            True if deleted successfully.
        """
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
                    raise ShotGridQueryError(
                        f"ShotGrid delete failed for {entity_type} id={entity_id}: {e}"
                    ) from e
        return False

    # --- Batch Operations ---

    def batch(self, requests: List[Dict[str, Any]]) -> List[Any]:
        """Execute batch operations.

        Args:
            requests: List of batch request dicts with keys:
                request_type: 'create', 'update', or 'delete'
                entity_type: Entity type
                entity_id: Entity ID (for update/delete)
                data: Field values (for create/update)

        Returns:
            List of results matching request order.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                results = self.sg.batch(requests)
                logger.info("Batch: %d requests completed", len(requests))
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
                    raise ShotGridQueryError(
                        f"Schema read failed for {entity_type or 'all'}: {e}"
                    ) from e
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
