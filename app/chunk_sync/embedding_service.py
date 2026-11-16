from __future__ import annotations

import logging
import os
from typing import Protocol, Sequence


class EncoderModel(Protocol):
    def encode(self, sentences: str | list[str], normalize_embeddings: bool = True, **kwargs: object) -> Sequence[float]:
        ...


class EmbeddingService:
    """Generates normalized embeddings using a locally loaded SentenceTransformer model."""

    def __init__(
        self,
        model_name: str,
        logger: logging.Logger | None = None,
        model: EncoderModel | None = None,
        batch_size: int = 64,
    ) -> None:
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.model_name = model_name
        self.batch_size = batch_size

        if model is not None:
            self.model = model
            self.logger.info("Embedding model injected for runtime/testing: %s", model_name)
            return

        # Import at runtime so unit tests can run without loading transformer dependencies.
        import torch
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        torch.set_num_threads(os.cpu_count() or torch.get_num_threads())
        self.logger.info("Loading embedding model: %s with threads=%s", model_name, torch.get_num_threads())
        self.model = SentenceTransformer(model_name, device="cpu")
        self.logger.info("Embedding model loaded")

    def generate_embedding(self, text: str) -> list[float]:
        """Generate one normalized embedding vector for input text."""

        vector = self.model.encode(text, normalize_embeddings=True)

        if hasattr(vector, "tolist"):
            output = vector.tolist()
        else:
            output = list(vector)

        return [float(value) for value in output]

    def generate_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate normalized embedding vectors for many texts in one model call."""

        if not texts:
            return []

        vectors = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )

        rows = vectors.tolist() if hasattr(vectors, "tolist") else list(vectors)
        if len(rows) != len(texts):
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(rows)}")

        return [[float(value) for value in row] for row in rows]
