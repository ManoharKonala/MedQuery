"""
Chat API routes.
Handles RAG queries, chat sessions, and conversational memory.
"""

import uuid
import json
from fastapi import APIRouter, HTTPException
from typing import Optional

from database import execute_query, fetch_one, fetch_all
from schemas import ChatRequest, ChatResponse, ChatSessionOut, ChatMessageOut
from embeddings import generate_embedding
from retriever import retrieve_and_rerank
from llm import generate_answer

router = APIRouter(prefix="/chat", tags=["Chat"])


def _get_or_create_session(session_id: str = None, document_id: str = None) -> str:
    """Get an existing chat session or create a new one."""
    if session_id:
        existing = fetch_one("SELECT id FROM chat_sessions WHERE id = %s", (session_id,))
        if existing:
            return str(existing["id"])

    # Create a new session
    new_id = str(uuid.uuid4())
    execute_query(
        "INSERT INTO chat_sessions (id, title, document_id) VALUES (%s, %s, %s)",
        (new_id, "New Conversation", str(document_id) if document_id else None),
    )
    return new_id


def _get_chat_history(session_id: str, limit: int = 6) -> list[dict]:
    """Fetch recent chat messages for conversational context."""
    messages = fetch_all(
        """SELECT role, content FROM chat_messages
           WHERE session_id = %s
           ORDER BY created_at DESC
           LIMIT %s""",
        (session_id, limit),
    )
    # Reverse to get chronological order
    return list(reversed(messages))


def _save_message(session_id: str, role: str, content: str, sources: list = None):
    """Save a chat message to PostgreSQL."""
    msg_id = str(uuid.uuid4())
    sources_json = json.dumps(sources or [])
    execute_query(
        """INSERT INTO chat_messages (id, session_id, role, content, sources)
           VALUES (%s, %s, %s, %s, %s::jsonb)""",
        (msg_id, session_id, role, content, sources_json),
    )


def _update_session_title(session_id: str, query: str):
    """Update session title based on the first user query."""
    session = fetch_one("SELECT title FROM chat_sessions WHERE id = %s", (session_id,))
    if session and session["title"] == "New Conversation":
        # Use the first 50 chars of the first query as the title
        title = query[:50] + "..." if len(query) > 50 else query
        execute_query(
            "UPDATE chat_sessions SET title = %s WHERE id = %s",
            (title, session_id),
        )


# ─── Chat Endpoints ───────────────────────────────────────────────


@router.post("", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """Process a RAG query: embed → search → rerank → generate → cite.

    Supports:
    - General queries across all documents
    - Document-specific queries (filtered by document_id)
    - Conversational follow-ups (using session_id for history)
    """
    query = request.query
    session_id = _get_or_create_session(
        str(request.session_id) if request.session_id else None,
        request.document_id,
    )

    # Update session title if it's a new conversation
    _update_session_title(session_id, query)

    # Save user message
    _save_message(session_id, "user", query)

    # 1. Retrieve and rerank relevant chunks
    reranked_chunks = retrieve_and_rerank(query, request.document_id, top_k=5)

    # 5. Get chat history for conversational context
    chat_history = _get_chat_history(session_id)

    # 6. Generate answer with Gemini
    result = generate_answer(query, reranked_chunks, chat_history)

    # 7. Save assistant response
    _save_message(session_id, "assistant", result["answer"], result["sources"])

    return ChatResponse(
        answer=result["answer"],
        session_id=session_id,
        sources=result["sources"],
    )


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions():
    """List all chat sessions, most recent first."""
    sessions = fetch_all(
        "SELECT * FROM chat_sessions ORDER BY created_at DESC"
    )
    return sessions


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_session_messages(session_id: str):
    """Get all messages in a chat session."""
    session = fetch_one("SELECT id FROM chat_sessions WHERE id = %s", (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = fetch_all(
        """SELECT * FROM chat_messages
           WHERE session_id = %s
           ORDER BY created_at ASC""",
        (session_id,),
    )

    # Parse JSONB sources field
    for msg in messages:
        if isinstance(msg.get("sources"), str):
            try:
                msg["sources"] = json.loads(msg["sources"])
            except (json.JSONDecodeError, TypeError):
                msg["sources"] = []

    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    session = fetch_one("SELECT id FROM chat_sessions WHERE id = %s", (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    execute_query("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
    return {"message": "Session deleted", "session_id": session_id}
