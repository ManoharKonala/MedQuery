# MedicalQuery RAG System - Codebase Deep Dive

This document provides a comprehensive, file-by-file, in-depth explanation of every single file in the MedicalQuery RAG system. It covers both the backend (FastAPI, PostgreSQL, ChromaDB, NLP) and the frontend (React, Vite).

---

## 🏗️ Backend

The backend is built with FastAPI and is responsible for document ingestion, vector storage, natural language processing, LLM generation, and serving APIs.

### 1. `backend/config.py`
**Purpose:** Centralized configuration management.
**In-Depth Explanation:**
This file uses `pydantic-settings` to load environment variables and provide typed access to configuration values. It handles credentials, model names, and system paths.
- **Model Caching Logic:** At the top of the file, it dynamically resolves a path for `models_cache_dir` inside the `backend` directory. It sets the `HF_HOME` and `SENTENCE_TRANSFORMERS_HOME` environment variables to this directory. This forces all Hugging Face models (like the embedding model and the cross-encoder reranker) to download into the local project directory instead of the system cache. This prevents cold starts and allows you to zip up the project and move it to another device without re-downloading models.
- **Configuration Fields:** Defines database connection parameters (`db_host`, `db_port`, etc.), PII redaction toggle (`enable_pii_redaction`), LLM keys (`gemini_api_key`, `hf_api_key`), Hugging Face fallback model (`hf_model`), embedding/reranker model names, and paths for uploaded documents and ChromaDB persistence.

### 2. `backend/main.py`
**Purpose:** Application entry point and startup manager.
**In-Depth Explanation:**
This file instantiates the FastAPI application and defines the application lifecycle.
- **Lifespan Context Manager (`lifespan`)**: This asynchronous function runs before the server starts accepting requests. 
    1. It creates the document `upload_dir`.
    2. It calls `init_tables()` to ensure PostgreSQL tables are created.
    3. **Pre-warming Models:** It calls `get_model()`, `get_reranker()`, and `get_collection()` to load the embedding model, reranker, and ChromaDB collection into RAM *before* the first user request. This eliminates the "cold start" latency for the first API call.
- **App Configuration:** Adds `CORSMiddleware` to allow requests from the React frontend (`localhost:5173`). 
- **Router Registration:** Includes the `documents_router`, `chat_router`, and `annotations_router` so that all modular API endpoints are registered under the main application.

### 3. `backend/database.py`
**Purpose:** PostgreSQL database connection and raw SQL helper utilities.
**In-Depth Explanation:**
This file uses `pg8000` (a pure Python PostgreSQL driver) instead of an ORM (like SQLAlchemy). This provides low-level control over queries and ensures high performance.
- **`get_connection()` & `get_db()`:** Defines a context manager that automatically handles committing transactions on success or rolling them back if an error occurs. It yields a raw cursor.
- **Query Helpers:** 
    - `execute_query(sql, params)`: Used for INSERT, UPDATE, and DELETE operations. Returns the number of affected rows. Parameterized inputs (`%s`) prevent SQL injection attacks.
    - `fetch_one` / `fetch_all`: Used for SELECT queries. They fetch raw tuples from `pg8000` and zip them with the column names (`cursor.description`) to return clean Python dictionaries.
- **`init_tables()`:** Defines the schema for the application using raw DDL. It creates the `documents`, `chat_sessions`, `chat_messages`, and `document_annotations` tables. It also defines foreign keys with `ON DELETE CASCADE` and sets up indexes (e.g., on `file_hash` for deduplication).

### 4. `backend/schemas.py`
**Purpose:** Pydantic schemas for data validation.
**In-Depth Explanation:**
Provides strict validation for data entering and leaving the API. FastAPI uses these schemas to auto-generate Swagger UI documentation (`/docs`) and to automatically parse JSON bodies.
- Defines schemas for Documents (`DocumentOut`, `DocumentUpdate`), Chat requests/responses (`ChatRequest`, `ChatResponse`), and Annotations.
- Defines `CitationSource` to structure how citations are returned from the LLM back to the frontend.

### 5. `backend/ocr_parser.py`
**Purpose:** Universal document parser with smart OCR routing.
**In-Depth Explanation:**
This file handles extracting text from PDFs, Images, and Text files. It employs a highly optimized "dual-path" strategy for PDFs.
- **Smart Decision Logic (`_extract_text_from_pdf`)**: Iterates through PDF pages. It extracts the raw digital text using `PyPDF2`. It checks if the digital text is sparse (less than 50 chars) or if the page contains embedded image objects (`_page_has_images`). 
- **Selective OCR**: If the page has rich digital text, it skips OCR entirely (instant extraction). If the page is sparse or has images, it uses `pdf2image` to render the page to a PNG at 200 DPI (which is 2.25x faster than 300 DPI without losing accuracy). It then runs EasyOCR on the image.
- **Merging**: If OCR finds text inside an embedded figure, it merges the digital text with the OCR text.
- **Hardware Acceleration**: `_get_ocr_reader()` uses `torch.cuda.is_available()` to automatically detect if a GPU is present and assigns EasyOCR to the GPU, dramatically speeding up text extraction.

