from __future__ import annotations

from app.graph_creater.models import create_node
from app.graph_creater.repositories import upsert_nodes


def test_upsert_nodes_inserts_then_updates_same_business_key(duckdb_store) -> None:
    first = create_node(
        node_type="Person",
        business_key="John Smith",
        display_name="John Smith",
        source_ref={"table": "qe", "column": "created_by", "primary_key": 1},
        properties={"qe_id": 1},
    )
    second = create_node(
        node_type="Person",
        business_key="John Smith",
        display_name="John Q Smith",
        source_ref={"table": "qe", "column": "created_by", "primary_key": 1},
        properties={"qe_id": 1},
    )

    upsert_nodes(duckdb_store, [first])
    upsert_nodes(duckdb_store, [second])

    assert duckdb_store.count("graph_nodes") == 1
    rows = duckdb_store.fetch_all("SELECT display_name FROM graph_nodes")
    assert rows[0]["display_name"] == "John Q Smith"
