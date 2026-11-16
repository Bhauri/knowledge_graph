from uuid import uuid4

from app.chunk_sync.node_lookup_service import NodeLookupService


class DummyStore:
    def __init__(self, rows):
        self._rows = rows

    def fetch_all(self, _sql, _params=None):
        return self._rows



def test_node_lookup_service_loads_cache_and_resolves_uuid() -> None:
    node_uuid = uuid4()
    service = NodeLookupService(
        DummyStore(
            [
                {
                    "source_table": "psp",
                    "source_pk": "101",
                    "node_uuid": node_uuid,
                }
            ]
        )
    )

    service.load_cache()

    assert service.get_node_uuid("psp", "101") == node_uuid
    assert service.get_node_uuid("psp", "999") is None
    assert service.missing_nodes == 1
