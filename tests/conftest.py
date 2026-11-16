from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.storage.duckdb_store import DuckDBStore


@pytest.fixture
def duckdb_store(tmp_path) -> Iterator[DuckDBStore]:
    """Fresh DuckDB store with all pipeline tables created in a temporary file."""

    store = DuckDBStore(tmp_path / "graph_store.duckdb")
    store.initialize()
    try:
        yield store
    finally:
        store.close()
