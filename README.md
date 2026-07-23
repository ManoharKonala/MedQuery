# 🩺 MedicalQuery RAG — Production-Ready Medical Document Intelligence System

[![FastAPI](https://img.shields.io/badge/FastAPI-005587?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F00?style=for-the-badge)](https://www.trychroma.com/)
[![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

**MedicalQuery RAG** is an end-to-end, production-ready Retrieval-Augmented Generation (RAG) system designed specifically for medical document management, automated parsing, PII redaction, and intelligent Q&A with verifiable source citations.

---

## 🏛️ System Architecture

```
                                  USER INTERFACE (React + Vite)
                                                │
                                    HTTP / REST API (Axios)
                                                │
                                                ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   FASTAPI BACKEND SERVICE                                   │
 └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
┌──────────────────────────┐                             ┌──────────────────────────┐
│   DOCUMENT INGESTION     │                             │   RAG RETRIEVAL & CHAT   │
├──────────────────────────┤                             ├──────────────────────────┤
│ 1. Dual-Path Parser      │                             │ 1. Query Embedder        │
│    (PyPDF2 + EasyOCR 300DPI)                          │    (sentence-transformers)│
│ 2. Deduplication         │                             │ 2. Vector Search         │
│    (SHA-256 + MinHash)   │                             │    (ChromaDB Top-20)     │
│ 3. PII Redaction         │                             │ 3. Cross-Encoder Rerank  │
│    (Presidio + spaCy)    │                             │    (ms-marco-MiniLM Top-5)│
│ 4. Hybrid Chunker        │                             │ 4. 3-Tier LLM Cascade    │
│    (Sliding Window)      │                             │    (Gemini -> HF -> Local)│
│ 5. Batch Embedder        │                             │ 5. Citation Parser       │
│    (all-MiniLM-L6-v2)    │                             │    ([Source N] validation)│
└────────────┬─────────────┘                             └────────────┬─────────────┘
             │                                                        │
             ▼                                                        ▼
┌──────────────────────────┐                             ┌──────────────────────────┐
│  PERSISTENT STORAGE      │                             │   RELATIONAL DATABASE    │
│  ChromaDB Vector Store   │                             │   PostgreSQL (pg8000)    │
│  (Embeddings & Chunks)   │                             │   (Docs, History, Notes) │
└──────────────────────────┘                             └──────────────────────────┘
```

---

## 🛠️ Tech Stack & Technical Roles

| Technology | Layer | Role & Technical Behavior |
|---|---|---|
| **FastAPI** | Backend Framework | High-performance asynchronous REST API handling uploads, streaming, ingestion, and chat. |
| **PostgreSQL (`pg8000`)** | Relational DB | Pure raw SQL driver (Strictly NO ORM) handling document metadata, chat sessions, history, and annotations. Uses parameterized queries (`%s`) for SQL injection security. |
| **ChromaDB** | Vector Database | Local persistent vector index storing 384-dimensional dense vectors, chunk text, and metadata (`document_id`, `page_number`, `section_header`). |
| **EasyOCR + pdf2image** | OCR Engine | Dual-path OCR renderer at 300 DPI. Guarantees text inside embedded figures, scans, diagrams, and medical charts is extracted without omission. |
| **PyPDF2** | PDF Parser | Direct digital text stream extractor for non-scanned PDF documents. |
| **Microsoft Presidio** | PII Redactor | Detects and anonymizes sensitive PII entities (names, phone numbers, SSNs, medical licenses) prior to embedding generation. Includes try-except safety fallback. |
| **Datasketch (MinHash LSH)** | Deduplication | Exact SHA-256 file byte hashing + 92% MinHash LSH similarity filtering to prevent near-duplicate chunks from polluting the vector space. |
| **Sentence-Transformers** | Embedding Model | `all-MiniLM-L6-v2` mapping text chunks and query strings into 384-dimensional semantic vector spaces. |
| **Cross-Encoder Reranker** | Reranking Engine | `cross-encoder/ms-marco-MiniLM-L-6-v2` performing joint query-passage scoring to rescore top-20 ChromaDB results down to the top-5 most relevant chunks. |
| **Google Gemini (1.5 Flash)** | Primary LLM | Tier-1 LLM for medical answer synthesis and structured `[Source N]` citation generation. |
| **HuggingFace (Mistral-7B)** | Fallback LLM 1 | Tier-2 fallback LLM via Serverless Inference API if Gemini API key expires or hits rate limits. |
| **Extractive Summary Engine** | Fallback LLM 2 | Tier-3 offline fallback producing structured, cited document summaries locally with zero external API dependencies. |
| **React 18 + Vite** | Frontend Framework | Interactive single-page application with modern dark theme (`#071525` navy + `#5CC8E8` cyan accent) using custom `useState`/`useEffect` hooks. |
| **Axios** | HTTP Client | Asynchronous API client for batch uploads, document management, and chat session persistence. |

---

## ✨ Core Features

- 📄 **Multi-Format Document Ingestion:** Supports PDFs, scanned documents, PNG/JPG/BMP/WebP images, plain text, and Markdown.
- 🔍 **Dual-Path OCR:** Combines digital text extraction with 300 DPI visual page rendering to capture embedded diagrams and medical test charts.
- 🔒 **PII Redaction:** Presidio-powered anonymization masks sensitive personal and medical identifiers before storing embeddings.
- ⚡ **Hybrid Chunker:** Enforces strict 300–800 character sliding windows with sentence overlap and section header tracking.
- 🎯 **Two-Stage Retrieval:** Vector similarity search (Top-20) followed by Cross-Encoder reranking (Top-5) for precision.
- 🛡️ **3-Tier LLM Fallback Cascade:** Gemini 1.5 Flash ➔ HuggingFace Mistral-7B ➔ Local Extractive Retrieval.
- 💬 **Interactive Chat & Citations:** Real-time conversational memory with clickable `[Source N]` badges and a slide-in source inspection drawer.
- 📊 **Dashboard Analytics:** Document storage metrics, debounced title search (`useDebounce`), batch file upload, and document annotation notes.

---

## 📋 Prerequisites

Before running the application, ensure you have the following installed:

1. **Python 3.10+**
2. **Node.js 18+ & npm**
3. **PostgreSQL 14+** (running locally on port `5432`)
4. **Poppler** (Required for `pdf2image` PDF rendering)
   - **Windows:** `choco install poppler` or download binary and add to System `PATH`
   - **Linux:** `sudo apt-get install poppler-utils`
   - **macOS:** `brew install poppler`

---

## 🚀 Step-by-Step Setup & Running Guide

### 1. Database Setup (PostgreSQL)

Create the PostgreSQL database manually or via `psql`:

```bash
# Connect to PostgreSQL shell
psql -U postgres

# Create database
CREATE DATABASE medicalquery;
\q
```

*(Optional)* Initialize tables manually using the provided schema script:
```bash
psql -U postgres -d medicalquery -f backend/schema.sql
```
*(Note: FastAPI also auto-creates all tables and indexes on first startup).*

---

### 2. Backend Setup & Run

Navigate to the `backend/` directory:

```bash
cd backend
```

Create a virtual environment and activate it:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Create your `.env` file from the provided template:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=medicalquery
DB_USER=postgres
DB_PASSWORD=your_postgres_password

GEMINI_API_KEY=your_google_gemini_api_key
HF_API_KEY=your_huggingface_api_key  # Optional (Fallback Tier 1)
```

Run the backend server:
```bash
uvicorn main:app --reload --port 8000
```
The FastAPI backend will run at **http://localhost:8000** (Interactive API Docs: http://localhost:8000/docs).

---

### 3. Frontend Setup & Run

Open a new terminal window and navigate to `frontend/`:

```bash
cd frontend
```

Install npm dependencies:
```bash
npm install
```

Start the Vite development server:
```bash
npm run dev
```
The application UI will run at **http://localhost:5173**.

---

## 📡 API Reference Overview

| Endpoint | Method | Description |
|---|---|---|
| `/documents` | `POST` | Upload and ingest a single document |
| `/documents/batch` | `POST` | Batch upload multiple documents |
| `/documents` | `GET` | List all uploaded documents (supports `?search=` query) |
| `/documents/stats` | `GET` | Fetch storage and chunk dashboard analytics |
| `/documents/{id}` | `DELETE` | Delete a document and its vectors |
| `/documents/{id}/download` | `GET` | Download raw original file |
| `/chat` | `POST` | RAG query processing (returns answer + citations + session ID) |
| `/chat/sessions` | `GET` | List user chat session history |
| `/chat/sessions/{id}/messages`| `GET` | Fetch full message transcript for a session |
| `/annotations` | `POST` | Add a note or highlight to a document page |

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
