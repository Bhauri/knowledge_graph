from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.graph_creater.models import create_node
from app.graph_creater.node_lookup_updater import NodeLookupUpdater
from app.graph_creater.repositories import upsert_nodes


def test_initialize_is_idempotent_and_tables_start_empty(duckdb_store) -> None:
    duckdb_store.initialize()

    for table in ("graph_nodes", "graph_edges", "node_lookup", "vector_chunks"):
        assert duckdb_store.count(table) == 0


def test_reset_tables_clears_rows(duckdb_store) -> None:
    node = create_node(
        node_type="Site",
        business_key="Singapore",
        display_name="Singapore",
        source_ref={"table": "qe", "column": "initiating_site", "primary_key": 1},
        properties={},
    )
    upsert_nodes(duckdb_store, [node])
    assert duckdb_store.count("graph_nodes") == 1

    duckdb_store.reset_tables()

    assert duckdb_store.count("graph_nodes") == 0


def test_refresh_lookup_maps_primary_source_refs(duckdb_store) -> None:
    node = create_node(
        node_type="QualityEvent",
        business_key="qe-1",
        display_name="QE 1",
        source_ref={"table": "qe", "column": "qe_id", "primary_key": 1},
        properties={},
    )
    upsert_nodes(duckdb_store, [node])

    count = NodeLookupUpdater(duckdb_store, logger=logging.getLogger("test")).refresh_lookup()

    assert count == 1
    rows = duckdb_store.fetch_all("SELECT source_table, source_pk, node_uuid FROM node_lookup")
    assert rows[0]["source_table"] == "qe"
    assert rows[0]["source_pk"] == "1"
    assert rows[0]["node_uuid"] == node.node_uuid


def test_transaction_rolls_back_on_error(duckdb_store) -> None:
    with pytest.raises(RuntimeError):
        with duckdb_store.transaction():
            duckdb_store.execute(
                "INSERT INTO node_lookup (source_table, source_pk, node_uuid) VALUES (?, ?, ?)",
                ["qe", "1", uuid4()],
            )
            raise RuntimeError("boom")

    assert duckdb_store.count("node_lookup") == 0
