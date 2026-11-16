from __future__ import annotations

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "graph_store.duckdb"


def _import_project_config():
    try:
        from config import get_embedding_model  # type: ignore

        return get_embedding_model
    except ModuleNotFoundError:
        project_root = Path(__file__).resolve().parents[1]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from config import get_embedding_model  # type: ignore

        return get_embedding_model


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


def _fetch_embedding_dimension(conn: duckdb.DuckDBPyConnection) -> int | None:
    row = conn.execute(
        """
        SELECT len(embedding)
        FROM vector_chunks
        WHERE embedding IS NOT NULL
        LIMIT 1
        """
    ).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _align_embedding_dimension(values: list[float], target_dim: int | None) -> list[float]:
    if not target_dim or target_dim <= 0:
        return values
    current_dim = len(values)
    if current_dim == target_dim:
        return values
    if current_dim > target_dim:
        return values[:target_dim]
    return values + [0.0] * (target_dim - current_dim)


def _load_graph_retrieval_function():
    script_path = Path(__file__).resolve().parent / "graph_retrieval.py"
    spec = spec_from_file_location("graph_retrieval_module", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load graph retrieval module: {script_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "retrieve_business_key_path_properties"):
        raise AttributeError("retrieve_business_key_path_properties not found in graph_retrieval.py")
    return module.retrieve_business_key_path_properties


def semantic_search_and_traverse(
    user_text: str,
    top_k_chunks: int = 10,
    top_k_keys: int = 5,
    max_depth: int = 5,
) -> dict[str, Any]:
    """Semantic search over vector_chunks, then graph traversal for top business keys."""
    query = (user_text or "").strip()
    if not query:
        raise ValueError("user_text must not be empty")
    if top_k_chunks < 1:
        raise ValueError("top_k_chunks must be at least 1")
    if top_k_keys < 1:
        raise ValueError("top_k_keys must be at least 1")

    get_embedding_model = _import_project_config()
    model = get_embedding_model()
    embedding = model.encode(query)
    conn = _connect()
    try:
        embedding_vector = [float(x) for x in embedding]
        target_dim = _fetch_embedding_dimension(conn)
        aligned_vector = _align_embedding_dimension(embedding_vector, target_dim)

        rows = _fetch_dicts(
            conn,
            """
            SELECT
                vc.chunk_uuid,
                vc.node_uuid,
                vc.chunk_type,
                vc.text_content,
                gn.business_key,
                gn.node_type,
                gn.display_name,
                list_cosine_similarity(vc.embedding, CAST(? AS FLOAT[])) AS similarity
            FROM vector_chunks vc
            JOIN graph_nodes gn ON gn.node_uuid = vc.node_uuid
            WHERE vc.embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT ?
            """,
            (aligned_vector, int(top_k_chunks)),
        )

        chunk_matches: list[dict[str, Any]] = []
        business_key_scores: dict[str, float] = {}

        for row in rows:
            chunk_uuid = str(row.get("chunk_uuid") or "")
            node_uuid = str(row.get("node_uuid") or "")
            business_key = str(row.get("business_key") or "").strip()
            similarity = float(row.get("similarity") or 0.0)

            chunk_matches.append(
                {
                    "chunk_uuid": chunk_uuid,
                    "node_uuid": node_uuid,
                    "node_type": row.get("node_type"),
                    "display_name": row.get("display_name"),
                    "business_key": business_key,
                    "chunk_type": row.get("chunk_type"),
                    "text_content": row.get("text_content"),
                    "similarity": similarity,
                }
            )

            if business_key:
                best = business_key_scores.get(business_key, -1.0)
                if similarity > best:
                    business_key_scores[business_key] = similarity

        ranked_keys = sorted(
            business_key_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[: int(top_k_keys)]

        retrieve_graph = _load_graph_retrieval_function()
        graph_results: dict[str, Any] = {}
        for business_key, score in ranked_keys:
            graph_data = retrieve_graph(business_key, max_depth=max_depth)
            graph_results[business_key] = {
                "similarity": score,
                "graph": graph_data,
            }

        return {
            "query_text": query,
            "top_k_chunks": int(top_k_chunks),
            "top_k_keys": int(top_k_keys),
            "chunk_matches": chunk_matches,
            "business_keys": [key for key, _ in ranked_keys],
            "graph_traversal_by_key": graph_results,
        }
    finally:
        conn.close()
