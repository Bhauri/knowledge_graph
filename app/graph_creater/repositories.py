from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow as pa

from app.storage.duckdb_store import DuckDBStore, dump_json

from .models import GraphNode


SOURCE_TABLES = (
    "qe",
    "psp",
    "capa",
    "containment_actions",
    "batch_containment_details",
    "qe_events",
    "initial_evaluations",
)


def fetch_source_rows(store: DuckDBStore, table_name: str) -> list[Mapping[str, Any]]:
    if table_name not in SOURCE_TABLES:
        raise ValueError(f"Unsupported source table: {table_name}")

    return store.fetch_all(f"SELECT * FROM dbo.{table_name}")


NODE_STAGE_NAME = "staged_nodes"

# One set-based statement per batch instead of one executemany call per row.
NODE_UPSERT_FROM_STAGE_SQL = f"""
    INSERT INTO graph_nodes (
        node_uuid, node_type, business_key, display_name,
        source_refs, properties, embedding_chunk_id, created_at, updated_at
    )
    SELECT
        CAST(s.node_uuid AS UUID), s.node_type, s.business_key, s.display_name,
        CAST(s.source_refs AS JSON), CAST(s.properties AS JSON), CAST(s.embedding_chunk_id AS UUID),
        s.created_at, s.updated_at
    FROM {NODE_STAGE_NAME} s
    ON CONFLICT (node_type, business_key) DO UPDATE SET
        display_name = excluded.display_name,
        source_refs = excluded.source_refs,
        properties = excluded.properties,
        embedding_chunk_id = excluded.embedding_chunk_id,
        updated_at = now()
"""


def _node_table(nodes: Sequence[GraphNode]) -> pa.Table:
    """Build an Arrow table for one batch of nodes (keys are unique per batch)."""
    timestamp_type = pa.timestamp("us", tz="UTC")
    return pa.table(
        {
            "node_uuid": pa.array([str(node.node_uuid) for node in nodes], pa.string()),
            "node_type": pa.array([node.node_type for node in nodes], pa.string()),
            "business_key": pa.array([node.business_key for node in nodes], pa.string()),
            "display_name": pa.array([node.display_name for node in nodes], pa.string()),
            "source_refs": pa.array([dump_json(node.source_refs) for node in nodes], pa.string()),
            "properties": pa.array([dump_json(node.properties) for node in nodes], pa.string()),
            "embedding_chunk_id": pa.array(
                [None if node.embedding_chunk_id is None else str(node.embedding_chunk_id) for node in nodes],
                pa.string(),
            ),
            "created_at": pa.array([node.created_at for node in nodes], timestamp_type),
            "updated_at": pa.array([node.updated_at for node in nodes], timestamp_type),
        }
    )


def upsert_nodes(store: DuckDBStore, nodes: Sequence[GraphNode]) -> None:
    if not nodes:
        return

    # Keep the last node per key so the single INSERT never touches the same row twice.
    unique: dict[tuple[str, str], GraphNode] = {}
    for node in nodes:
        unique[(node.node_type, node.business_key)] = node

    with store.staged_table(NODE_STAGE_NAME, _node_table(list(unique.values()))):
        store.execute(NODE_UPSERT_FROM_STAGE_SQL)
