from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from app.storage.duckdb_store import DuckDBStore

from .edge_models import GraphEdge
from .edge_repository import EdgeRepository
from .node_lookup_service import NodeLookupService
from .relationship_builder import RelationshipBuilder


class GraphEdgeService:
    def __init__(
        self,
        store: DuckDBStore,
        batch_size: int = 5000,
        logger: logging.Logger | None = None,
    ) -> None:
        self.store = store
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.edge_repository = EdgeRepository(store)
        self.node_lookup_service = NodeLookupService(store, logger=self.logger)
        self.relationship_builder = RelationshipBuilder(self.node_lookup_service, logger=self.logger)

    @staticmethod
    def _dedupe_edges(edges: Sequence[GraphEdge]) -> tuple[list[GraphEdge], int]:
        unique: dict[tuple[str, str, str], GraphEdge] = {}

        for edge in edges:
            key = (str(edge.from_node_uuid), str(edge.to_node_uuid), edge.relationship)
            if key in unique:
                continue
            unique[key] = edge

        skipped = len(edges) - len(unique)
        return list(unique.values()), skipped

    def _upsert_in_batches(self, edges: Sequence[GraphEdge]) -> tuple[int, int]:
        created = 0
        updated = 0

        total = len(edges)
        for start in range(0, total, self.batch_size):
            chunk = edges[start : start + self.batch_size]
            # Commit per batch so completed work survives an interrupted run.
            with self.store.transaction():
                result = self.edge_repository.upsert_edges(chunk)
            created += result.inserted
            updated += result.updated
            self.logger.info("Edges committed: %d/%d", min(start + len(chunk), total), total)

        return created, updated

    def sync_edges(self) -> dict[str, int]:
        start = time.perf_counter()

        self.node_lookup_service.load_cache()

        qe_rows = self.edge_repository.fetch_source_rows("qe")
        psp_rows = self.edge_repository.fetch_source_rows("psp")
        capa_rows = self.edge_repository.fetch_source_rows("capa")
        containment_rows = self.edge_repository.fetch_source_rows("containment_actions")
        batch_rows = self.edge_repository.fetch_source_rows("batch_containment_details")
        event_rows = self.edge_repository.fetch_source_rows("qe_events")
        evaluation_rows = self.edge_repository.fetch_source_rows("initial_evaluations")

        rows_by_table = {
            "qe": qe_rows,
            "psp": psp_rows,
            "capa": capa_rows,
            "containment_actions": containment_rows,
            "batch_containment_details": batch_rows,
            "qe_events": event_rows,
            "initial_evaluations": evaluation_rows,
        }

        edges: list[GraphEdge] = []
        edges.extend(self.relationship_builder.process_yaml_relationships(self.relationship_builder._yaml_relationships, rows_by_table))
        edges.extend(self.relationship_builder.process_qe(qe_rows, psp_rows, evaluation_rows, event_rows, containment_rows))
        edges.extend(self.relationship_builder.process_psp(psp_rows, capa_rows, event_rows, containment_rows))
        edges.extend(self.relationship_builder.process_capa(capa_rows))
        edges.extend(self.relationship_builder.process_containment(containment_rows, batch_rows))
        edges.extend(self.relationship_builder.process_batch(batch_rows))
        edges.extend(self.relationship_builder.process_event(event_rows))
        edges.extend(self.relationship_builder.process_evaluation(evaluation_rows, event_rows))

        deduped_edges, duplicates_skipped = self._dedupe_edges(edges)
        created, updated = self._upsert_in_batches(deduped_edges)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        summary = {
            "edges_generated": len(edges),
            "edges_upserted": len(deduped_edges),
            "edges_created": created,
            "edges_updated": updated,
            "duplicates_skipped": duplicates_skipped,
            "missing_nodes": self.node_lookup_service.missing_nodes,
            "execution_ms": elapsed_ms,
        }

        self.logger.info("Edge sync summary: %s", summary)
        return summary
