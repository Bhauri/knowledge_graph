from __future__ import annotations

import logging

from app.storage.duckdb_store import DuckDBStore

from .graph_edge_service import GraphEdgeService


class GraphEdgeBuilder:
    def __init__(self, store: DuckDBStore, batch_size: int = 5000) -> None:
        self.store = store
        self.batch_size = batch_size
        self.logger = logging.getLogger(self.__class__.__name__)

    def build(self) -> dict[str, int]:
        service = GraphEdgeService(self.store, batch_size=self.batch_size, logger=self.logger)
        return service.sync_edges()
