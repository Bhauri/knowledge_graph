from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import duckdb
import numpy as np
import os


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


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = build_database_path()

TABLE_NAME = "dbo.schema_index"

# Example open-source embedding model
MODEL_NAME = "BAAI/bge-small-en-v1.5"

BATCH_SIZE = 32


# ============================================================
# DATABASE CONNECTION
# ============================================================

connection = duckdb.connect(str(DB_PATH))


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

model = SentenceTransformer(MODEL_NAME)

print(f"Loaded embedding model: {MODEL_NAME}")

# Check embedding dimension
embedding_dimension = model.get_sentence_embedding_dimension()

print(f"Embedding dimension: {embedding_dimension}")


# ============================================================
# READ RECORDS
# ============================================================

select_sql = f"""
    SELECT
        id,
        searchable_text
    FROM {TABLE_NAME}
    WHERE searchable_text IS NOT NULL
      AND TRIM(searchable_text) <> ''
      AND embedding IS NULL
    ORDER BY id
"""

rows = connection.execute(select_sql).fetchall()


print(f"Rows requiring embeddings: {len(rows)}")


# ============================================================
# PROCESS IN BATCHES
# ============================================================

update_sql = f"""
    UPDATE {TABLE_NAME}
    SET embedding = ?
    WHERE id = ?
"""


for start in range(0, len(rows), BATCH_SIZE):

    batch = rows[start:start + BATCH_SIZE]

    ids = [row[0] for row in batch]

    texts = [
        row[1].strip()
        for row in batch
    ]

    # --------------------------------------------------------
    # CREATE EMBEDDINGS
    # --------------------------------------------------------

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    # --------------------------------------------------------
    # UPDATE DATABASE
    # --------------------------------------------------------

    update_data = []

    for row_id, embedding in zip(ids, embeddings):

        embedding_list = embedding.astype(
            np.float32
        ).tolist()

        update_data.append(
            (embedding_list, row_id)
        )

    connection.executemany(update_sql, update_data)

    print(
        f"Processed {min(start + BATCH_SIZE, len(rows))}"
        f"/{len(rows)}"
    )


connection.close()

print("Embedding generation completed.")