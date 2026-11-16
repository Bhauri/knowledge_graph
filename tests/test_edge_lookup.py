from __future__ import annotations

from uuid import uuid4

from app.graph_creater.node_lookup_service import NodeLookupService


class DummyStore:
    def fetch_all(self, _sql, _params=None):
        return []


def test_lookup_node_normalizes_business_key() -> None:
    service = NodeLookupService(DummyStore())
    expected_uuid = uuid4()
    service._cache = {("Person", "john-smith"): expected_uuid}

    node_uuid = service.lookup_node("Person", "  JOHN SMITH  ")

    assert node_uuid == expected_uuid


def test_lookup_node_missing_increments_counter() -> None:
    service = NodeLookupService(DummyStore())
    service._cache = {}

    node_uuid = service.lookup_node("Site", "Singapore")

    assert node_uuid is None
    assert service.missing_nodes == 1
