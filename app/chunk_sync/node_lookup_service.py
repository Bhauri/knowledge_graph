from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.storage.duckdb_store import DuckDBStore


class NodeLookupService:
    """Resolves source record IDs to graph node UUIDs via the DuckDB node_lookup table."""

    def __init__(self, store: DuckDBStore, logger: logging.Logger | None = None) -> None:
        self.store = store
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._cache: dict[tuple[str, str], UUID] = {}
        self.missing_nodes = 0

    def load_cache(self) -> None:
        """Preload node lookup mapping once for fast in-memory resolution."""

        rows = self.store.fetch_all(
            """
            SELECT nl.source_table, nl.source_pk, gn.node_uuid
            FROM node_lookup nl
            INNER JOIN graph_nodes gn ON gn.node_uuid = nl.node_uuid
            """
        )

        self._cache = {
            (str(row["source_table"]).strip().lower(), str(row["source_pk"]).strip()): row["node_uuid"]
            for row in rows
            if row.get("source_table") is not None and row.get("source_pk") is not None and row.get("node_uuid") is not None
        }

        self.logger.info("Loaded node_lookup cache entries=%s", len(self._cache))

    def get_node_uuid(self, source_table: str, source_pk: Any) -> UUID | None:
        """Get node UUID from cached source_table + source_pk key."""

        key = (source_table.strip().lower(), str(source_pk).strip())
        node_uuid = self._cache.get(key)

        if node_uuid is None:
            self.missing_nodes += 1

        return node_uuid
