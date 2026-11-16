from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pyarrow as pa

from app.storage.duckdb_store import DuckDBStore, dump_json

from .edge_models import GraphEdge


SOURCE_TABLES = (
    "qe",
    "psp",
    "capa",
    "containment_actions",
    "batch_containment_details",
    "qe_events",
    "initial_evaluations",
)

EDGE_STAGE_NAME = "staged_edges"

# Counts staged edges that already exist, so inserted/updated can be reported per batch.
EDGE_EXISTING_COUNT_SQL = f"""
    SELECT COUNT(*) AS existing_count FROM {EDGE_STAGE_NAME} s
    JOIN graph_edges g
      ON g.from_node_uuid = CAST(s.from_node_uuid AS UUID)
     AND g.to_node_uuid = CAST(s.to_node_uuid AS UUID)
     AND g.relationship = s.relationship
"""

# One set-based statement per batch instead of one executemany call per row.
EDGE_UPSERT_FROM_STAGE_SQL = f"""
    INSERT INTO graph_edges (
        edge_uuid, from_node_uuid, to_node_uuid, relationship,
        source_refs, properties, created_at
    )
    SELECT
        CAST(s.edge_uuid AS UUID), CAST(s.from_node_uuid AS UUID), CAST(s.to_node_uuid AS UUID),
        s.relationship, CAST(s.source_refs AS JSON), CAST(s.properties AS JSON), s.created_at
    FROM {EDGE_STAGE_NAME} s
    ON CONFLICT (from_node_uuid, to_node_uuid, relationship) DO UPDATE SET
        source_refs = excluded.source_refs,
        properties = excluded.properties
"""


@dataclass(slots=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0


def _edge_key(from_node_uuid: Any, to_node_uuid: Any, relationship: str) -> tuple[str, str, str]:
    return (str(from_node_uuid), str(to_node_uuid), relationship)


def _edge_table(edges: Sequence[GraphEdge]) -> pa.Table:
    """Build an Arrow table for one batch of edges (keys are unique per batch)."""
    return pa.table(
        {
            "edge_uuid": pa.array([str(edge.edge_uuid) for edge in edges], pa.string()),
            "from_node_uuid": pa.array([str(edge.from_node_uuid) for edge in edges], pa.string()),
            "to_node_uuid": pa.array([str(edge.to_node_uuid) for edge in edges], pa.string()),
            "relationship": pa.array([edge.relationship for edge in edges], pa.string()),
            "source_refs": pa.array([dump_json(edge.source_refs) for edge in edges], pa.string()),
            "properties": pa.array([dump_json(edge.properties) for edge in edges], pa.string()),
            "created_at": pa.array([edge.created_at for edge in edges], pa.timestamp("us", tz="UTC")),
        }
    )


class EdgeRepository:
    """Reads source rows and writes graph edges, both through DuckDB."""

    def __init__(self, store: DuckDBStore) -> None:
        self.store = store

    def fetch_source_rows(self, table_name: str) -> list[Mapping[str, Any]]:
        if table_name not in SOURCE_TABLES:
            raise ValueError(f"Unsupported source table: {table_name}")

        return self.store.fetch_all(f"SELECT * FROM dbo.{table_name}")

    def upsert_edges(self, edges: Sequence[GraphEdge]) -> UpsertResult:
        """Insert or update edges. Must run inside a store transaction opened by the caller."""
        if not edges:
            return UpsertResult()

        # Keep the last edge per key so the single INSERT never touches the same row twice.
        unique: dict[tuple[str, str, str], GraphEdge] = {}
        for edge in edges:
            unique[_edge_key(edge.from_node_uuid, edge.to_node_uuid, edge.relationship)] = edge
        batch = list(unique.values())

        with self.store.staged_table(EDGE_STAGE_NAME, _edge_table(batch)):
            existing = int(self.store.fetch_all(EDGE_EXISTING_COUNT_SQL)[0]["existing_count"])
            self.store.execute(EDGE_UPSERT_FROM_STAGE_SQL)

        return UpsertResult(inserted=len(batch) - existing, updated=existing)
