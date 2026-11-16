from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pyarrow as pa

from app.storage.duckdb_store import DuckDBStore, dump_json

from .models import ChunkRecord


CHUNK_STAGE_NAME = "staged_chunks"

# Counts staged chunks that already exist, so inserted/updated can be reported per batch.
CHUNK_EXISTING_COUNT_SQL = f"""
    SELECT COUNT(*) AS existing_count FROM {CHUNK_STAGE_NAME} s
    JOIN vector_chunks v
      ON v.node_uuid = CAST(s.node_uuid AS UUID)
     AND v.source_column = s.source_column
     AND v.chunk_order = s.chunk_order
"""

# One set-based statement per batch instead of one executemany call per row.
CHUNK_UPSERT_FROM_STAGE_SQL = f"""
    INSERT INTO vector_chunks (
        node_uuid, chunk_type, chunk_order, source_table, source_pk, source_column,
        text_content, embedding, embedding_model, embedding_version, metadata
    )
    SELECT
        CAST(s.node_uuid AS UUID), s.chunk_type, s.chunk_order, s.source_table, s.source_pk,
        s.source_column, s.text_content, CAST(s.embedding AS FLOAT[]), s.embedding_model,
        s.embedding_version, CAST(s.metadata AS JSON)
    FROM {CHUNK_STAGE_NAME} s
    ON CONFLICT (node_uuid, source_column, chunk_order) DO UPDATE SET
        chunk_type = excluded.chunk_type,
        source_table = excluded.source_table,
        source_pk = excluded.source_pk,
        text_content = excluded.text_content,
        embedding = excluded.embedding,
        embedding_model = excluded.embedding_model,
        embedding_version = excluded.embedding_version,
        metadata = excluded.metadata,
        updated_at = now()
"""


@dataclass(slots=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0


def _chunk_key(node_uuid: Any, source_column: str, chunk_order: Any) -> tuple[str, str, int]:
    return (str(node_uuid), str(source_column), int(chunk_order))


def _chunk_table(chunks: Sequence[ChunkRecord]) -> pa.Table:
    """Build an Arrow table for one batch of chunks (keys are unique per batch)."""
    return pa.table(
        {
            "node_uuid": pa.array([str(chunk.node_uuid) for chunk in chunks], pa.string()),
            "chunk_type": pa.array([chunk.chunk_type for chunk in chunks], pa.string()),
            "chunk_order": pa.array([int(chunk.chunk_order) for chunk in chunks], pa.int32()),
            "source_table": pa.array([chunk.source_table for chunk in chunks], pa.string()),
            "source_pk": pa.array([str(chunk.source_pk) for chunk in chunks], pa.string()),
            "source_column": pa.array([chunk.source_column for chunk in chunks], pa.string()),
            "text_content": pa.array([chunk.text_content for chunk in chunks], pa.string()),
            "embedding": pa.array(
                [None if chunk.embedding is None else [float(value) for value in chunk.embedding] for chunk in chunks],
                pa.list_(pa.float32()),
            ),
            "embedding_model": pa.array([chunk.embedding_model for chunk in chunks], pa.string()),
            "embedding_version": pa.array([int(chunk.embedding_version) for chunk in chunks], pa.int32()),
            "metadata": pa.array([dump_json(chunk.metadata) for chunk in chunks], pa.string()),
        }
    )


class ChunkRepository:
    """Persists chunk records to DuckDB using conflict-safe upserts."""

    def __init__(self, store: DuckDBStore) -> None:
        self.store = store

    def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> UpsertResult:
        """Insert or update chunks. Must run inside a store transaction opened by the caller."""
        if not chunks:
            return UpsertResult()

        # Keep the last chunk per key so the single INSERT never touches the same row twice.
        unique: dict[tuple[str, str, int], ChunkRecord] = {}
        for chunk in chunks:
            unique[_chunk_key(chunk.node_uuid, chunk.source_column, chunk.chunk_order)] = chunk
        batch = list(unique.values())

        with self.store.staged_table(CHUNK_STAGE_NAME, _chunk_table(batch)):
            existing = int(self.store.fetch_all(CHUNK_EXISTING_COUNT_SQL)[0]["existing_count"])
            self.store.execute(CHUNK_UPSERT_FROM_STAGE_SQL)

        return UpsertResult(inserted=len(batch) - existing, updated=existing)

    def upsert_chunk(self, chunk: ChunkRecord) -> UpsertResult:
        """UPSERT a single chunk by delegating to batched implementation."""

        return self.upsert_chunks([chunk])
