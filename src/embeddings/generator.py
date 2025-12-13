"""Embedding generation utilities for text content."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# Default model
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIM = 384


class EmbeddingGenerator:
    """Generate embeddings for text content."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialize embedding generator.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self.model.get_sentence_embedding_dimension()

    def encode(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to encode

        Returns:
            Embedding vector as list of floats
        """
        return self.model.encode(text).tolist()

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, batch_size=batch_size)
        return [emb.tolist() for emb in embeddings]


# Singleton instance
_generator: EmbeddingGenerator | None = None


def get_generator(model_name: str = DEFAULT_MODEL) -> EmbeddingGenerator:
    """Get or create singleton embedding generator."""
    global _generator
    if _generator is None or _generator._model_name != model_name:
        _generator = EmbeddingGenerator(model_name)
    return _generator
