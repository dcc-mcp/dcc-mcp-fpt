"""Tests for project-scoped ShotGrid client operations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dcc_mcp_fpt.access import PermissionLevel, ShotGridAccessPolicy
from dcc_mcp_fpt.client import ShotGridClient
from dcc_mcp_fpt.exceptions import ShotGridPermissionError

PROJECT = {
    "id": 192,
    "type": "Project",
    "name": "demo_project",
    "tank_name": "demo_project",
}
PROJECT_REF = {"type": "Project", "id": 192}


def make_client(level=PermissionLevel.ADMIN):
    sg = MagicMock()
    sg.server_info = {"version": "8.0.0"}
    sg.find.return_value = [{"id": 1, "type": "Shot", "code": "SH001"}]
    sg.create.return_value = {"id": 1, "type": "Shot", "code": "SH001", "project": PROJECT_REF}
    sg.update.return_value = {"id": 1, "type": "Shot", "code": "SH001_MOD"}
    sg.delete.return_value = True
    sg.batch.return_value = [{"id": 1, "type": "Shot"}]

    def find_one(entity_type, filters, fields=None):
        if entity_type == "Project":
            return PROJECT
        if entity_type == "Shot" and filters == [["id", "is", 1]]:
            return {"id": 1, "type": "Shot", "project": PROJECT_REF}
        return None

    sg.find_one.side_effect = find_one
    client = ShotGridClient(
        "https://test.shotgrid.autodesk.com",
        "test_script",
        "test_key",
        access_policy=ShotGridAccessPolicy(default_level=level),
        default_project="demo_project",
    )
    client._sg = sg
    return client, sg


def test_find_adds_default_project_filter():
    client, sg = make_client()

    client.find("Shot", [["code", "is", "SH001"]], fields=["id", "code"])

    filters = sg.find.call_args.args[1]
    assert ["project", "is", PROJECT_REF] in filters


def test_find_does_not_project_scope_global_entities():
    client, sg = make_client()

    client.find("Project", [["name", "is", "demo_project"]])

    filters = sg.find.call_args.args[1]
    assert filters == [["name", "is", "demo_project"]]


def test_create_injects_default_project():
    client, sg = make_client()

    client.create("Shot", {"code": "SH001"})

    data = sg.create.call_args.args[1]
    assert data["project"] == PROJECT_REF


def test_write_permission_blocks_delete():
    client, sg = make_client(level=PermissionLevel.WRITE)

    with pytest.raises(ShotGridPermissionError, match="requires admin"):
        client.delete("Shot", 1)

    sg.delete.assert_not_called()


def test_batch_checks_each_request_and_injects_project():
    client, sg = make_client()

    client.batch(
        [
            {"request_type": "create", "entity_type": "Shot", "data": {"code": "SH001"}},
            {"request_type": "update", "entity_type": "Shot", "entity_id": 1, "data": {"code": "SH001_MOD"}},
        ]
    )

    requests = sg.batch.call_args.args[0]
    assert requests[0]["data"]["project"] == PROJECT_REF
    assert "project" not in requests[1]
