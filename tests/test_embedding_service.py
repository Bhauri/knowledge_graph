from app.chunk_sync.embedding_service import EmbeddingService


class SpyModel:
    def __init__(self) -> None:
        self.calls = []

    def encode(self, text, normalize_embeddings=True, **kwargs):
        self.calls.append((text, normalize_embeddings))
        return [0.5] * 384



def test_generate_embedding_uses_normalization_and_returns_384() -> None:
    model = SpyModel()
    service = EmbeddingService("sentence-transformers/all-MiniLM-L6-v2", model=model)

    vector = service.generate_embedding("hello")

    assert len(vector) == 384
    assert model.calls == [("hello", True)]


def test_generate_embeddings_encodes_batch_in_one_call() -> None:
    class BatchModel:
        def __init__(self) -> None:
            self.calls = []

        def encode(self, texts, normalize_embeddings=True, **kwargs):
            self.calls.append(list(texts))
            return [[0.5, 0.25] for _ in texts]

    model = BatchModel()
    service = EmbeddingService("sentence-transformers/all-mpnet-base-v2", model=model)

    vectors = service.generate_embeddings(["a", "b"])

    assert vectors == [[0.5, 0.25], [0.5, 0.25]]
    assert model.calls == [["a", "b"]]
