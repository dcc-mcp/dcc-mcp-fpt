"""Project-scoped access policy for ShotGrid operations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional

from dcc_mcp_fpt.exceptions import ShotGridPermissionError


class PermissionLevel(str, Enum):
    """Supported project permission levels."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


_LEVEL_RANK = {
    PermissionLevel.READ: 1,
    PermissionLevel.WRITE: 2,
    PermissionLevel.ADMIN: 3,
}

_OPERATION_LEVELS = {
    "find": PermissionLevel.READ,
    "find_one": PermissionLevel.READ,
    "schema": PermissionLevel.READ,
    "connection": PermissionLevel.READ,
    "create": PermissionLevel.WRITE,
    "update": PermissionLevel.WRITE,
    "batch": PermissionLevel.WRITE,
    "delete": PermissionLevel.ADMIN,
}


@dataclass(frozen=True)
class ProjectRef:
    """Resolved ShotGrid project identity."""

    id: int
    name: Optional[str] = None
    code: Optional[str] = None
    tank_name: Optional[str] = None

    def as_entity_ref(self) -> Dict[str, Any]:
        """Return a ShotGrid entity reference."""
        return {"type": "Project", "id": self.id}

    def policy_keys(self) -> Iterable[str]:
        """Return all stable keys that can match this project in policy config."""
        yield f"id:{self.id}"
        yield str(self.id)
        for value in (self.name, self.code, self.tank_name):
            if value:
                yield value


@dataclass(frozen=True)
class ShotGridAccessPolicy:
    """Declarative per-project permission policy.

    The policy is intentionally env-friendly so local testing can switch
    projects without editing code or committing credentials.
    """

    default_level: PermissionLevel = PermissionLevel.ADMIN
    project_levels: Mapping[str, PermissionLevel] = field(default_factory=dict)
    read_only: bool = False

    @classmethod
    def from_env(cls) -> "ShotGridAccessPolicy":
        """Build a policy from ShotGrid environment variables."""
        return cls(
            default_level=_parse_level(os.environ.get("SHOTGRID_PERMISSION_LEVEL"), PermissionLevel.ADMIN),
            project_levels=_parse_project_permissions(os.environ.get("SHOTGRID_PROJECT_PERMISSIONS", "")),
            read_only=_env_truthy(os.environ.get("SHOTGRID_READ_ONLY")),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShotGridAccessPolicy":
        """Build a policy from a profile/request mapping."""
        permission = value.get("permission_level") or value.get("permission_hint") or value.get("permission")
        project_permissions = value.get("project_permissions")
        if isinstance(project_permissions, (dict, list)):
            raw_project_permissions = json.dumps(project_permissions)
        else:
            raw_project_permissions = str(project_permissions or "")
        return cls(
            default_level=_parse_level(str(permission) if permission else None, PermissionLevel.ADMIN),
            project_levels=_parse_project_permissions(raw_project_permissions),
            read_only=_mapping_truthy(value.get("read_only")),
        )

    def merge_min(self, other: "ShotGridAccessPolicy") -> "ShotGridAccessPolicy":
        """Return a policy capped by both policies.

        Empty project-level mappings mean "no project allowlist". When both
        sides define allowlists, only projects present in both remain allowed.
        """
        project_levels: Dict[str, PermissionLevel]
        if self.project_levels and other.project_levels:
            shared = set(self.project_levels).intersection(other.project_levels)
            project_levels = {
                key: min(self.project_levels[key], other.project_levels[key], key=_LEVEL_RANK.get) for key in shared
            }
        elif self.project_levels:
            project_levels = dict(self.project_levels)
        elif other.project_levels:
            project_levels = dict(other.project_levels)
        else:
            project_levels = {}

        return ShotGridAccessPolicy(
            default_level=min(self.default_level, other.default_level, key=_LEVEL_RANK.get),
            project_levels=project_levels,
            read_only=self.read_only or other.read_only,
        )

    def require(
        self,
        operation: str,
        *,
        project_ref: Optional[ProjectRef] = None,
        project_identifier: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> None:
        """Raise if an operation is not allowed for the project context."""
        required = _OPERATION_LEVELS.get(operation, PermissionLevel.WRITE)
        effective_level = self._effective_level(project_ref, project_identifier)

        if self.read_only and _LEVEL_RANK[required] > _LEVEL_RANK[PermissionLevel.READ]:
            raise ShotGridPermissionError(f"ShotGrid policy is read-only; {operation} is not allowed")

        if _LEVEL_RANK[effective_level] < _LEVEL_RANK[required]:
            target = _project_label(project_ref, project_identifier)
            detail = f" for project {target}" if target else ""
            entity = f" on {entity_type}" if entity_type else ""
            raise ShotGridPermissionError(
                f"ShotGrid {operation}{entity}{detail} requires {required.value} permission; "
                f"configured level is {effective_level.value}"
            )

    def _effective_level(
        self,
        project_ref: Optional[ProjectRef],
        project_identifier: Optional[str],
    ) -> PermissionLevel:
        if not self.project_levels:
            return self.default_level

        keys = []
        if project_ref is not None:
            keys.extend(project_ref.policy_keys())
        if project_identifier:
            keys.append(project_identifier)

        for key in keys:
            normalized = _normalize_key(key)
            level = self.project_levels.get(normalized)
            if level is not None:
                return min(level, self.default_level, key=_LEVEL_RANK.get)

        target = _project_label(project_ref, project_identifier) or "unscoped operation"
        raise ShotGridPermissionError(f"ShotGrid project policy does not allow {target}")


def _parse_project_permissions(raw: str) -> Dict[str, PermissionLevel]:
    """Parse JSON or CSV project permission config."""
    if not raw.strip():
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    items = []
    if isinstance(parsed, dict):
        items = list(parsed.items())
    elif isinstance(parsed, list):
        for entry in parsed:
            if isinstance(entry, dict):
                project = entry.get("project") or entry.get("key") or entry.get("id")
                level = entry.get("level") or entry.get("permission")
                if project and level:
                    items.append((str(project), str(level)))
    else:
        for part in raw.split(","):
            if not part.strip():
                continue
            key, sep, value = part.partition("=")
            if sep:
                items.append((key.strip(), value.strip()))

    return {
        _normalize_key(str(project)): _parse_level(str(level), PermissionLevel.READ)
        for project, level in items
        if str(project).strip()
    }


def _parse_level(raw: Optional[str], default: PermissionLevel) -> PermissionLevel:
    if not raw:
        return default
    value = raw.strip().lower()
    aliases = {
        "readonly": "read",
        "read-only": "read",
        "ro": "read",
        "rw": "write",
        "write": "write",
        "writer": "write",
        "owner": "admin",
        "delete": "admin",
        "full": "admin",
    }
    value = aliases.get(value, value)
    try:
        return PermissionLevel(value)
    except ValueError as exc:
        raise ValueError("SHOTGRID_PERMISSION_LEVEL must be one of: read, write, admin") from exc


def parse_permission_level(raw: Optional[str], default: PermissionLevel) -> PermissionLevel:
    """Parse a public permission level string."""
    return _parse_level(raw, default)


def _normalize_key(value: str) -> str:
    return value.strip().lower()


def _env_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mapping_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _project_label(
    project_ref: Optional[ProjectRef],
    project_identifier: Optional[str],
) -> Optional[str]:
    if project_ref is not None:
        return project_ref.name or project_ref.code or project_ref.tank_name or f"id:{project_ref.id}"
    return project_identifier