### 6. `backend/chunker.py`
**Purpose:** Structure-enriched sliding window text chunking.
**In-Depth Explanation:**
Breaks down long documents into smaller blocks (chunks) so they can fit into the embedding model's context window.
- **Semantic Tracking (`_is_header`)**: Uses Regex to detect Markdown headers (`#`) or ALL-CAPS lines (e.g., `ADVERSE REACTIONS`). It remembers the most recently seen header.
- **Sliding Window:** Tokenizes the text into sentences using `nltk.sent_tokenize`. It builds chunks sentence by sentence until reaching `TARGET_CHUNK_SIZE` (800 chars). 
- **Context Preservation:** When starting a new chunk, it includes overlapping sentences (`OVERLAP_SIZE` of 150 chars) from the previous chunk. This ensures concepts aren't cut in half.
- **Metadata Tagging:** Attaches the active `section_header` to the chunk. This ensures that even if a chunk is deep in a section, the LLM knows what section it belongs to.

### 7. `backend/dedup.py`
**Purpose:** Deduplication engine for files and chunks.
**In-Depth Explanation:**
Prevents duplicate data from wasting vector database space and skewing search results.
- **Exact File Deduplication (`compute_file_hash`)**: Hashes the raw bytes of an uploaded file using SHA-256. This allows the system to reject identical files instantly upon upload.
- **Near-Duplicate Chunk Detection (`is_near_duplicate_chunk`)**: Uses Locality Sensitive Hashing (LSH) via the `datasketch` library (`MinHash`). It generates 3-word shingles for a chunk and computes a MinHash signature. If a chunk has a high similarity (threshold 0.92) to an existing chunk, it is classified as a duplicate and dropped.

### 8. `backend/embeddings.py`
**Purpose:** Vector representation generator.
**In-Depth Explanation:**
Uses `sentence-transformers` to convert text chunks into high-dimensional vectors (arrays of floats).
- **Lazy Loading**: `get_model()` only instantiates the model when first needed, caching it globally in `_model`.
- **Model**: Uses `all-MiniLM-L6-v2`, a fast and efficient bi-encoder model that produces 384-dimensional vectors.
- **Batch Processing (`generate_embeddings_batch`)**: Takes a list of texts and embeds them simultaneously using `batch_size=32`. This is significantly faster than embedding chunks one by one in a loop.

### 9. `backend/vector_store.py`
**Purpose:** Persistent ChromaDB management.
**In-Depth Explanation:**
Manages the vector database where document chunks and their embeddings are stored for fast semantic search.
- **Persistence**: Initializes a `chromadb.PersistentClient` pointing to a local directory (`./chroma_db`). This means no external database server is required.
- **Cosine Similarity**: Configures the collection to use `cosine` distance (`"hnsw:space": "cosine"`), which is optimal for semantic embeddings.
- **CRUD Operations**: Provides methods to add chunks (`add_chunks`), search based on a query vector (`search`), and delete chunks belonging to a specific document (`delete_by_document_id`).

### 10. `backend/retriever.py`
**Purpose:** The RAG retrieval pipeline.
**In-Depth Explanation:**
Orchestrates the search process. When a user asks a question, this file finds the best document chunks to answer it.
1. **Embedding**: Embeds the user's query into a vector.
2. **Broad Search**: Queries ChromaDB to find the top 20 candidate chunks based on cosine similarity.
3. **Reranking**: Passes those 20 chunks to the Cross-Encoder (`rerank` from `reranker.py`) to score them with high precision, returning the top 5 absolute best chunks to feed to the LLM.

### 11. `backend/reranker.py`
**Purpose:** Cross-encoder relevance scoring.
**In-Depth Explanation:**
Bi-encoders (like the embedding model) are fast but compare vectors independently. Cross-encoders are slower but compare the query and the chunk simultaneously, allowing for deep attention mechanisms to assess relevance.
- Uses `cross-encoder/ms-marco-MiniLM-L-6-v2`. 
- **`rerank()`**: Takes the user's query and the broad search chunks. It creates pairs `(query, chunk_text)` and predicts a relevance score for each pair. It sorts the chunks by this score and returns the Top-K.

