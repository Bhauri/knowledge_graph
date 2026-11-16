from uuid import uuid4

from app.chunk_sync.chunk_repository import ChunkRepository
from app.chunk_sync.models import ChunkRecord



def _make_chunk(node_uuid, text_content: str) -> ChunkRecord:
    return ChunkRecord(
        node_uuid=node_uuid,
        chunk_type="Description",
        chunk_order=1,
        source_table="psp",
        source_pk="101",
        source_column="description",
        text_content=text_content,
        embedding=[0.1, 0.2, 0.3],
        embedding_model="all-MiniLM-L6-v2",
        embedding_version=1,
        metadata={"node_type": "PSP"},
    )


def test_upsert_chunks_inserts_then_updates_same_key(duckdb_store) -> None:
    repo = ChunkRepository(duckdb_store)
    node_uuid = uuid4()

    with duckdb_store.transaction():
        first = repo.upsert_chunks([_make_chunk(node_uuid, "Example")])
    with duckdb_store.transaction():
        second = repo.upsert_chunks([_make_chunk(node_uuid, "Changed")])

    assert (first.inserted, first.updated) == (1, 0)
    assert (second.inserted, second.updated) == (0, 1)

    rows = duckdb_store.fetch_all("SELECT text_content, embedding FROM vector_chunks")
    assert len(rows) == 1
    assert rows[0]["text_content"] == "Changed"
    assert len(rows[0]["embedding"]) == 3
