"""Tests for project-scoped CLI client operations."""

from __future__ import annotations

import json

import pytest

from dcc_mcp_fpt.access import PermissionLevel, ShotGridAccessPolicy
from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.exceptions import ShotGridPermissionError


def _input(call):
    return json.loads(call[call.index("--input") + 1])


def make_client(fpt_runner, level=PermissionLevel.ADMIN):
    return ShotGridClient(
        "https://test.shotgrid.autodesk.com",
        "test_script",
        "test_key",
        runner=fpt_runner,
        access_policy=ShotGridAccessPolicy(default_level=level),
        default_project="demo_project",
    )


def test_find_adds_default_project_filter(fpt_runner):
    make_client(fpt_runner).find("Shot", [["code", "is", "SH001"]], fields=["id", "code"])

    assert ["project", "is", {"type": "Project", "id": 192}] in _input(fpt_runner.calls[-1])["search"]["filters"]


def test_create_injects_default_project(fpt_runner):
    make_client(fpt_runner).create("Shot", {"code": "SH001"})

    assert _input(fpt_runner.calls[-1])["project"] == {"type": "Project", "id": 192}


def test_resolve_project_by_id_uses_reference_without_remote_lookup(fpt_runner):
    client = make_client(fpt_runner)

    project = client.resolve_project(project_id=192)

    assert project.id == 192
    assert fpt_runner.calls == []


def test_write_permission_blocks_delete(fpt_runner):
    client = make_client(fpt_runner, level=PermissionLevel.WRITE)

    with pytest.raises(ShotGridPermissionError, match="requires admin"):
        client.delete("Shot", 1)

    assert not any(call[1:3] == ["entity", "delete"] for call in fpt_runner.calls)


def test_batch_keeps_request_order(fpt_runner):
    results = make_client(fpt_runner).batch(
        [
            {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH001"}},
            {"request_type": "update", "entity_type": "Shot", "entity_id": 1, "data": {"code": "SH001_MOD"}},
        ]
    )

    commands = [call[1:3] for call in fpt_runner.calls if call[1:3] in (["entity", "create"], ["entity", "update"])]
    assert commands == [["entity", "create"], ["entity", "update"]]
    assert len(results) == 2
