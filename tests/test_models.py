"""Tests for Pydantic models."""

from __future__ import annotations

from dcc_mcp_fpt.models import (
    ShotGridBatchItem,
    ShotGridConnectionInfo,
    ShotGridCreateRequest,
    ShotGridEntity,
    ShotGridFindRequest,
    ShotGridFindResponse,
    ShotGridNote,
    ShotGridUpdateRequest,
)


class TestModels:
    """Tests for ShotGrid data models."""

    def test_shotgrid_entity(self):
        entity = ShotGridEntity(type="Shot", id=1, attributes={"code": "SH001"})
        assert entity.type == "Shot"
        assert entity.id == 1

    def test_find_request(self):
        req = ShotGridFindRequest(
            entity_type="Shot",
            filters=[["sg_status", "is", "ip"]],
            fields=["code", "sg_status"],
            limit=100,
        )
        assert req.entity_type == "Shot"
        assert req.limit == 100

    def test_find_request_defaults(self):
        req = ShotGridFindRequest(entity_type="Shot")
        assert req.limit == 500
        assert req.page == 1
        assert req.filters == []

    def test_find_response(self):
        resp = ShotGridFindResponse(
            items=[{"id": 1, "code": "SH001"}],
            total_count=1,
            page=1,
            page_size=500,
        )
        assert resp.total_count == 1

    def test_create_request(self):
        req = ShotGridCreateRequest(
            entity_type="Shot",
            data={"code": "SH001", "project": {"type": "Project", "id": 1}},
        )
        assert req.entity_type == "Shot"
        assert req.data["code"] == "SH001"

    def test_update_request(self):
        req = ShotGridUpdateRequest(
            entity_type="Shot",
            entity_id=42,
            data={"sg_status": "fin"},
        )
        assert req.entity_id == 42

    def test_batch_item_create(self):
        item = ShotGridBatchItem(
            request_type="create",
            entity_type="Shot",
            data={"code": "SH001"},
        )
        assert item.request_type == "create"

    def test_batch_item_delete(self):
        item = ShotGridBatchItem(
            request_type="delete",
            entity_type="Shot",
            entity_id=1,
        )
        assert item.entity_id == 1

    def test_note(self):
        note = ShotGridNote(
            content="<p>Looks good!</p>",
            subject="Review",
            link_entity_type="Shot",
            link_entity_id=42,
        )
        assert note.subject == "Review"

    def test_connection_info(self):
        info = ShotGridConnectionInfo(
            url="https://test.shotgrid.autodesk.com",
            script_name="test_script",
            authenticated=True,
            server_version="8.0.0",
        )
        assert info.authenticated is True
        assert info.server_version == "8.0.0"
