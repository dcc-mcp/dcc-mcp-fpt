"""Pydantic models for ShotGrid entities and responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ShotGridEntity(BaseModel):
    """Represents a generic ShotGrid entity."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Entity type (e.g., 'Shot', 'Asset', 'Task')")
    id: int = Field(..., description="Entity ID")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Entity field values")


class ShotGridFindRequest(BaseModel):
    """Parameters for a ShotGrid find query."""

    entity_type: str = Field(..., description="Entity type to query")
    filters: List[Any] = Field(default_factory=list, description="ShotGrid filter expressions")
    fields: Optional[List[str]] = Field(default=None, description="Fields to retrieve")
    order: Optional[List[Dict[str, str]]] = Field(default=None, description="Sort order")
    limit: int = Field(default=500, ge=1, le=5000, description="Maximum results")
    retired_only: bool = Field(default=False, description="Include retired entities")
    page: int = Field(default=1, ge=1, description="Page number for pagination")


class ShotGridFindResponse(BaseModel):
    """Response from a ShotGrid find query."""

    items: List[Dict[str, Any]] = Field(default_factory=list, description="Found entities")
    total_count: int = Field(default=0, description="Total matching count")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=500, description="Page size")


class ShotGridCreateRequest(BaseModel):
    """Parameters for creating a ShotGrid entity."""

    entity_type: str = Field(..., description="Entity type to create")
    data: Dict[str, Any] = Field(..., description="Field values for new entity")


class ShotGridUpdateRequest(BaseModel):
    """Parameters for updating a ShotGrid entity."""

    entity_type: str = Field(..., description="Entity type to update")
    entity_id: int = Field(..., description="Entity ID to update")
    data: Dict[str, Any] = Field(..., description="Field values to update")


class ShotGridBatchRequest(BaseModel):
    """Parameters for batch operations."""

    requests: List[Dict[str, Any]] = Field(..., description="Batch operation requests")


class ShotGridBatchItem(BaseModel):
    """A single item in a batch request."""

    request_type: str = Field(..., description="Operation type: create, update, delete")
    entity_type: str = Field(..., description="Entity type")
    entity_id: Optional[int] = Field(default=None, description="Entity ID (for update/delete)")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Field values (for create/update)")


class ShotGridSchemaField(BaseModel):
    """Represents a ShotGrid schema field definition."""

    name: str = Field(..., description="Field name")
    data_type: str = Field(default="text", description="Field data type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Field properties")


class ShotGridSchemaEntity(BaseModel):
    """Represents a ShotGrid entity schema."""

    name: str = Field(..., description="Entity type name")
    fields: Dict[str, ShotGridSchemaField] = Field(default_factory=dict, description="Entity fields")


class ShotGridNote(BaseModel):
    """Represents a ShotGrid note."""

    id: Optional[int] = Field(default=None, description="Note ID")
    subject: Optional[str] = Field(default=None, description="Note subject")
    content: str = Field(..., description="Note body content")
    link_entity_type: Optional[str] = Field(default=None, description="Linked entity type")
    link_entity_id: Optional[int] = Field(default=None, description="Linked entity ID")
    user: Optional[Dict[str, Any]] = Field(default=None, description="Note author")


class ShotGridConnectionInfo(BaseModel):
    """Connection information for the current ShotGrid session."""

    url: str = Field(..., description="ShotGrid server URL")
    script_name: str = Field(..., description="Script/API user name")
    authenticated: bool = Field(default=False, description="Whether authentication succeeded")
    server_version: Optional[str] = Field(default=None, description="ShotGrid server version")