### 12. `backend/pii_redactor.py`
**Purpose:** Microsoft Presidio-based sensitive data anonymization.
**In-Depth Explanation:**
Ensures that sensitive patient data is not stored in the vector database or sent to external LLMs.
- Initializes the `AnalyzerEngine` and `AnonymizerEngine` from `presidio`.
- **`redact_pii()`**: Scans text for entities like `PHONE_NUMBER`, `EMAIL_ADDRESS`, `US_SSN`, `PERSON`, and `DATE_TIME`. It replaces them with tags (e.g., `<PERSON>`).
- Includes a graceful fallback: if Presidio fails to load (e.g., missing spaCy models) or if it's toggled off in `config.py`, it safely returns the un-redacted text without crashing the pipeline.

### 13. `backend/llm.py`
**Purpose:** Answer generation and citation parsing using a 3-Tier Fallback Cascade.
**In-Depth Explanation:**
This file handles constructing the prompt and calling LLMs to answer the user's question based on retrieved context.
- **Prompt Engineering (`_build_rag_prompt`)**: Constructs a strict prompt injecting the system instructions, the user's query, chat history, and the retrieved source chunks labeled as `[Source 1]`, `[Source 2]`, etc.
- **Tier 1 (Google Gemini)**: Attempts to use the `google.generativeai` SDK (`gemini-1.5-flash`). This is the most capable model for reasoning and rephrasing.
- **Tier 2 (Hugging Face Mistral)**: If Gemini fails (e.g., API limit, invalid key), it catches the exception and falls back to making an HTTP POST request to the Hugging Face Serverless Inference API for `Mistral-7B-Instruct`.
- **Tier 3 (Local Extractive Fallback)**: If both remote APIs fail, it falls back to a 100% local, offline mechanism. It takes the top 3 retrieved chunks and formats them directly into a markdown response, bypassing generative AI entirely while still providing the user with the most relevant text.
- **Citation Parsing (`_parse_citations`)**: Uses regex to extract `[Source N]` tags from the LLM's output. It matches these numbers back to the metadata of the provided chunks to construct formal `CitationSource` objects containing the document title, page number, and snippet.

### 14. `backend/routers/documents.py`
**Purpose:** API endpoints for document CRUD and the ingestion pipeline.
**In-Depth Explanation:**
Defines all HTTP routes prefixed with `/documents`.
- **`upload_document` / `batch_upload_documents`**: Receives raw files via `UploadFile`. It saves the file to disk, computes a hash to reject exact duplicates, and inserts a pending record into PostgreSQL.
- **`_run_ingestion_pipeline`**: This internal function acts as the conductor for the document processing symphony. It takes a saved file and routes it sequentially through: 
    `parse_document()` (OCR) -> `chunk_text()` -> `redact_pii_batch()` -> `filter_duplicate_chunks()` -> `generate_embeddings_batch()` -> `add_chunks()` (ChromaDB). Finally, it marks the document as "completed" in PostgreSQL.
- **CRUD Operations**: Includes endpoints to list documents (`GET /`), get stats (`GET /stats`), rename (`PUT /{id}`), delete (`DELETE /{id}` which cascades to ChromaDB and local disk), and download the raw file (`GET /{id}/download`).

### 15. `backend/routers/chat.py`
**Purpose:** API endpoints for the chat interface.
**In-Depth Explanation:**
Manages chat state and triggers the retrieval generation process.
- **`chat_query`**: Receives a user query. It looks up or creates a `chat_session` in the DB. It saves the user's message to `chat_messages`. It triggers `retrieve_and_rerank()` from the retriever, gets history, and calls `generate_answer()` from the LLM module. Finally, it saves the assistant's response (along with JSON-serialized citations) back to the database.
- **Session Management**: Includes endpoints to list past sessions (`GET /sessions`), load messages for a specific session (`GET /sessions/{id}/messages`), and delete sessions.

### 16. `backend/routers/annotations.py`
**Purpose:** API endpoints for manual document annotations.
**In-Depth Explanation:**
Provides endpoints to add, retrieve, and delete highlights or notes on specific pages of a document using the `document_annotations` table in PostgreSQL.

---

## 🎨 Frontend

The frontend is a modern React Single Page Application (SPA) built with Vite. It features a responsive, dark-mode glassmorphism UI.

### 17. `frontend/src/App.jsx`
**Purpose:** Root component and Router configuration.
**In-Depth Explanation:**
Defines the main layout shell of the application.
- Uses `BrowserRouter` from `react-router-dom` to handle client-side routing.
- Contains the static `<aside>` navigation sidebar containing links to the Documents and Chat pages.
- The `<main>` content area hosts a `<Routes>` block that conditionally renders `Dashboard.jsx` or `Chat.jsx` depending on the current URL path. It supports dynamic routes like `/chat/:sessionId`.

### 18. `frontend/src/api.js`
**Purpose:** Axios HTTP client configuration.
**In-Depth Explanation:**
Centralizes all external network calls to the FastAPI backend.
- Creates an Axios instance (`api`) pointing to `http://localhost:8000`.
- Exports individual asynchronous wrapper functions for every backend endpoint (e.g., `getDocuments`, `uploadDocument`, `sendChatMessage`). This abstracts away the HTTP layer from the React components.

