"""
Hybrid Structure-Enriched Sliding Window Chunker.
Safe & Resilient for Medical Documents.

Strategy:
1. Scans document line-by-line to track the most recent "Section Header".
2. Uses a strict sliding window (by sentence) to ensure chunks never exceed target size.
3. Attaches the tracked section header to the chunk metadata.

This guarantees perfect embedding sizes (no giant chunks due to OCR failure)
while preserving critical medical context (e.g., knowing a chunk belongs to "Adverse Reactions").
"""

import re
import nltk

# Ensure punkt is downloaded for sentence tokenization
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)

from nltk.tokenize import sent_tokenize

# Configuration
TARGET_CHUNK_SIZE = 800  # Target characters per chunk (~150 words)
OVERLAP_SIZE = 150       # Target overlap characters between chunks


def _is_header(line: str) -> bool:
    """Detect if a line looks like a structural header."""
    # Common medical/document header patterns
    header_pattern = re.compile(
        r"^(?:"
        r"#{1,4}\s+.+|"              # Markdown headers (# Title)
        r"[A-Z][A-Z\s]{3,}$|"        # ALL-CAPS lines (e.g., ADVERSE REACTIONS)
        r"\d+\.\d*\s+[A-Z].+"        # Numbered sections (e.g., 1. Introduction)
        r")$"
    )
    return bool(header_pattern.match(line))


def chunk_text(text: str) -> list[dict]:
    """
    Splits text into strict overlapping chunks, while tracking the active section header.
    """
    if not text or not text.strip():
        return []

    chunks = []
    lines = text.split("\n")
    
    current_header = "General Information"
    current_chunk_sentences = []
    current_chunk_length = 0
    chunk_index = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. Track structural context
        # If it looks like a header and isn't too long (sanity check against paragraphs in all-caps)
        if _is_header(line) and len(line) < 100:
            current_header = line.lstrip("#").strip()
            
        # 2. Strict Sliding Window Chunking by sentence
        sentences = sent_tokenize(line)
        for sentence in sentences:
            sentence_len = len(sentence)
            
            # If adding this sentence exceeds our safe size limit
            if current_chunk_length + sentence_len > TARGET_CHUNK_SIZE and current_chunk_sentences:
                
                # A. Save the current chunk, tagging it with the active header
                chunk_str = " ".join(current_chunk_sentences).strip()
                chunks.append({
                    "text": chunk_str,
                    "chunk_index": chunk_index,
                    "section_header": current_header
                })
                chunk_index += 1
                
                # B. Start a new chunk with sentence overlap for context continuity
                overlap_chunk = []
                overlap_length = 0
                
                for prev_sentence in reversed(current_chunk_sentences):
                    if overlap_length + len(prev_sentence) <= OVERLAP_SIZE:
                        overlap_chunk.insert(0, prev_sentence)
                        overlap_length += len(prev_sentence) + 1
                    else:
                        # Ensure at least one overlapping sentence if OVERLAP_SIZE is set
                        if not overlap_chunk and OVERLAP_SIZE > 0:
                            overlap_chunk.insert(0, prev_sentence)
                            overlap_length += len(prev_sentence) + 1
                        break
                
                current_chunk_sentences = overlap_chunk
                current_chunk_sentences.append(sentence)
                current_chunk_length = overlap_length + sentence_len
            else:
                current_chunk_sentences.append(sentence)
                current_chunk_length += sentence_len + 1

    # 3. Flush any remaining sentences into a final chunk
    if current_chunk_sentences:
        chunk_str = " ".join(current_chunk_sentences).strip()
        if chunk_str:
            chunks.append({
                "text": chunk_str,
                "chunk_index": chunk_index,
                "section_header": current_header
            })
            
    print(f"[Chunker] Created {len(chunks)} hybrid chunks from {len(text)} characters.")
    return chunks
