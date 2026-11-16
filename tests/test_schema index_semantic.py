from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import duckdb
import numpy as np
import os
# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_database_environment() -> None:
    env_path = PROJECT_ROOT / "virtual_env" / ".env"

    if env_path.exists():
        load_dotenv(env_path)
        return

    load_dotenv()


def build_database_path() -> Path:
    load_database_environment()

    raw_path = os.getenv("DUCKDB_PATH", "").strip()
    return Path(raw_path) if raw_path else PROJECT_ROOT / "data" / "graph_store.duckdb"


DB_PATH = build_database_path()

MODEL_NAME = "BAAI/bge-small-en-v1.5"

connection = duckdb.connect(str(DB_PATH), read_only=True)

model = SentenceTransformer(MODEL_NAME)


# ============================================================
# SEMANTIC SEARCH
# ============================================================

import re


def normalize(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def semantic_search(
    query: str,
    top_k: int = 10,
    similarity_threshold: float = 0.60
):
    """
    Hybrid schema search:

    1. Vector similarity
    2. Alias / searchable_text lexical match
    3. Node type relevance

    Semantic search generates candidates.
    Lexical and node-type signals improve ranking.
    """

    if not query or not query.strip():
        return []

    # --------------------------------------------------
    # 1. Embedding
    # --------------------------------------------------

    query_embedding = model.encode(
        query,
        normalize_embeddings=True
    )

    query_vector = query_embedding.tolist()

    # --------------------------------------------------
    # 2. DuckDB candidate search
    # --------------------------------------------------

    sql = """
        WITH scored AS (
            SELECT
                id,
                object_type,
                entity_name,
                property_name,
                canonical_name,
                data_type,
                node_type,
                filterable,
                sortable,
                searchable_text,
                aliases,
                metadata,

                list_cosine_similarity(
                    embedding,
                    CAST($query_embedding AS FLOAT[])
                ) AS similarity,

                CASE
                    WHEN list_contains(
                        list_transform(COALESCE(aliases, []), x -> lower(x)),
                        lower($query)
                    )
                    THEN 1.0

                    WHEN
                        lower($query) = lower(property_name)
                    THEN 0.9

                    WHEN
                        lower($query) = lower(canonical_name)
                    THEN 0.9

                    WHEN
                        lower(searchable_text) LIKE
                        '%' || lower($query) || '%'
                    THEN 0.7

                    ELSE 0.0
                END AS lexical_score

            FROM dbo.schema_index

            WHERE embedding IS NOT NULL
        )

        SELECT *
        FROM scored
        WHERE similarity >= $threshold
        ORDER BY similarity DESC
        LIMIT $candidate_limit
    """

    cursor = connection.execute(
        sql,
        {
            "query_embedding": query_vector,
            "query": query.strip(),
            "threshold": similarity_threshold,
            "candidate_limit": max(top_k * 3, 20)
        }
    )
    columns = [column[0] for column in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # --------------------------------------------------
    # 3. Hybrid ranking
    # --------------------------------------------------

    query_normalized = normalize(query)

    results = []

    for row in rows:

        result = dict(row)

        similarity = float(
            result.get("similarity") or 0
        )

        lexical_score = float(
            result.get("lexical_score") or 0
        )

        # ----------------------------------------------
        # Node type relevance
        # ----------------------------------------------

        node_type = normalize(
            result.get("node_type") or ""
        )

        property_name = normalize(
            result.get("property_name") or ""
        )

        searchable_text = normalize(
            result.get("searchable_text") or ""
        )

        node_type_score = 0.0

        # Example:
        # "defect code" should favor FailureCode
        if (
            "defect" in query_normalized
            or "failure code" in query_normalized
        ):
            if node_type == "failurecode":
                node_type_score = 1.0

        # Location concepts
        elif "location" in query_normalized:
            if node_type == "location":
                node_type_score = 1.0

        # Root cause concepts
        elif "root cause" in query_normalized:
            if node_type in {
                "rootcause",
                "rootcausecategory"
            }:
                node_type_score = 1.0

        # ----------------------------------------------
        # Final score
        # ----------------------------------------------

        final_score = (
            similarity * 0.60
            + lexical_score * 0.25
            + node_type_score * 0.15
        )

        result["lexical_score"] = lexical_score
        result["node_type_score"] = node_type_score
        result["final_score"] = final_score

        results.append(result)

    # --------------------------------------------------
    # 4. Final ranking
    # --------------------------------------------------

    results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return results[:top_k]


results = semantic_search(
    "How many events failed with defect code 123?"
)

for result in results:
    print(
        result["entity_name"],
        result["property_name"],
        result["canonical_name"],
        result["similarity"]
    )