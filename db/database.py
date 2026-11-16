from __future__ import annotations

from typing import Any

import duckdb

from app.storage.duckdb_store import default_duckdb_path


class Database:
    """DuckDB access for the agent. Named parameters use the `$name` form."""

    def __init__(self) -> None:
        self.path = default_duckdb_path()
        self.connection = duckdb.connect(str(self.path))

    def execute(self, sql_text: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.connection.execute(sql_text, parameters)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def table_columns(self, schema: str, table: str) -> set[str]:
        rows = self.connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $schema_name
              AND table_name = $table_name
            """,
            {"schema_name": schema, "table_name": table},
        ).fetchall()
        return {row[0] for row in rows}
