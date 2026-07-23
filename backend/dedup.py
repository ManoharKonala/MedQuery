"""
Deduplication module using SHA-256 (exact match) and MinHash (near-duplicate).
Prevents duplicate documents and chunks from polluting the vector store.
"""

import hashlib
from datasketch import MinHash, MinHashLSH

# Global MinHash LSH index for near-duplicate chunk detection
_lsh = MinHashLSH(threshold=0.92, num_perm=128)
_existing_hashes = set()  # Track inserted MinHash keys



def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of a file's raw bytes for exact deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _create_minhash(text: str) -> MinHash:
    """Create a MinHash signature for a text string using word-level shingles."""
    m = MinHash(num_perm=128)
    words = text.lower().split()
    # Use 3-word shingles for better accuracy
    for i in range(len(words) - 2):
        shingle = " ".join(words[i : i + 3])
        m.update(shingle.encode("utf-8"))
    return m


def is_near_duplicate_chunk(chunk_id: str, text: str) -> bool:
    """Check if a chunk is a near-duplicate of an already indexed chunk.

    Args:
        chunk_id: Unique identifier for this chunk.
        text: The chunk text content.

    Returns:
        True if the chunk is a near-duplicate (should be skipped), False otherwise.
    """
    if len(text.split()) < 5:
        return False

    minhash = _create_minhash(text)

    # Check for similar existing chunks
    try:
        result = _lsh.query(minhash)
        if result:
            return True
    except Exception:
        pass

    # Insert this chunk's MinHash into the LSH index
    try:
        _lsh.insert(chunk_id, minhash)
        _existing_hashes.add(chunk_id)
    except ValueError:
        # Key already exists
        pass

    return False


def filter_duplicate_chunks(chunks: list[dict]) -> list[dict]:
    """Filter out near-duplicate chunks from a list.

    Args:
        chunks: List of chunk dicts with keys: text, chunk_index, section_header.

    Returns:
        Filtered list with near-duplicates removed.
    """
    unique_chunks = []
    for chunk in chunks:
        chunk_id = compute_text_hash(chunk["text"])
        if not is_near_duplicate_chunk(chunk_id, chunk["text"]):
            unique_chunks.append(chunk)

    removed_count = len(chunks) - len(unique_chunks)
    if removed_count > 0:
        print(f"[Dedup] Removed {removed_count} near-duplicate chunks.")
    return unique_chunks
