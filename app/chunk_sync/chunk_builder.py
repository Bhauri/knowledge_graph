from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .embedding_service import EmbeddingService
from .models import ChunkRecord, SourceFieldSpec, TableChunkSpec
from .text_cleaner import clean_text


class ChunkBuilder:
    """Builds semantic chunks and embeddings from source rows."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        embedding_model_short_name: str,
        embedding_version: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.embedding_model_short_name = embedding_model_short_name
        self.embedding_version = embedding_version
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _extract_field_value(self, row: Mapping[str, Any], spec: SourceFieldSpec) -> Any:
        if spec.source_column in row:
            return row.get(spec.source_column)

        for alias in spec.aliases:
            if alias in row:
                return row.get(alias)

        return None

    def build_chunk(
        self,
        *,
        node_uuid: Any,
        source_table: str,
        source_pk: Any,
        node_type: str,
        field_spec: SourceFieldSpec,
        chunk_order: int,
        text_content: str,
    ) -> ChunkRecord:
        """Build one chunk record and generate its embedding immediately."""

        embedding = self.embedding_service.generate_embedding(text_content)
        return self._make_record(
            node_uuid=node_uuid,
            source_table=source_table,
            source_pk=source_pk,
            node_type=node_type,
            field_spec=field_spec,
            chunk_order=chunk_order,
            text_content=text_content,
            embedding=embedding,
        )

    def _make_record(
        self,
        *,
        node_uuid: Any,
        source_table: str,
        source_pk: Any,
        node_type: str,
        field_spec: SourceFieldSpec,
        chunk_order: int,
        text_content: str,
        embedding: list[float],
    ) -> ChunkRecord:
        metadata = {
            "node_type": node_type,
            "source_table": source_table,
            "source_pk": source_pk,
            "source_column": field_spec.source_column,
            "chunk_type": field_spec.metadata_chunk_type,
        }

        return ChunkRecord(
            node_uuid=node_uuid,
            chunk_type=field_spec.chunk_type,
            chunk_order=chunk_order,
            source_table=source_table,
            source_pk=str(source_pk),
            source_column=field_spec.source_column,
            text_content=text_content,
            embedding=embedding,
            embedding_model=self.embedding_model_short_name,
            embedding_version=self.embedding_version,
            metadata=metadata,
        )

    def _process_rows(
        self,
        spec: TableChunkSpec,
        rows: list[Mapping[str, Any]],
        node_uuid_by_pk: dict[str, Any],
    ) -> tuple[list[ChunkRecord], int, int]:
        pending: list[dict[str, Any]] = []
        skipped_null_fields = 0
        missing_node_count = 0

        for row in rows:
            source_pk = row.get(spec.source_pk_column)
            if source_pk is None:
                continue

            node_uuid = node_uuid_by_pk.get(str(source_pk).strip())
            if node_uuid is None:
                missing_node_count += 1
                self.logger.warning("Missing node_uuid for %s:%s", spec.source_table, source_pk)
                continue

            chunk_order = 0
            for field_spec in spec.fields:
                raw_value = self._extract_field_value(row, field_spec)
                text_content = clean_text(raw_value)
                if text_content is None:
                    skipped_null_fields += 1
                    continue

                chunk_order += 1
                pending.append(
                    {
                        "node_uuid": node_uuid,
                        "source_table": spec.source_table,
                        "source_pk": source_pk,
                        "node_type": spec.node_type,
                        "field_spec": field_spec,
                        "chunk_order": chunk_order,
                        "text_content": text_content,
                    }
                )

        if not pending:
            return [], skipped_null_fields, missing_node_count

        # One batched model call per table slice instead of one call per chunk.
        embeddings = self.embedding_service.generate_embeddings([item["text_content"] for item in pending])
        chunks = [self._make_record(**item, embedding=vector) for item, vector in zip(pending, embeddings)]

        return chunks, skipped_null_fields, missing_node_count

    def process_qe(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)

    def process_psp(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)

    def process_capa(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)

    def process_containment(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)

    def process_events(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)

    def process_evaluations(self, spec: TableChunkSpec, rows: list[Mapping[str, Any]], node_uuid_by_pk: dict[str, Any]) -> tuple[list[ChunkRecord], int, int]:
        return self._process_rows(spec, rows, node_uuid_by_pk)
