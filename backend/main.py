"""
MedicalQuery RAG — FastAPI Application Entry Point.
Initializes the app, CORS, startup events, and includes all routers.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ──
    print("=" * 60)
    print("  MedicalQuery RAG — Starting Up")
    print("=" * 60)

    # Create upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)
    print(f"[Startup] Upload directory: {os.path.abspath(settings.upload_dir)}")

    # Initialize database tables
    try:
        init_tables()
    except Exception as e:
        print(f"[Startup] WARNING: Database init failed: {e}")
        print("[Startup] Make sure PostgreSQL is running and credentials are correct.")

    # Pre-warm Embedding Model, Reranker, and ChromaDB on Startup
    try:
        from embeddings import get_model
        from reranker import get_reranker
        from vector_store import get_collection

        print("[Startup] Pre-warming embedding model...")
        get_model()

        print("[Startup] Pre-warming reranker model...")
        get_reranker()

        print("[Startup] Pre-warming ChromaDB collection...")
        get_collection()
    except Exception as e:
        print(f"[Startup] WARNING: Pre-warming failed: {e}")


    print("=" * 60)
    print("  MedicalQuery RAG — Ready!")
    print("=" * 60)

    yield

    # ── Shutdown ──
    print("[Shutdown] MedicalQuery RAG shutting down.")


# ── Create FastAPI App ──
app = FastAPI(
    title="MedicalQuery RAG API",
    description="A production-ready RAG system for medical document management and intelligent Q&A.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Routers ──
from routers.documents import router as documents_router
from routers.chat import router as chat_router
from routers.annotations import router as annotations_router

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(annotations_router)


# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "MedicalQuery RAG"}


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "MedicalQuery RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
