"""Tests for project-scoped ShotGrid access policy."""

from __future__ import annotations

import pytest

from dcc_mcp_fpt.access import (
    PermissionLevel,
    ProjectRef,
    ShotGridAccessPolicy,
    parse_permission_level,
)
from dcc_mcp_fpt.exceptions import ShotGridPermissionError


def test_read_policy_allows_find_but_blocks_create():
    policy = ShotGridAccessPolicy(default_level=PermissionLevel.READ)
    project = ProjectRef(id=192, name="demo_project")

    policy.require("find", project_ref=project, entity_type="Shot")

    with pytest.raises(ShotGridPermissionError, match="requires write"):
        policy.require("create", project_ref=project, entity_type="Shot")


def test_project_permissions_act_as_allowlist():
    policy = ShotGridAccessPolicy(
        default_level=PermissionLevel.ADMIN,
        project_levels={"demo_project": PermissionLevel.WRITE},
    )

    policy.require(
        "update",
        project_ref=ProjectRef(id=192, name="demo_project"),
        entity_type="Shot",
    )

    with pytest.raises(ShotGridPermissionError, match="does not allow"):
        policy.require(
            "find",
            project_ref=ProjectRef(id=999, name="other-project"),
            entity_type="Shot",
        )


def test_project_permission_level_caps_delete():
    policy = ShotGridAccessPolicy(
        default_level=PermissionLevel.ADMIN,
        project_levels={"id:192": PermissionLevel.WRITE},
    )

    with pytest.raises(ShotGridPermissionError, match="requires admin"):
        policy.require("delete", project_ref=ProjectRef(id=192), entity_type="Shot")


def test_read_only_overrides_write_level():
    policy = ShotGridAccessPolicy(default_level=PermissionLevel.ADMIN, read_only=True)

    with pytest.raises(ShotGridPermissionError, match="read-only"):
        policy.require("update", project_ref=ProjectRef(id=192), entity_type="Shot")


def test_merge_min_caps_permission_level():
    base = ShotGridAccessPolicy(default_level=PermissionLevel.ADMIN)
    request = ShotGridAccessPolicy(default_level=PermissionLevel.READ)

    merged = base.merge_min(request)

    assert merged.default_level == PermissionLevel.READ
    with pytest.raises(ShotGridPermissionError, match="requires write"):
        merged.require("create", project_ref=ProjectRef(id=192), entity_type="Shot")


def test_merge_min_intersects_project_allowlists():
    base = ShotGridAccessPolicy(
        default_level=PermissionLevel.ADMIN,
        project_levels={"demo": PermissionLevel.ADMIN, "other": PermissionLevel.ADMIN},
    )
    request = ShotGridAccessPolicy(
        default_level=PermissionLevel.WRITE,
        project_levels={"demo": PermissionLevel.READ},
    )

    merged = base.merge_min(request)

    assert merged.project_levels == {"demo": PermissionLevel.READ}
    with pytest.raises(ShotGridPermissionError, match="does not allow"):
        merged.require("find", project_ref=ProjectRef(id=2, name="other"), entity_type="Shot")


# --- from_mapping tests ---


def test_from_mapping_with_permission_level():
    """from_mapping resolves permission_level as default_level."""
    policy = ShotGridAccessPolicy.from_mapping({"permission_level": "read"})
    assert policy.default_level == PermissionLevel.READ


def test_from_mapping_with_permission_hint():
    """from_mapping resolves permission_hint as default_level fallback."""
    policy = ShotGridAccessPolicy.from_mapping({"permission_hint": "write"})
    assert policy.default_level == PermissionLevel.WRITE


def test_from_mapping_with_permission_key():
    """from_mapping resolves plain 'permission' key."""
    policy = ShotGridAccessPolicy.from_mapping({"permission": "admin"})
    assert policy.default_level == PermissionLevel.ADMIN


def test_from_mapping_with_project_permissions_dict():
    """from_mapping parses dict-format project_permissions."""
    policy = ShotGridAccessPolicy.from_mapping(
        {
            "permission_level": "admin",
            "project_permissions": {"demo": "read", "id:192": "write"},
        }
    )
    assert policy.default_level == PermissionLevel.ADMIN
    assert policy.project_levels["demo"] == PermissionLevel.READ
    assert policy.project_levels["id:192"] == PermissionLevel.WRITE


def test_from_mapping_with_project_permissions_list():
    """from_mapping parses list-format project_permissions."""
    policy = ShotGridAccessPolicy.from_mapping(
        {
            "project_permissions": [
                {"project": "demo", "level": "read"},
                {"key": "id:192", "permission": "write"},
            ]
        }
    )
    assert policy.project_levels["demo"] == PermissionLevel.READ
    assert policy.project_levels["id:192"] == PermissionLevel.WRITE


def test_from_mapping_with_read_only():
    """from_mapping parses read_only boolean."""
    policy = ShotGridAccessPolicy.from_mapping({"read_only": True})
    assert policy.read_only is True


def test_from_mapping_read_only_string():
    """from_mapping parses read_only from truthy string."""
    policy = ShotGridAccessPolicy.from_mapping({"read_only": "1"})
    assert policy.read_only is True


# --- parse_permission_level tests ---


def test_parse_permission_level_standard_values():
    """Standard permission level values are parsed correctly."""
    assert parse_permission_level("read", PermissionLevel.ADMIN) == PermissionLevel.READ
    assert parse_permission_level("write", PermissionLevel.ADMIN) == PermissionLevel.WRITE
    assert parse_permission_level("admin", PermissionLevel.READ) == PermissionLevel.ADMIN


def test_parse_permission_level_aliases():
    """Common aliases resolve to canonical levels."""
    assert parse_permission_level("readonly", PermissionLevel.ADMIN) == PermissionLevel.READ
    assert parse_permission_level("read-only", PermissionLevel.ADMIN) == PermissionLevel.READ
    assert parse_permission_level("ro", PermissionLevel.ADMIN) == PermissionLevel.READ
    assert parse_permission_level("rw", PermissionLevel.READ) == PermissionLevel.WRITE
    assert parse_permission_level("writer", PermissionLevel.READ) == PermissionLevel.WRITE
    assert parse_permission_level("owner", PermissionLevel.READ) == PermissionLevel.ADMIN
    assert parse_permission_level("delete", PermissionLevel.READ) == PermissionLevel.ADMIN
    assert parse_permission_level("full", PermissionLevel.READ) == PermissionLevel.ADMIN


def test_parse_permission_level_none_returns_default():
    """None input returns the provided default."""
    assert parse_permission_level(None, PermissionLevel.READ) == PermissionLevel.READ
    assert parse_permission_level(None, PermissionLevel.ADMIN) == PermissionLevel.ADMIN


def test_parse_permission_level_empty_string_returns_default():
    """Empty string returns the provided default."""
    assert parse_permission_level("", PermissionLevel.WRITE) == PermissionLevel.WRITE


def test_parse_permission_level_invalid_raises():
    """Invalid permission level raises ValueError."""
    with pytest.raises(ValueError, match="must be one of"):
        parse_permission_level("superadmin", PermissionLevel.READ)
