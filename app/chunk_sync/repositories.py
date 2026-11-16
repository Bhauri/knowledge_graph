from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.storage.duckdb_store import DuckDBStore

from .models import CHUNK_SPECS, TableChunkSpec


class SourceRepository:
    """Source table reader with predictable batch iteration."""

    def __init__(self, store: DuckDBStore) -> None:
        self.store = store

    def iter_table_rows(self, table: str, pk_column: str, batch_size: int) -> Iterable[list[Mapping[str, Any]]]:
        offset = 0

        while True:
            query = f"""
                SELECT *
                FROM dbo.{table}
                ORDER BY {pk_column}
                LIMIT ? OFFSET ?
                """

            rows = self.store.fetch_all(query, [batch_size, offset])

            if not rows:
                break

            yield rows
            offset += batch_size

    def specs(self) -> tuple[TableChunkSpec, ...]:
        return CHUNK_SPECS
