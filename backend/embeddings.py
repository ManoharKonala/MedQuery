"""
Embedding module using sentence-transformers.
Generates dense vector representations for text chunks and queries.
"""

from sentence_transformers import SentenceTransformer
from config import settings
import numpy as np

# Lazy-loaded global model instance
_model = None


def get_model() -> SentenceTransformer:
    """Load the embedding model (cached after first call)."""
    global _model
    if _model is None:
        print(f"[Embeddings] Loading model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        print(f"[Embeddings] Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate a single embedding vector for the given text."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts (more efficient)."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """Return the dimension of the embedding vectors."""
    model = get_model()
    return model.get_sentence_embedding_dimension()
