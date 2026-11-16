from __future__ import annotations

import json
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "graph_store.duckdb"

# Tables are listed in dependency order for resets (children first).
RESET_ORDER: tuple[str, ...] = ("node_lookup", "vector_chunks", "graph_edges", "graph_nodes")

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS graph_nodes (
        node_uuid UUID PRIMARY KEY,
        node_type VARCHAR NOT NULL,
        business_key VARCHAR NOT NULL,
        display_name VARCHAR NOT NULL,
        source_refs JSON NOT NULL,
        properties JSON NOT NULL,
        embedding_chunk_id UUID,
        created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        UNIQUE (node_type, business_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS graph_edges (
        edge_uuid UUID PRIMARY KEY,
        from_node_uuid UUID NOT NULL,
        to_node_uuid UUID NOT NULL,
        relationship VARCHAR NOT NULL,
        source_refs JSON NOT NULL,
        properties JSON NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        UNIQUE (from_node_uuid, to_node_uuid, relationship)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS node_lookup (
        source_table VARCHAR NOT NULL,
        source_pk VARCHAR NOT NULL,
        node_uuid UUID NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        PRIMARY KEY (source_table, source_pk)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_chunks (
        chunk_uuid UUID PRIMARY KEY DEFAULT uuid(),
        node_uuid UUID NOT NULL,
        chunk_type VARCHAR NOT NULL,
        chunk_order INTEGER NOT NULL,
        source_table VARCHAR NOT NULL,
        source_pk VARCHAR NOT NULL,
        source_column VARCHAR NOT NULL,
        text_content VARCHAR NOT NULL,
        embedding FLOAT[],
        embedding_model VARCHAR,
        embedding_version INTEGER NOT NULL DEFAULT 1,
        metadata JSON NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
        UNIQUE (node_uuid, source_column, chunk_order)
    )
    """,
)


def default_duckdb_path() -> Path:
    """Return the DuckDB file path from DUCKDB_PATH, or the project default."""
    env_file = PROJECT_ROOT / "virtual_env" / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    raw_path = os.getenv("DUCKDB_PATH", "").strip()
    return Path(raw_path) if raw_path else DEFAULT_DUCKDB_PATH


def dump_json(value: Any) -> str:
    """Serialize a value for a DuckDB JSON column."""
    return json.dumps(value, default=str)


class DuckDBStore:
    """Single-file DuckDB store that holds all pipeline outputs.

    DuckDB allows only one writer process at a time, so close other connections
    to the file (for example a running Streamlit app) before running the pipeline.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_duckdb_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.path))
        self._in_transaction = False

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        """Create all pipeline tables if they do not exist."""
        with self.transaction():
            for statement in _SCHEMA_STATEMENTS:
                self.connection.execute(statement)

    def reset_tables(self) -> None:
        """Delete all rows from pipeline tables (schema is kept)."""
        with self.transaction():
            for table in RESET_ORDER:
                self.connection.execute(f"DELETE FROM {table}")

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None:
        self.connection.execute(sql, list(parameters or []))

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        if not rows:
            return
        self.connection.executemany(sql, [list(row) for row in rows])

    @contextmanager
    def staged_table(self, name: str, table: pa.Table) -> Iterator[None]:
        """Expose an Arrow table as a named relation for set-based statements."""
        self.connection.register(name, table)
        try:
            yield
        finally:
            self.connection.unregister(name)

    def fetch_all(self, sql: str, parameters: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        cursor = self.connection.execute(sql, list(parameters or []))
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def count(self, table: str) -> int:
        rows = self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(rows[0])

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Run the enclosed statements in one transaction (nested calls join the outer one)."""
        if self._in_transaction:
            yield
            return
        self.connection.begin()
        self._in_transaction = True
        try:
            yield
        except BaseException:
            self.connection.rollback()
            raise
        finally:
            self._in_transaction = False
        self.connection.commit()
