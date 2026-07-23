"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ─── Document Schemas ───────────────────────────────────────────────

class DocumentOut(BaseModel):
    """Response schema for a document."""
    id: UUID
    title: str
    filename: str
    file_path: str
    file_hash: str
    file_size: int
    page_count: int
    chunk_count: int
    uploaded_at: datetime
    status: str


class DocumentUpdate(BaseModel):
    """Request schema for updating a document's title."""
    title: str = Field(..., min_length=1, max_length=255)


# ─── Chat Schemas ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request schema for a chat query."""
    query: str = Field(..., min_length=1)
    session_id: Optional[UUID] = None
    document_id: Optional[UUID] = None  # For chatting with a specific doc


class CitationSource(BaseModel):
    """A single source citation attached to an LLM response."""
    source_index: int
    document_title: str
    document_id: str
    page_number: Optional[int] = None
    snippet: str


class ChatResponse(BaseModel):
    """Response schema for a chat query."""
    answer: str
    session_id: UUID
    sources: List[CitationSource] = []


class ChatSessionOut(BaseModel):
    """Response schema for a chat session."""
    id: UUID
    title: str
    document_id: Optional[UUID] = None
    created_at: datetime


class ChatMessageOut(BaseModel):
    """Response schema for a chat message."""
    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: list = []
    created_at: datetime


# ─── Annotation Schemas ─────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    """Request schema for creating an annotation."""
    document_id: UUID
    page_number: Optional[int] = None
    highlighted_text: Optional[str] = None
    note: str = Field(..., min_length=1)


class AnnotationOut(BaseModel):
    """Response schema for an annotation."""
    id: UUID
    document_id: UUID
    page_number: Optional[int] = None
    highlighted_text: Optional[str] = None
    note: str
    created_at: datetime
