-- ==========================================
-- MedicalQuery RAG Database Schema
-- Target: PostgreSQL 14+
-- Driver: pg8000 (Raw SQL)
-- ==========================================

-- Enable UUID extension for generating primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------
-- 1. Documents Metadata Table
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 for exact deduplication
    file_size BIGINT NOT NULL,
    page_count INT DEFAULT 0,
    chunk_count INT DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'processing'
);

-- Index for debounced title search
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
-- Index for file hash lookup
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);


-- ------------------------------------------
-- 2. Chat Sessions Table
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for session listing
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC);


-- ------------------------------------------
-- 3. Chat Messages History Table
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,  -- Array of citation metadata objects
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for retrieving conversational memory by session
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id, created_at ASC);


-- ------------------------------------------
-- 4. Document Annotations Table
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS document_annotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT,
    highlighted_text TEXT,
    note TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for document annotations
CREATE INDEX IF NOT EXISTS idx_document_annotations_doc_id ON document_annotations(document_id);