### 19. `frontend/src/hooks/useDebounce.js`
**Purpose:** Custom React hook for input debouncing.
**In-Depth Explanation:**
Debouncing ensures that a function is not called too rapidly.
- Takes a `value` (like a search string) and a `delay` (in ms).
- Uses `useEffect` and `setTimeout`. When the user types, the effect triggers and starts a timer. If the user types again before the timer ends, the dependency array `[value, delay]` causes the effect to re-run, running the cleanup function (`clearTimeout`), which cancels the previous timer and starts a new one.
- Only when the user stops typing for `delay` milliseconds does the `setDebouncedValue` trigger. This prevents the Dashboard from spamming the backend with API requests for every single keystroke.

### 20. `frontend/src/pages/Dashboard.jsx`
**Purpose:** Document Management Interface.
**In-Depth Explanation:**
This complex component handles uploading, listing, and managing documents.
- **State Management**: Uses `useState` to track the document list, statistics, uploading status, drag-and-drop state, and modal visibility for editing titles.
- **Search Logic**: Hooks the `searchQuery` state into `useDebounce`. A `useEffect` watches the `debouncedSearch` value. When it changes, it triggers `fetchDocuments()`. This allows real-time, spam-free searching.
- **Drag & Drop**: Implements `onDragOver`, `onDragLeave`, and `onDrop` events on a custom drop zone div. When files are dropped, it prevents the default browser behavior (which would normally open the file) and passes the `File` objects to the `handleFileUpload` function.
- **Upload Progress**: Supports batch uploading. It sets `isUploading` to true, triggering a spinner, calls the batch upload API, and upon completion, re-fetches the document list and statistics to update the UI reactively.
- **Rendering**: Maps over the `documents` array to render an HTML `<table>`. It includes helper functions to format file sizes (`formatBytes`) and render styled pill badges for file types and statuses.

### 21. `frontend/src/pages/Chat.jsx`
**Purpose:** Conversational RAG Interface.
**In-Depth Explanation:**
Handles the real-time chat interface, session history, and citation rendering.
- **State Management**: Tracks `messages` (an array of message objects), `sessions` (the sidebar history), `inputValue` (controlled input), and `isLoading` (for the typing indicator).
- **Auto-scroll**: Uses a `useRef` (`messagesEndRef`) placed at the bottom of the message list. A `useEffect` watches the `messages` array; whenever a new message is added, it calls `scrollIntoView({ behavior: 'smooth' })`.
- **Optimistic UI (`handleSend`)**: When a user sends a message, it immediately updates the `messages` state with the user's text and clears the input box. *Then* it awaits the API response. This makes the UI feel instantly responsive.
- **Citation Rendering (`renderMessageContent`)**: The LLM returns text like "The patient has a fever [Source 1]". This function uses a Regex `split` to find `[Source N]` strings. It replaces those specific strings with a clickable React `<span>` component (the citation badge).
- **Citation Drawer**: When a citation badge is clicked, `openCitations` updates the `activeCitations` state and sets `showCitationDrawer` to true. This triggers a CSS translation to slide out a side-panel. It uses an accordion pattern (`expandedCitationIndex` state) to allow expanding/collapsing individual source snippets.

### 22. `frontend/src/index.css`
**Purpose:** Global stylesheet and design system.
**In-Depth Explanation:**
This file implements the custom dark-mode glassmorphism design.
- **CSS Variables**: Defines a strict design token system using `:root`. It sets colors like `--bg-primary` (dark navy), `--accent` (cyan), and handles translucent properties for glass effects (`--bg-glass`, `--border-glass`).
- **Glassmorphism**: Achieved using `backdrop-filter: blur(20px)` and semi-transparent `rgba` background colors on components like `.glass-card` and `.citation-drawer`.
- **Animations**: Defines `@keyframes` for smooth UI interactions, including `messageSlideIn` (messages popping up), `fadeIn` (modals appearing), and `typing-dot` (the bouncing dots while waiting for the LLM).
- **Flexbox & CSS Grid**: Uses modern layout tools heavily. For instance, `.app-layout` is a Flex container taking `100vh`, while `.stats-grid` uses `grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))` for automatic responsiveness.

### 23. `frontend/vite.config.js` & `frontend/main.jsx`
**Purpose:** Build configuration and React mount point.
**In-Depth Explanation:**
- **`vite.config.js`**: Configures Vite, the fast modern build tool replacing Webpack. It imports the `@vitejs/plugin-react` plugin to support JSX compilation and Fast Refresh during development.
- **`main.jsx`**: The standard React entry point. It targets the `<div id="root">` element in `index.html` and renders the `<App />` component, wrapping it in `<React.StrictMode>` to catch potential side-effects and deprecations in development.
