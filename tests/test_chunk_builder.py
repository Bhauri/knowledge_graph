from uuid import uuid4

from app.chunk_sync.chunk_builder import ChunkBuilder
from app.chunk_sync.embedding_service import EmbeddingService
from app.chunk_sync.models import CHUNK_SPECS


class FakeModel:
    def encode(self, text, normalize_embeddings=True, **kwargs):
        if isinstance(text, list):
            return [[0.1, 0.2, 0.3] for _ in text]
        return [0.1, 0.2, 0.3]



def _embedding_service() -> EmbeddingService:
    return EmbeddingService("sentence-transformers/all-MiniLM-L6-v2", model=FakeModel())



def test_build_chunk_generates_metadata_and_embedding() -> None:
    builder = ChunkBuilder(_embedding_service(), "all-MiniLM-L6-v2", 1)
    spec = CHUNK_SPECS[1]  # psp
    field_spec = spec.fields[0]  # description

    chunk = builder.build_chunk(
        node_uuid=uuid4(),
        source_table="psp",
        source_pk=101,
        node_type="PSP",
        field_spec=field_spec,
        chunk_order=1,
        text_content="Some description",
    )

    assert chunk.source_column == "description"
    assert chunk.chunk_type == "Description"
    assert chunk.metadata == {
        "node_type": "PSP",
        "source_table": "psp",
        "source_pk": 101,
        "source_column": "description",
        "chunk_type": "Description",
    }
    assert chunk.embedding == [0.1, 0.2, 0.3]



def test_process_rows_uses_alias_and_skips_empty_fields() -> None:
    builder = ChunkBuilder(_embedding_service(), "all-MiniLM-L6-v2", 1)
    qe_spec = CHUNK_SPECS[0]

    node_uuid = uuid4()
    rows = [{"qe_id": 1, "observatrion": "  Observation text  ", "expectation": "   "}]

    chunks, skipped, missing = builder.process_qe(qe_spec, rows, {"1": node_uuid})

    assert len(chunks) == 1
    assert chunks[0].source_column == "observatrion"
    assert chunks[0].chunk_order == 1
    assert chunks[0].text_content == "Observation text"
    assert skipped == 1
    assert missing == 0
