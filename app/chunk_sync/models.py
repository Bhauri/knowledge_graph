from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml


@dataclass(frozen=True, slots=True)
class SourceFieldSpec:
    """Field mapping between source data and a semantic chunk."""

    source_column: str
    chunk_type: str
    metadata_chunk_type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TableChunkSpec:
    """Chunk extraction specification for one source table."""

    source_table: str
    node_type: str
    source_pk_column: str
    fields: tuple[SourceFieldSpec, ...]


@dataclass(slots=True)
class ChunkRecord:
    """Canonical chunk record for vector_chunks upsert."""

    node_uuid: UUID
    chunk_type: str
    chunk_order: int
    source_table: str
    source_pk: str
    source_column: str
    text_content: str
    embedding: list[float]
    embedding_model: str
    embedding_version: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _load_chunk_specs() -> tuple[TableChunkSpec, ...]:
    config_path = Path(__file__).resolve().parents[2] / "config" / "table_specs.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Chunk spec config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    tables = payload.get("tables", {})
    specs: list[TableChunkSpec] = []
    for table_name, table_spec in tables.items():
        chunks = table_spec.get("chunks", {}) or {}
        fields_payload = chunks.get("fields", []) or []
        field_specs = tuple(
            SourceFieldSpec(
                source_column=str(field.get("source_column", "")),
                chunk_type=str(field.get("chunk_type", "")),
                metadata_chunk_type=str(field.get("metadata_chunk_type", "")),
                aliases=tuple(str(alias) for alias in field.get("aliases", []) or []),
            )
            for field in fields_payload
        )
        if not field_specs and not chunks:
            continue
        specs.append(
            TableChunkSpec(
                source_table=str(table_spec.get("source_table", table_name)),
                node_type=str(chunks.get("node_type", "")),
                source_pk_column=str(chunks.get("source_pk_column", "")),
                fields=field_specs,
            )
        )
    return tuple(specs)


CHUNK_SPECS: tuple[TableChunkSpec, ...] = _load_chunk_specs()
