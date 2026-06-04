"""Utility helpers for the ShotGrid adapter."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple


def get_shotgrid_env() -> Tuple[str, str, str]:
    """Read ShotGrid connection parameters from environment variables.

    Returns:
        Tuple of (url, script_name, api_key).

    Raises:
        ValueError: If any required variable is missing.
    """
    url = os.environ.get("SHOTGRID_URL", "")
    script_name = os.environ.get("SHOTGRID_SCRIPT_NAME", "")
    api_key = os.environ.get("SHOTGRID_SCRIPT_KEY", "")

    if not all([url, script_name, api_key]):
        missing = []
        if not url:
            missing.append("SHOTGRID_URL")
        if not script_name:
            missing.append("SHOTGRID_SCRIPT_NAME")
        if not api_key:
            missing.append("SHOTGRID_SCRIPT_KEY")
        raise ValueError(
            f"Missing ShotGrid environment variables: {', '.join(missing)}. "
            "Set SHOTGRID_URL, SHOTGRID_SCRIPT_NAME, and SHOTGRID_SCRIPT_KEY."
        )

    return url, script_name, api_key


def parse_filters(filter_str: str) -> List[Any]:
    """Parse a simple filter string into ShotGrid filter format.

    Supports basic patterns like:
        "code:is:shot001"   → [["code", "is", "shot001"]]
        "sg_status:is_not:c" → [["sg_status", "is_not", "c"]]

    Args:
        filter_str: Filter expression string.

    Returns:
        ShotGrid-compatible filter list.
    """
    if not filter_str:
        return []

    filters = []
    for part in filter_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            segments = part.split(":")
            if len(segments) >= 3:
                field = segments[0].strip()
                operator = segments[1].strip()
                value = ":".join(segments[2:]).strip()
                filters.append([field, operator, value])
    return filters


def build_filters(
    entity_type: Optional[str] = None,
    project_id: Optional[int] = None,
    conditions: Optional[List[Any]] = None,
) -> List[Any]:
    """Build a composite ShotGrid filter list.

    Args:
        entity_type: Entity type (used for project filter if applicable).
        project_id: Project ID to filter by.
        conditions: Additional filter conditions.

    Returns:
        Combined filter list.
    """
    filters: List[Any] = []

    if project_id is not None:
        # Most entities use project field
        filters.append(["project", "is", {"type": "Project", "id": project_id}])

    if conditions:
        filters.extend(conditions)

    return filters


def to_human_readable(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ShotGrid entity dict to a more agent-friendly format.

    Resolves entity references to name/id pairs and handles
    multi-entity fields.

    Args:
        entity: Raw ShotGrid entity dictionary.

    Returns:
        Simplified entity dictionary.
    """
    result: Dict[str, Any] = {}
    for key, value in entity.items():
        if isinstance(value, dict) and "type" in value and "id" in value:
            # Entity reference → simplified
            result[key] = {
                "id": value["id"],
                "type": value["type"],
                "name": value.get("name", str(value["id"])),
            }
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Multi-entity field → list of simplified refs
            result[key] = [
                {"id": item.get("id"), "type": item.get("type"), "name": item.get("name", str(item.get("id")))}
                for item in value
                if isinstance(item, dict)
            ]
        else:
            result[key] = value
    return result
