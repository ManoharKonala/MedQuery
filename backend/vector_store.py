"""
ChromaDB vector store manager.
Handles adding, searching, and deleting document chunks.
Persists data to a local directory — no server needed.
"""

import chromadb
from config import settings

# Lazy-loaded global client and collection
_client = None
_collection = None

COLLECTION_NAME = "medicalquery_chunks"


def get_collection():
    """Get or create the ChromaDB collection (cached after first call)."""
    global _client, _collection
    if _collection is None:
        print(f"[ChromaDB] Initializing persistent client at: {settings.chroma_persist_dir}")
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
        print(f"[ChromaDB] Collection '{COLLECTION_NAME}' ready. Total chunks: {_collection.count()}")
    return _collection


def add_chunks(
    chunk_ids: list[str],
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
):
    """Add chunks with their embeddings and metadata to ChromaDB."""
    collection = get_collection()
    collection.add(
        ids=chunk_ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"[ChromaDB] Added {len(chunk_ids)} chunks. Total: {collection.count()}")


def search(
    query_embedding: list[float],
    n_results: int = 20,
    where_filter: dict = None,
) -> dict:
    """Search ChromaDB for the most similar chunks.

    Args:
        query_embedding: The query vector.
        n_results: Number of results to return.
        where_filter: Optional metadata filter (e.g., {"document_id": "..."}).

    Returns:
        Dict with keys: ids, documents, metadatas, distances
    """
    collection = get_collection()

    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter:
        query_params["where"] = where_filter

    results = collection.query(**query_params)
    return results


def delete_by_document_id(document_id: str):
    """Delete all chunks belonging to a specific document."""
    collection = get_collection()
    collection.delete(where={"document_id": document_id})
    print(f"[ChromaDB] Deleted chunks for document: {document_id}")


def get_chunk_count() -> int:
    """Return the total number of chunks in the collection."""
    collection = get_collection()
    return collection.count()


def get_chunk_count_by_document(document_id: str) -> int:
    """Return the number of chunks for a specific document."""
    collection = get_collection()
    results = collection.get(where={"document_id": document_id})
    return len(results["ids"])
