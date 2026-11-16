from __future__ import annotations

import logging
import time
from typing import Callable

from app.storage.duckdb_store import DuckDBStore

from .chunk_builder import ChunkBuilder
from .chunk_repository import ChunkRepository, UpsertResult
from .config import ChunkSyncConfig
from .embedding_service import EmbeddingService
from .models import TableChunkSpec
from .node_lookup_service import NodeLookupService
from .repositories import SourceRepository


def _default_chunk_processor(builder: ChunkBuilder, spec: TableChunkSpec):
    def _process(rows: list, node_uuid_by_pk: dict[str, object]):
        return builder._process_rows(spec, rows, node_uuid_by_pk)

    return _process


class ChunkSyncService:
    """Coordinates source extraction, chunk creation, embedding, and persistence.

    Source rows and chunks are read and written through the DuckDB store.
    """

    def __init__(
        self,
        store: DuckDBStore,
        config: ChunkSyncConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        self.source_repository = SourceRepository(store)
        self.node_lookup_service = NodeLookupService(store, logger=self.logger)
        self.embedding_service = EmbeddingService(config.embedding_model_name, logger=self.logger)
        self.chunk_builder = ChunkBuilder(
            embedding_service=self.embedding_service,
            embedding_model_short_name=config.embedding_model_short_name,
            embedding_version=config.embedding_version,
            logger=self.logger,
        )
        self.chunk_repository = ChunkRepository(store)

    def _processor_for(self, table_name: str) -> Callable:
        del table_name
        return lambda spec, rows, node_uuid_by_pk: _default_chunk_processor(self.chunk_builder, spec)(rows, node_uuid_by_pk)

    def _upsert_in_batches(self, chunks: list, batch_size: int) -> UpsertResult:
        total_inserted = 0
        total_updated = 0

        if not chunks:
            return UpsertResult()

        with self.store.transaction():
            for index in range(0, len(chunks), batch_size):
                batch = chunks[index : index + batch_size]
                result = self.chunk_repository.upsert_chunks(batch)
                total_inserted += result.inserted
                total_updated += result.updated

        return UpsertResult(inserted=total_inserted, updated=total_updated)

    def _flush_pending_chunks_if_needed(
        self,
        pending_chunks: list,
        rows_since_flush: int,
        total_inserted: int,
        total_updated: int,
    ) -> tuple[int, int]:
        if rows_since_flush >= 1000 and pending_chunks:
            upsert_result = self._upsert_in_batches(pending_chunks, self.config.upsert_batch_size)
            pending_chunks.clear()
            return total_inserted + upsert_result.inserted, total_updated + upsert_result.updated

        return total_inserted, total_updated

    def sync_chunks(self) -> dict[str, int]:
        start = time.perf_counter()
        self.logger.info("Chunk sync started")

        self.node_lookup_service.load_cache()

        records_processed = 0
        chunks_generated = 0
        skipped_null_fields = 0

        total_inserted = 0
        total_updated = 0
        pending_chunks: list = []
        rows_since_flush = 0

        for spec in self.source_repository.specs():
            process_fn = self._processor_for(spec.source_table)
            self.logger.info("Processing table=%s", spec.source_table)

            for rows in self.source_repository.iter_table_rows(
                table=spec.source_table,
                pk_column=spec.source_pk_column,
                batch_size=self.config.source_batch_size,
            ):
                records_processed += len(rows)

                for start in range(0, len(rows), 1000):
                    chunk_rows = rows[start : start + 1000]

                    node_uuid_by_pk = {}
                    for row in chunk_rows:
                        source_pk = row.get(spec.source_pk_column)
                        if source_pk is None:
                            continue
                        node_uuid = self.node_lookup_service.get_node_uuid(spec.source_table, source_pk)
                        if node_uuid is not None:
                            node_uuid_by_pk[str(source_pk).strip()] = node_uuid

                    chunks, skipped, _missing = process_fn(spec, chunk_rows, node_uuid_by_pk)
                    skipped_null_fields += skipped
                    chunks_generated += len(chunks)
                    pending_chunks.extend(chunks)
                    rows_since_flush += len(chunk_rows)

                    total_inserted, total_updated = self._flush_pending_chunks_if_needed(
                        pending_chunks,
                        rows_since_flush,
                        total_inserted,
                        total_updated,
                    )
                    if rows_since_flush >= 1000:
                        rows_since_flush = 0

                    self.logger.info(
                        "batch_complete table=%s rows=%s chunks=%s inserted=%s updated=%s",
                        spec.source_table,
                        len(chunk_rows),
                        len(chunks),
                        total_inserted,
                        total_updated,
                    )

        if pending_chunks:
            upsert_result = self._upsert_in_batches(pending_chunks, self.config.upsert_batch_size)
            total_inserted += upsert_result.inserted
            total_updated += upsert_result.updated

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        summary = {
            "records_processed": records_processed,
            "chunks_generated": chunks_generated,
            "chunks_inserted": total_inserted,
            "chunks_updated": total_updated,
            "skipped_null_fields": skipped_null_fields,
            "missing_node_uuid": self.node_lookup_service.missing_nodes,
            "execution_ms": elapsed_ms,
        }

        self.logger.info("Chunk sync completed summary=%s", summary)
        return summary
