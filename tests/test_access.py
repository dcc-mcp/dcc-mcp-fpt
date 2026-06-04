"""Tests for project-scoped ShotGrid access policy."""

from __future__ import annotations

import pytest

from dcc_mcp_fpt.access import PermissionLevel, ProjectRef, ShotGridAccessPolicy
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
