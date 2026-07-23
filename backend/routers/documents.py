"""
Document management API routes.
Handles file upload, CRUD, batch upload, and full ingestion pipeline.
"""

import os
import uuid
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import Optional, List

from config import settings
from database import execute_query, fetch_one, fetch_all
from schemas import DocumentOut, DocumentUpdate
from ocr_parser import parse_document
from pii_redactor import redact_pii_batch
from chunker import chunk_text
from dedup import compute_file_hash, filter_duplicate_chunks
from embeddings import generate_embeddings_batch
from vector_store import add_chunks, delete_by_document_id, get_chunk_count_by_document

router = APIRouter(prefix="/documents", tags=["Documents"])


def _save_upload_file(file: UploadFile) -> tuple[str, bytes]:
    """Save an uploaded file to the uploads directory and return (path, raw_bytes)."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    save_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")

    content = file.file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    return save_path, content


def _run_ingestion_pipeline(doc_id: str, file_path: str, title: str) -> int:
    """Run the full ingestion pipeline for a document.

    Steps: Parse → PII Redact → Chunk → Dedup → Embed → Store in ChromaDB.
    Returns the number of chunks created.
    """
    # 1. Parse the document (OCR if needed)
    parsed = parse_document(file_path)
    raw_text = parsed["text"]
    pages = parsed["pages"]
    page_count = parsed["page_count"]

    # Update page count in PostgreSQL
    execute_query(
        "UPDATE documents SET page_count = %s WHERE id = %s",
        (page_count, doc_id),
    )

    if not raw_text.strip():
        execute_query(
            "UPDATE documents SET status = %s WHERE id = %s",
            ("empty", doc_id),
        )
        return 0

    # 2. Structure-aware semantic chunking
    chunks = chunk_text(raw_text)
    if not chunks:
        execute_query(
            "UPDATE documents SET status = %s WHERE id = %s",
            ("no_chunks", doc_id),
        )
        return 0

    # 3. PII Redaction
    chunk_texts = [c["text"] for c in chunks]
    redacted_texts = redact_pii_batch(chunk_texts)
    for i, chunk in enumerate(chunks):
        chunk["text"] = redacted_texts[i]

    # 4. Deduplication (filter near-duplicate chunks)
    chunks = filter_duplicate_chunks(chunks)

    if not chunks:
        execute_query(
            "UPDATE documents SET status = %s WHERE id = %s",
            ("all_duplicates", doc_id),
        )
        return 0

    # 5. Generate embeddings (batch)
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = generate_embeddings_batch(texts_to_embed)

    # 6. Prepare metadata and IDs for ChromaDB
    chunk_ids = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        chunk_ids.append(chunk_id)
        metadatas.append({
            "document_id": doc_id,
            "document_title": title,
            "section_header": chunk.get("section_header", ""),
            "chunk_index": chunk.get("chunk_index", i),
            "page_number": _find_page_for_chunk(chunk["text"], pages),
        })

    # 7. Store in ChromaDB
    add_chunks(chunk_ids, texts_to_embed, embeddings, metadatas)

    # 8. Update document status in PostgreSQL
    execute_query(
        "UPDATE documents SET status = %s, chunk_count = %s WHERE id = %s",
        ("completed", len(chunk_ids), doc_id),
    )

    return len(chunk_ids)


def _find_page_for_chunk(chunk_text: str, pages: list[dict]) -> int:
    """Find which page a chunk most likely belongs to based on text overlap."""
    best_page = 1
    best_overlap = 0
    chunk_words = set(chunk_text.lower().split()[:20])  # First 20 words

    for page in pages:
        page_words = set(page["text"].lower().split())
        overlap = len(chunk_words & page_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_page = page["page_number"]

    return best_page


# ─── CRUD Endpoints ────────────────────────────────────────────────


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
):
    """Upload a single document, parse it, and index it into ChromaDB."""
    # Validate file type
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".txt", ".md", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file
    file_path, file_bytes = _save_upload_file(file)
    file_hash = compute_file_hash(file_bytes)

    # Check for exact duplicate
    existing = fetch_one("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
    if existing:
        os.remove(file_path)  # Clean up the saved file
        raise HTTPException(status_code=409, detail="This exact file has already been uploaded.")

    # Create document record
    doc_id = str(uuid.uuid4())
    doc_title = title or os.path.splitext(file.filename)[0]

    execute_query(
        """INSERT INTO documents (id, title, filename, file_path, file_hash, file_size, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (doc_id, doc_title, file.filename, file_path, file_hash, len(file_bytes), "processing"),
    )

    # Run ingestion pipeline
    try:
        chunk_count = _run_ingestion_pipeline(doc_id, file_path, doc_title)
    except Exception as e:
        execute_query(
            "UPDATE documents SET status = %s WHERE id = %s",
            (f"error: {str(e)[:100]}", doc_id),
        )
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # Fetch and return the created document
    doc = fetch_one("SELECT * FROM documents WHERE id = %s", (doc_id,))
    return doc


