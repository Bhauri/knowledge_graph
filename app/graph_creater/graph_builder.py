from __future__ import annotations

import logging
from collections.abc import Iterable

from app.storage.duckdb_store import DuckDBStore

from .processors import process_source_table
from .repositories import SOURCE_TABLES, fetch_source_rows, upsert_nodes


class GraphBuilder:
    def __init__(self, store: DuckDBStore) -> None:
        self.store = store
        self.logger = logging.getLogger(self.__class__.__name__)

    def build(self) -> None:
        for table_name in SOURCE_TABLES:
            rows = fetch_source_rows(self.store, table_name)
            self.logger.info("Processing %s rows=%s", table_name, len(rows))
            nodes = process_source_table(table_name, rows)

            if not nodes:
                self.logger.info("No nodes generated from %s", table_name)
                continue

            batch_size = 1000
            for start in range(0, len(nodes), batch_size):
                batch = nodes[start : start + batch_size]
                with self.store.transaction():
                    upsert_nodes(self.store, batch)
                self.logger.info("Committed batch table=%s batch=%s/%s rows=%s", table_name, (start // batch_size) + 1, (len(nodes) + batch_size - 1) // batch_size, len(batch))

            self.logger.info("Upserted %s nodes from %s", len(nodes), table_name)
