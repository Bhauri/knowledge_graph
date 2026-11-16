from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.storage.duckdb_store import DuckDBStore

from .models import normalize_key


class NodeLookupService:
    def __init__(self, store: DuckDBStore, logger: logging.Logger | None = None) -> None:
        self.store = store
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._cache: dict[tuple[str, str], UUID] = {}
        self.missing_nodes = 0

    def load_cache(self) -> None:
        rows = self.store.fetch_all("SELECT node_uuid, node_type, business_key FROM graph_nodes")

        self._cache = {
            (str(row["node_type"]).strip(), str(row["business_key"]).strip()): row["node_uuid"]
            for row in rows
        }
        self.logger.info("Loaded node lookup cache with %s entries", len(self._cache))

    def lookup_node(self, node_type: str, business_key: Any) -> UUID | None:
        normalized = normalize_key(business_key)
        if not normalized:
            return None

        key = (node_type.strip(), normalized)
        node_uuid = self._cache.get(key)
        if node_uuid is None:
            self.missing_nodes += 1
        return node_uuid
