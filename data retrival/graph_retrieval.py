from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "graph_store.duckdb"


def _duckdb_path() -> Path:
    env_file = PROJECT_ROOT / "virtual_env" / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
    raw_path = os.getenv("DUCKDB_PATH", "").strip()
    return Path(raw_path) if raw_path else DEFAULT_DUCKDB_PATH


def _connect() -> duckdb.DuckDBPyConnection:
    """Open a fresh read-only connection to the DuckDB graph store."""
    return duckdb.connect(str(_duckdb_path()), read_only=True)


def _fetch_dicts(conn: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, list(params))
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value) if value else {}
    return value if value is not None else {}


def _fetch_node_by_business_key(conn: duckdb.DuckDBPyConnection, business_key: str) -> dict[str, Any] | None:
    rows = _fetch_dicts(
        conn,
        """
        SELECT node_uuid, node_type, business_key, display_name, properties
        FROM graph_nodes
        WHERE business_key = ?
        LIMIT 1
        """,
        (business_key,),
    )
    if not rows:
        return None
    row = rows[0]
    row["node_uuid"] = str(row["node_uuid"])
    row["properties"] = _parse_json(row.get("properties"))
    return row


def _fetch_neighbors(conn: duckdb.DuckDBPyConnection, node_uuid: str) -> list[dict[str, Any]]:
    rows = _fetch_dicts(
        conn,
        """
        SELECT e.relationship, e.to_node_uuid, n.business_key AS to_business_key, n.node_type AS to_node_type, n.display_name AS to_display_name, n.properties AS to_properties
        FROM graph_edges e
        JOIN graph_nodes n ON n.node_uuid = e.to_node_uuid
        WHERE e.from_node_uuid = CAST(? AS UUID)
        ORDER BY e.relationship, n.business_key
        """,
        (node_uuid,),
    )
    for row in rows:
        row["to_node_uuid"] = str(row["to_node_uuid"])
        row["to_properties"] = _parse_json(row.get("to_properties"))
    return rows


def _fetch_chunks_for_nodes(
    conn: duckdb.DuckDBPyConnection,
    node_uuids: list[str],
) -> list[dict[str, Any]]:
    if not node_uuids:
        return []

    placeholders = ", ".join("CAST(? AS UUID)" for _ in node_uuids)
    rows = _fetch_dicts(
        conn,
        f"""
        SELECT
            chunk_uuid,
            node_uuid,
            chunk_type,
            chunk_order,
            source_table,
            source_pk,
            source_column,
            text_content,
            metadata
        FROM vector_chunks
        WHERE node_uuid IN ({placeholders})
        ORDER BY node_uuid, source_column, chunk_order
        """,
        node_uuids,
    )
    for row in rows:
        row["chunk_uuid"] = str(row["chunk_uuid"])
        row["node_uuid"] = str(row["node_uuid"])
        row["metadata"] = _parse_json(row.get("metadata"))
    return rows


def retrieve_business_key_path_properties(business_key: str, max_depth: int = 5) -> dict[str, Any]:
    """Retrieve a starting node by business key and traverse all related nodes along has*/belong* paths.

    The traversal collects node properties from each visited node and returns:
    - the starting node
    - the visited nodes along the traversal path
    - the discovered relationships and their targets
    """

    if not business_key or not business_key.strip():
        raise ValueError("business_key must not be empty")

    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    conn = _connect()
    try:
        start_node = _fetch_node_by_business_key(conn, business_key.strip())
        if not start_node:
            return {
                "business_key": business_key,
                "found": False,
                "start_node": None,
                "visited_nodes": [],
                "relationships": [],
                "related_text_chunks": [],
            }

        visited: dict[str, dict[str, Any]] = {}
        queue: deque[tuple[str, str | None, str | None]] = deque()
        queue.append((str(start_node["node_uuid"]), None, None))

        relationships: list[dict[str, Any]] = []
        visited[str(start_node["node_uuid"])] = {
            "node_uuid": str(start_node["node_uuid"]),
            "node_type": start_node.get("node_type"),
            "business_key": start_node.get("business_key"),
            "display_name": start_node.get("display_name"),
            "properties": start_node.get("properties") or {},
        }

        while queue and len(visited) <= max_depth * 50:
            node_uuid, parent_uuid, parent_relationship = queue.popleft()
            if node_uuid in visited and parent_uuid is not None:
                pass

            neighbors = _fetch_neighbors(conn, node_uuid)
            for neighbor in neighbors:
                rel_name = str(neighbor.get("relationship") or "")
                if not rel_name.startswith("HAS") and not rel_name.startswith("BELONG"):
                    continue

                target_uuid = str(neighbor.get("to_node_uuid"))
                target_record = {
                    "node_uuid": target_uuid,
                    "node_type": neighbor.get("to_node_type"),
                    "business_key": neighbor.get("to_business_key"),
                    "display_name": neighbor.get("to_display_name"),
                    "properties": neighbor.get("to_properties") or {},
                }
                if target_uuid not in visited:
                    visited[target_uuid] = target_record
                    queue.append((target_uuid, node_uuid, rel_name))

                relationships.append(
                    {
                        "from_node_uuid": node_uuid,
                        "to_node_uuid": target_uuid,
                        "relationship": rel_name,
                        "from_business_key": visited.get(node_uuid, {}).get("business_key"),
                        "to_business_key": target_record.get("business_key"),
                    }
                )

        related_text_chunks = _fetch_chunks_for_nodes(conn, list(visited.keys()))
        chunks_by_node_uuid: dict[str, list[dict[str, Any]]] = {}
        for chunk in related_text_chunks:
            chunk_node_uuid = str(chunk.get("node_uuid") or "")
            if not chunk_node_uuid:
                continue
            chunks_by_node_uuid.setdefault(chunk_node_uuid, []).append(chunk)

        for node_uuid, node in visited.items():
            node["text_chunks"] = chunks_by_node_uuid.get(node_uuid, [])

        return {
            "business_key": business_key,
            "found": True,
            "start_node": visited.get(str(start_node["node_uuid"])),
            "visited_nodes": list(visited.values()),
            "relationships": relationships,
            "related_text_chunks": related_text_chunks,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Retrieve graph-node properties by business key")
    parser.add_argument("business_key")
    parser.add_argument("--max-depth", type=int, default=5)
    args = parser.parse_args()

    result = retrieve_business_key_path_properties(args.business_key, max_depth=args.max_depth)
    import json

    print(json.dumps(result, indent=2, default=str))
