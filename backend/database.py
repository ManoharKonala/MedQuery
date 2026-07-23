"""
PostgreSQL database connection and raw SQL helpers using pg8000.
No ORM — all queries use parameterized raw SQL for security.
"""

import pg8000
import uuid
from contextlib import contextmanager
from config import settings


def get_connection():
    """Create a new pg8000 connection to PostgreSQL."""
    return pg8000.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


@contextmanager
def get_db():
    """Context manager for database transactions.
    Auto-commits on success, auto-rolls-back on error.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(sql: str, params: tuple = None):
    """Execute a write query (INSERT, UPDATE, DELETE) with parameterized inputs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        return cursor.rowcount


def fetch_one(sql: str, params: tuple = None):
    """Execute a read query and return a single row as a dict."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        if row:
            return dict(zip(columns, row))
        return None


def fetch_all(sql: str, params: tuple = None):
    """Execute a read query and return all rows as a list of dicts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def init_tables():
    """Create all required tables if they don't exist.
    Called once on application startup.
    """
    sql = """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- 1. Documents Metadata Table
    CREATE TABLE IF NOT EXISTS documents (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        title VARCHAR(255) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        file_path VARCHAR(512) NOT NULL,
        file_hash VARCHAR(64) UNIQUE NOT NULL,
        file_size BIGINT NOT NULL,
        page_count INT DEFAULT 0,
        chunk_count INT DEFAULT 0,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'processing'
    );

    -- 2. Chat Sessions Table
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
        document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. Chat Messages History Table
    CREATE TABLE IF NOT EXISTS chat_messages (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        sources JSONB DEFAULT '[]'::jsonb,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Document Annotations Table
    CREATE TABLE IF NOT EXISTS document_annotations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
        page_number INT,
        highlighted_text TEXT,
        note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
    CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id, created_at ASC);
    CREATE INDEX IF NOT EXISTS idx_document_annotations_doc_id ON document_annotations(document_id);
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
    print("[DB] All tables and indexes initialized successfully.")

