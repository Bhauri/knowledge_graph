from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
import time

from app.storage.duckdb_store import DuckDBStore

from ..chunk_sync.config import get_config
from ..chunk_sync.service import ChunkSyncService
from .graph_builder import GraphBuilder
from .graph_edge_builder import GraphEdgeBuilder
from .node_lookup_updater import NodeLookupUpdater

OUTPUT_TABLES: tuple[str, ...] = ("graph_nodes", "graph_edges", "node_lookup", "vector_chunks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run node creation, node_lookup refresh, edge creation, and chunk embedding sync into DuckDB."
    )
    parser.add_argument(
        "--first-run",
        action="store_true",
        help="Delete all rows from graph_nodes, graph_edges, node_lookup, and vector_chunks in DuckDB before processing.",
    )
    parser.add_argument("--edge-batch-size", type=int, default=5000, help="Bulk UPSERT batch size for edges.")
    parser.add_argument("--log-level", default="INFO", help="Logging level, default: INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    logger = logging.getLogger("main")
    started_at = time.perf_counter()

    store = DuckDBStore()
    store.initialize()
    logger.info("DuckDB store ready path=%s", store.path)

    if args.first_run:
        store.reset_tables()
        logger.info("First-run reset completed for %s", ", ".join(OUTPUT_TABLES))
    else:
        logger.info("No --first-run flag supplied; rebuilding over existing graph data may preserve stale node properties")

    try:
        logger.info("Step 1/4: Building primary and derived graph nodes from table specs")
        GraphBuilder(store=store).build()

        logger.info("Step 2/4: Refreshing node lookup")
        node_lookup_count = NodeLookupUpdater(store=store, logger=logger).refresh_lookup()

        logger.info("Step 3/4: Creating relationships from YAML specs and fallback logic")
        edge_summary = GraphEdgeBuilder(
            store=store,
            batch_size=args.edge_batch_size,
        ).build()

        logger.info("Step 4/4: Creating chunks and embeddings")
        chunk_config = get_config()
        chunk_summary = ChunkSyncService(
            store=store,
            config=chunk_config,
            logger=logger,
        ).sync_chunks()

        row_counts = {table: store.count(table) for table in OUTPUT_TABLES}
    finally:
        store.close()

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info("DuckDB row counts: %s", row_counts)
    logger.info(
        "Pipeline completed node_lookup_entries=%s edge_summary=%s chunk_summary=%s execution_ms=%s",
        node_lookup_count,
        edge_summary,
        chunk_summary,
        elapsed_ms,
    )


if __name__ == "__main__":
    main()
