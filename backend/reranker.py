"""
Cross-encoder reranker module.
Re-scores (query, chunk) pairs for precision after initial vector retrieval.
"""

from sentence_transformers import CrossEncoder
from config import settings

# Lazy-loaded global reranker instance
_reranker = None


def get_reranker() -> CrossEncoder:
    """Load the cross-encoder reranker model (cached after first call)."""
    global _reranker
    if _reranker is None:
        print(f"[Reranker] Loading model: {settings.reranker_model}")
        _reranker = CrossEncoder(settings.reranker_model)
        print("[Reranker] Model loaded.")
    return _reranker


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Re-rank retrieved chunks using the cross-encoder.

    Args:
        query: The user's search query.
        chunks: List of dicts with keys: id, text, metadata, distance.
        top_k: Number of top results to return after reranking.

    Returns:
        Top-K chunks sorted by cross-encoder relevance score (highest first).
    """
    if not chunks:
        return []

    reranker = get_reranker()

    # Prepare (query, passage) pairs for the cross-encoder
    pairs = [(query, chunk["text"]) for chunk in chunks]

    # Score all pairs
    scores = reranker.predict(pairs)

    # Attach scores to chunks
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i])

    # Sort by rerank score (highest = most relevant) and take top-K
    ranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
    return ranked[:top_k]
