from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "graph_store.duckdb"
SEED_SCHEMA = "dbo"

# Children first, so a full reset never has to fight dependencies.
SEED_TABLES: tuple[str, ...] = (
    "batch_containment_details",
    "containment_actions",
    "capa",
    "initial_evaluations",
    "qe_events",
    "psp",
    "qe",
)


def connect_seed_db() -> duckdb.DuckDBPyConnection:
    """Open the DuckDB store used by the pipeline and make sure the dbo schema exists."""
    load_dotenv(PROJECT_ROOT / "virtual_env" / ".env")
    raw_path = os.getenv("DUCKDB_PATH", "").strip()
    path = Path(raw_path) if raw_path else DEFAULT_DUCKDB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(path))
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SEED_SCHEMA}")
    return connection


def drop_seed_tables(connection: duckdb.DuckDBPyConnection) -> None:
    for table in SEED_TABLES:
        connection.execute(f"DROP TABLE IF EXISTS {SEED_SCHEMA}.{table}")
        connection.execute(f"DROP SEQUENCE IF EXISTS {SEED_SCHEMA}.{table}_seq")


def recreate_seed_table(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    columns_sql: str,
    id_column: str | None = None,
) -> None:
    """Drop and recreate dbo.<table>. id_column is filled from a sequence when given."""
    connection.execute(f"DROP TABLE IF EXISTS {SEED_SCHEMA}.{table}")
    connection.execute(f"DROP SEQUENCE IF EXISTS {SEED_SCHEMA}.{table}_seq")
    if id_column:
        connection.execute(f"CREATE SEQUENCE {SEED_SCHEMA}.{table}_seq")
        columns_sql = (
            f"{id_column} INTEGER PRIMARY KEY DEFAULT nextval('{SEED_SCHEMA}.{table}_seq'), {columns_sql}"
        )
    connection.execute(f"CREATE TABLE {SEED_SCHEMA}.{table} ({columns_sql})")


def insert_rows(connection: duckdb.DuckDBPyConnection, insert_sql: str, rows: Sequence[Sequence[Any]]) -> None:
    """Bulk insert; insert_sql must end with VALUES %s, which becomes one ? per column."""
    if not rows:
        return
    placeholders = ", ".join("?" for _ in rows[0])
    connection.executemany(insert_sql.replace("VALUES %s", f"VALUES ({placeholders})"), [tuple(row) for row in rows])