@router.post("/batch", status_code=201)
async def batch_upload_documents(files: List[UploadFile] = File(...)):
    """Upload multiple documents at once. Each file goes through the full pipeline."""
    results = []
    for file in files:
        try:
            # Reuse the single upload logic
            file.file.seek(0)  # Reset file pointer
            ext = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".txt", ".md", ".csv"}
            if ext not in allowed_extensions:
                results.append({"filename": file.filename, "status": "error", "detail": f"Unsupported file type: {ext}"})
                continue

            file_path, file_bytes = _save_upload_file(file)
            file_hash = compute_file_hash(file_bytes)

            existing = fetch_one("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
            if existing:
                os.remove(file_path)
                results.append({"filename": file.filename, "status": "duplicate"})
                continue

            doc_id = str(uuid.uuid4())
            doc_title = os.path.splitext(file.filename)[0]

            execute_query(
                """INSERT INTO documents (id, title, filename, file_path, file_hash, file_size, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (doc_id, doc_title, file.filename, file_path, file_hash, len(file_bytes), "processing"),
            )

            chunk_count = _run_ingestion_pipeline(doc_id, file_path, doc_title)
            results.append({"filename": file.filename, "status": "completed", "document_id": doc_id, "chunks": chunk_count})

        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "detail": str(e)})

    return {"uploaded": len(results), "results": results}


@router.get("")
async def list_documents(search: Optional[str] = Query(None)):
    """List all documents, with optional debounced search by title."""
    if search:
        docs = fetch_all(
            "SELECT * FROM documents WHERE title ILIKE %s ORDER BY uploaded_at DESC",
            (f"%{search}%",),
        )
    else:
        docs = fetch_all("SELECT * FROM documents ORDER BY uploaded_at DESC")
    return docs


@router.get("/stats")
async def get_stats():
    """Get dashboard summary statistics."""
    from vector_store import get_chunk_count
    total_docs = fetch_one("SELECT COUNT(*) as count FROM documents")
    total_chunks = get_chunk_count()
    total_size = fetch_one("SELECT COALESCE(SUM(file_size), 0) as total FROM documents")

    return {
        "total_documents": total_docs["count"] if total_docs else 0,
        "total_chunks": total_chunks,
        "total_storage_bytes": total_size["total"] if total_size else 0,
    }


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str):
    """Get a single document by ID."""
    doc = fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/{document_id}", response_model=DocumentOut)
async def update_document(document_id: str, update: DocumentUpdate):
    """Update a document's title."""
    doc = fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    execute_query(
        "UPDATE documents SET title = %s WHERE id = %s",
        (update.title, document_id),
    )

    # Update title in ChromaDB metadata too
    # ChromaDB doesn't support metadata-only updates easily,
    # so we just update the PG record. The document_title in search results
    # will be refreshed on next re-index.

    return fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks from both PostgreSQL and ChromaDB."""
    doc = fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Delete chunks from ChromaDB
    delete_by_document_id(document_id)

    # 2. Delete raw file from disk
    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        os.remove(doc["file_path"])

    # 3. Delete from PostgreSQL (cascades to annotations)
    execute_query("DELETE FROM documents WHERE id = %s", (document_id,))

    return {"message": "Document deleted successfully", "document_id": document_id}


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """Download the original raw file."""
    from fastapi.responses import FileResponse

    doc = fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = doc["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(file_path, filename=doc["filename"])
