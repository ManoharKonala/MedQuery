"""
Retriever Module.
Encapsulates the logic for searching the vector database and reranking results.
"""

from embeddings import generate_embedding
from vector_store import search as vector_search
from reranker import rerank

def retrieve_and_rerank(query: str, document_id: str = None, top_k: int = 5) -> list[dict]:
    """
    Executes the full retrieval pipeline:
    1. Embeds the user query.
    2. Searches ChromaDB for the top candidate chunks (broad search).
    3. Reranks the candidates using a cross-encoder for high precision.
    
    Args:
        query: The user's query.
        document_id: Optional filter to restrict search to a single document.
        top_k: Number of final reranked results to return.
        
    Returns:
        A list of chunk dictionaries sorted by relevance.
    """
    # 1. Generate query embedding
    query_embedding = generate_embedding(query)

    # 2. Search ChromaDB (broad search: fetch 20 candidates)
    where_filter = None
    if document_id:
        where_filter = {"document_id": str(document_id)}

    search_results = vector_search(query_embedding, n_results=20, where_filter=where_filter)

    # Format ChromaDB results into a clean list of dictionaries
    chunks = []
    if search_results and search_results.get("ids") and search_results["ids"][0]:
        for i in range(len(search_results["ids"][0])):
            chunks.append({
                "id": search_results["ids"][0][i],
                "text": search_results["documents"][0][i],
                "metadata": search_results["metadatas"][0][i],
                "distance": search_results["distances"][0][i],
            })

    # 3. Rerank for precision (Top 20 -> Top 5)
    reranked_chunks = rerank(query, chunks, top_k=top_k)

    return reranked_chunks
