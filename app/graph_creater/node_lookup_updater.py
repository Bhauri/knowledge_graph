from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.storage.duckdb_store import DuckDBStore


PRIMARY_SOURCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("qe", "qe_id"),
    ("psp", "psp_id"),
    ("capa", "capa_id"),
    ("containment_actions", "con_id"),
    ("batch_containment_details", "batch"),
    ("qe_events", "event_id"),
    ("initial_evaluations", "eval_id"),
)


def _load_refs(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        value = json.loads(value)
    return [ref for ref in (value or []) if isinstance(ref, dict)]


class NodeLookupUpdater:
    """Maintains the node_lookup table in DuckDB from primary graph node source references."""

    def __init__(self, store: DuckDBStore, logger: logging.Logger | None = None) -> None:
        self.store = store
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def refresh_lookup(self) -> int:
        """Rebuild node_lookup entries from graph_nodes.source_refs for primary records only.

        When several nodes reference the same primary key, the last one read wins.
        """
        primary_columns = set(PRIMARY_SOURCE_COLUMNS)
        rows = self.store.fetch_all("SELECT node_uuid, source_refs FROM graph_nodes")

        entries: dict[tuple[str, str], UUID] = {}
        for row in rows:
            node_uuid = row["node_uuid"]
            for ref in _load_refs(row["source_refs"]):
                table_name = ref.get("table")
                column_name = ref.get("column")
                primary_key = ref.get("primary_key")
                if (table_name, column_name) not in primary_columns:
                    continue
                if primary_key is None or str(primary_key) == "":
                    continue
                entries[(str(table_name), str(primary_key))] = node_uuid

        with self.store.transaction():
            self.store.execute("DELETE FROM node_lookup")
            self.store.executemany(
                "INSERT INTO node_lookup (source_table, source_pk, node_uuid) VALUES (?, ?, ?)",
                [(table, pk, node_uuid) for (table, pk), node_uuid in entries.items()],
            )

        self.logger.info("Node lookup refreshed entries=%s", len(entries))
        return len(entries)
