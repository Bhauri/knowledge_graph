from __future__ import annotations

from uuid import uuid4

from app.graph_creater.edge_models import create_edge
from app.graph_creater.edge_repository import EdgeRepository


def test_upsert_edges_inserts_then_updates_same_key(duckdb_store) -> None:
    edge = create_edge(
        from_node_uuid=uuid4(),
        to_node_uuid=uuid4(),
        relationship="HAS_PSP",
        source_ref={"table": "psp", "parent_pk": 1, "child_pk": 2, "relationship_source": "parent_qeid"},
    )

    repo = EdgeRepository(duckdb_store)

    with duckdb_store.transaction():
        first = repo.upsert_edges([edge])
    with duckdb_store.transaction():
        second = repo.upsert_edges([edge])

    assert (first.inserted, first.updated) == (1, 0)
    assert (second.inserted, second.updated) == (0, 1)
    assert duckdb_store.count("graph_edges") == 1
