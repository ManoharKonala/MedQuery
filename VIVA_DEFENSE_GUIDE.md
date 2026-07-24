# 🎓 MedicalQuery RAG — Master Viva, Architecture & Code Defense Guide

This comprehensive reference guide covers every architectural decision, line-of-code rationale, database design, React rendering mechanism, and high-scale system design strategy for the **MedicalQuery RAG System**.

---

## 📑 Table of Contents
1. [System Architecture & Data Flow](#1-system-architecture--data-flow)
2. [Tech Stack Roles & Rationale](#2-tech-stack-roles--rationale)
3. [Database Design & Raw SQL Security](#3-database-design--raw-sql-security)
4. [RAG Pipeline, Chunking & Model Choices](#4-rag-pipeline-chunking--model-choices)
5. [React Frontend Mechanics (`useState`, `useEffect`, `useDebounce`)](#5-react-frontend-mechanics-usestate-useeffect-usedebounce)
6. [FastAPI Async vs Synchronous Processing](#6-fastapi-async-vs-synchronous-processing)
7. [High-Scale System Design (10,000-Page Concurrent PDF Scaling)](#7-high-scale-system-design-10000-page-concurrent-pdf-scaling)
8. [API Endpoints Cheat Sheet](#8-api-endpoints-cheat-sheet)

---

## 1. System Architecture & Data Flow

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
│    (PyPDF2 + EasyOCR 200DPI)                          │    (sentence-transformers)│
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

## 2. Tech Stack Roles & Rationale

| Technology | Layer | Role & Technical Rationale |
|---|---|---|
| **FastAPI** | Backend Framework | Asynchronous Python web framework providing high throughput, automatic OpenAPI documentation (`/docs`), and native threadpool offloading. |
| **PostgreSQL (`pg8000`)** | Relational DB | Pure-Python PostgreSQL driver used with raw SQL (Strictly NO ORM) for high execution speed, zero C-compiler dependencies, and 100% security via parameterized queries (`%s`). |
| **ChromaDB** | Vector Database | Local persistent vector database storing 384-dimensional dense vectors, chunk text, and metadata (`document_id`, `page_number`, `section_header`). |
| **EasyOCR + pdf2image** | OCR Engine | Dual-path OCR renderer at 200 DPI. Guarantees text inside embedded figures, scans, diagrams, and medical charts is extracted without omission. |
| **PyPDF2** | PDF Parser | Direct digital text stream extractor for standard PDF documents. |
| **Microsoft Presidio** | PII Redactor | Anonymizes sensitive PII entities (names, phone numbers, SSNs, medical licenses) prior to embedding generation. Configurable via `ENABLE_PII_REDACTION`. |
| **Datasketch (MinHash LSH)** | Deduplication | Exact SHA-256 file byte hashing + 92% MinHash LSH similarity filtering to prevent duplicate chunks from polluting vector search. |
| **Sentence-Transformers** | Embedding Model | `all-MiniLM-L6-v2` mapping text chunks and query strings into 384-dimensional semantic vector spaces. |
| **Cross-Encoder Reranker** | Reranking Engine | `cross-encoder/ms-marco-MiniLM-L-6-v2` performing joint query-passage scoring to rescore top-20 ChromaDB results down to top-5 most relevant chunks. |
| **Google Gemini (1.5 Flash)** | Primary LLM | Tier-1 LLM for medical answer synthesis and structured `[Source N]` citation generation. |
| **HuggingFace (Mistral-7B)** | Fallback LLM 1 | Tier-2 fallback LLM via Serverless Inference API if Gemini API key expires or hits rate limits. |
| **Extractive Summary Engine** | Fallback LLM 2 | Tier-3 offline fallback producing structured, cited document summaries locally with zero external API dependencies. |
| **React 18 + Vite** | Frontend Framework | Single-page application with modern dark theme (`#071525` navy + `#5CC8E8` cyan accent) using custom `useState`/`useEffect` hooks. |

---

## 3. Database Design & Raw SQL Security

### **Q: Why PostgreSQL and raw `pg8000`? Why NOT an ORM like SQLAlchemy?**
1. **Strict Assignment Compliance:** The assignment explicitly specified raw SQL with `pg8000`.
2. **Performance & Control:** ORMs add significant abstraction overhead (object hydration, lazy-loading queries, hidden SQL execution). Raw SQL with `pg8000` gives **100% explicit control over exact SQL execution plans** and sub-millisecond query performance.
3. **SQL Injection Security:** Security against SQL injection is guaranteed by using **parameterized binding** (`%s` placeholders) across every query in `database.py` and routers:
   ```python
   # SAFE: Parameterized binding prevents SQL injection
   fetch_one("SELECT * FROM documents WHERE id = %s", (document_id,))
   ```

### **Schema Breakdown (`schema.sql` / `database.py`):**
* **`documents` Table:** Stores file metadata (`id`, `title`, `filename`, `file_path`, `file_hash`, `file_size`, `page_count`, `chunk_count`, `uploaded_at`, `status`). Has a `UNIQUE` constraint on `file_hash` (SHA-256) for exact file deduplication.
* **`chat_sessions` Table:** Groups messages into conversations (`id`, `title`, `document_id`, `created_at`). `document_id` references `documents(id) ON DELETE SET NULL`.
* **`chat_messages` Table:** Stores chat history (`id`, `session_id`, `role`, `content`, `sources`, `created_at`). `sources` is stored as a `JSONB` array of citation objects.
* **`document_annotations` Table:** Stores page-specific notes (`id`, `document_id`, `page_number`, `highlighted_text`, `note`, `created_at`).
* **B-Tree Indexes:** Indexes created on `documents(title)`, `documents(file_hash)`, `chat_messages(session_id, created_at)`, and `document_annotations(document_id)` for $O(\log N)$ lookup speed.

---

## 4. RAG Pipeline, Chunking & Model Choices

### **Why Two-Stage Retrieval (Vector Search + Cross-Encoder Reranker)?**
```
Query ──► [all-MiniLM-L6-v2 Embedder] ──► [ChromaDB Vector Search] ──► Top-20 Candidate Chunks
                                                                               │
                                                                               ▼
Answer ◄── [3-Tier LLM Cascade] ◄── Top-5 Reranked Chunks ◄── [ms-marco Cross-Encoder]
```
1. **Stage 1 (Bi-Encoder Vector Search):** Embeddings compute document vector representations independently. It is ultra-fast ($O(1)$ ANN lookups via ChromaDB) and fetches the **Top-20 broad candidate chunks**.
2. **Stage 2 (Cross-Encoder Reranker):** Passes the `(Query, Chunk)` pair simultaneously through self-attention layers, computing exact token-to-token cross-attention to rescore candidates into the **Top-5 ultra-precise chunks**.

### **Hybrid Structure-Enriched Sliding Window Chunking (`chunker.py`):**
* **Header Tracking:** Scans text for Markdown (`#`), ALL-CAPS (`ADVERSE REACTIONS`), or numbered sections (`1.2 Dosage`) to tag chunks with section metadata.
* **Sliding Window:** Groups sentences up to **800 characters (~150 words)** with a **150-character overlap**.
* **Why it beats pure semantic chunking:** Pure semantic chunking on messy OCR text can fail to detect topic shifts and collapse 3 pages into 1 giant un-embeddable chunk. Sliding window guarantees strict upper bounds while sentence overlap prevents context loss across chunk boundaries.

---

## 5. React Frontend Mechanics (`useState`, `useEffect`, `useDebounce`)

### **1. `useDebounce` Hook (`hooks/useDebounce.js`)**
```javascript
export function useDebounce(value, delay = 500) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer); // Cleanup cancels previous timer if value changes within 500ms
  }, [value, delay]);

  return debouncedValue;
}
```
* **Execution Flow:**
  `User types "M"` ➔ Timer 1 (500ms) ➔ `User types "Med"` ➔ Timer 1 Cancelled! Timer 2 (500ms) ➔ `User stops typing` ➔ 500ms passes ➔ `debouncedSearch` updates ➔ API request sent!
* **Why:** Prevents sending 7 separate HTTP requests while typing "Medical". Only 1 request is sent after typing stops.

### **2. `useState` & Button Click Execution (`Chat.jsx`)**
`useState` creates reactive memory. Calling a setter function triggers React to re-render the UI:
```javascript
const [messages, setMessages] = useState([]);
const [inputValue, setInputValue] = useState('');

const handleSend = async () => {
  const query = inputValue.trim();
  if (!query) return;

  // 1. Optimistically add user query & clear input box (UI re-renders immediately)
  setMessages((prev) => [...prev, { role: 'user', content: query, sources: [] }]);
  setInputValue('');

  // 2. HTTP POST call to FastAPI /chat endpoint
  const res = await sendChatMessage(query, activeSessionId);

  // 3. Add AI answer & citations (UI re-renders showing AI response bubble)
  setMessages((prev) => [...prev, { role: 'assistant', content: res.data.answer, sources: res.data.sources }]);
};
```

### **3. `useEffect` Types**
1. **Mount Effect (`useEffect(() => { fetchStats(); }, [])`):** Runs ONCE when page loads to populate Dashboard cards.
2. **Dependency Effect (`useEffect(() => { fetchDocuments(); }, [debouncedSearch])`):** Triggers document search whenever `debouncedSearch` changes.
3. **DOM Effect (`useEffect(() => { scrollRef.current.scrollIntoView(); }, [messages])`):** Smoothly scrolls chat window to bottom when new messages arrive.

---

## 6. FastAPI Async vs Synchronous Processing

### **Q: Why are heavy endpoints (`upload_document`) written as `def` instead of `async def`?**
* **The Mechanism:** 
  In FastAPI, defining an endpoint as `async def` assumes non-blocking I/O. If you put heavy CPU-bound code (like PyTorch neural network inference or EasyOCR) inside `async def`, it **blocks FastAPI's main asyncio event loop**, freezing the entire server.
* **FastAPI Threadpool Offloading:**
  When an endpoint is defined as standard `def`, FastAPI automatically offloads execution to an **external Thread Pool worker** (via `anyio` threadpool). The heavy CPU work runs on a worker thread while the main asyncio event loop remains free to serve concurrent HTTP requests!

---

## 7. High-Scale System Design (10,000-Page Concurrent PDF Scaling)

### **Q: How do you scale this system for multiple users uploading 10,000-page PDFs concurrently without crashing?**

```
[ Client Upload ] ──► [ Object Storage (AWS S3) ]
                              │
                              ▼
                      [ FastAPI Gateway ]
                              │ (Enqueues Job ID)
                              ▼
                      [ Redis Task Queue ]
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
     [ Celery Worker 1 ] [ Celery Worker 2 ] [ Celery Worker N ]
     (Page Streaming)    (Page Streaming)    (Page Streaming)
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                   [ Distributed Vector DB ]
                   (Qdrant / Milvus Cluster)
```

1. **Asynchronous Task Queue (Celery + Redis):** Uploads return a `202 Accepted` status with a `job_id` immediately. PDF processing is offloaded to background Celery worker processes.
2. **Page-by-Page Generator Streaming:** Instead of loading a 10,000-page PDF into RAM at once (which causes Out-Of-Memory OOM crashes), process PDFs using **Python page-by-page generator streams** (10 pages per batch). RAM consumption remains constant ($O(1)$ memory).
3. **Horizontal Worker Scaling:** Scale Celery worker containers horizontally across Kubernetes pods based on CPU/GPU queue depth.
4. **Distributed Vector Database:** Upgrade local ChromaDB to a distributed vector database cluster like **Qdrant or Milvus**, which shards vectors across nodes with HNSW graph indexing for sub-10ms queries over millions of vectors.

---

## 8. API Endpoints Cheat Sheet

| Endpoint | Method | Parameters | Description |
|---|---|---|---|
| `/documents` | `POST` | `file: UploadFile`, `title: Optional[str]` | Uploads single document & runs full ingestion pipeline |
| `/documents/batch` | `POST` | `files: List[UploadFile]` | Batch upload multiple documents |
| `/documents` | `GET` | `search: Optional[str]` | Lists documents with optional debounced title search |
| `/documents/stats` | `GET` | None | Dashboard stats (total docs, chunks, storage bytes) |
| `/documents/{id}` | `DELETE` | `document_id: str` | Deletes document from PostgreSQL & vectors from ChromaDB |
| `/chat` | `POST` | `query: str`, `session_id: Optional[str]`, `document_id: Optional[str]` | Runs 2-stage retrieval + 3-tier LLM cascade |
| `/chat/sessions` | `GET` | None | Lists chat session history |
| `/chat/sessions/{id}/messages` | `GET` | `session_id: str` | Fetches transcript for a chat session |
| `/annotations` | `POST` | `document_id`, `page_number`, `note` | Adds a page annotation note to PostgreSQL |
