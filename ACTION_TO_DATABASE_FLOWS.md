# MedicalQuery: Complete Action-to-Database Flows

This document maps **every single functionality** in the entire application. It traces exactly what happens when you click a button on the screen, how React handles the render, which API is triggered, which backend file processes it, and the exact SQL queries that run against the database. 

If anyone points to a feature on the screen and asks "How does this work?", you will find the exact step-by-step lifecycle here.

---

## 1. Feature: Initial Dashboard Load (Viewing the Table)
**The User Action:** You open `http://localhost:5173/` in your browser.
**1. The React Execution (`Dashboard.jsx`):**
- The `<Dashboard />` component mounts to the screen. 
- React immediately runs the `useEffect(..., [])` hook.
- Inside the hook, it calls two functions: `fetchDocuments()` and `fetchStats()`. 
- State variables `isLoading` and `isStatsLoading` are set to `true`, causing React to draw skeleton loaders on the screen.
**2. The API Hit (`api.js`):**
- Axios sends HTTP requests: `GET /documents` and `GET /documents/stats`.
**3. The Backend Process (`routers/documents.py`):**
- FastAPI routes the requests to `get_documents()` and `get_document_stats()`.
**4. The Database Queries (`database.py`):**
- For the list: `execute_query("SELECT id, title, filename, status, created_at, file_size FROM documents ORDER BY created_at DESC")`
- For stats: `execute_query("SELECT COUNT(*) as total_docs, SUM(file_size) as total_size FROM documents")`
**5. The Final Render:**
- The Backend returns JSON arrays.
- React receives the data and calls `setDocuments(data)`.
- `isLoading` becomes `false`. React's Virtual DOM iterates over the `documents` array using `.map()` and draws a `<tr>` (table row) for every document in the database.

---

## 2. Feature: Searching / Filtering Documents
**The User Action:** You type "Blood Test" into the Dashboard search bar.
**1. The React Execution (`Dashboard.jsx` & `useDebounce.js`):**
- Every time you type a letter, the `searchQuery` state updates.
- The `useDebounce` hook intercepts this. It waits 500 milliseconds after you *stop* typing before updating a hidden state variable called `debouncedSearch`.
- A `useEffect` watching `debouncedSearch` triggers a new `fetchDocuments(searchQuery)`.
**2. The API Hit:**
- Axios sends: `GET /documents?search=Blood%20Test`.
**3. The Backend Process (`routers/documents.py`):**
- FastAPI detects the optional `search` query parameter.
**4. The Database Queries (`database.py`):**
- It executes a parameterized fuzzy search: 
  `SELECT * FROM documents WHERE title ILIKE %s OR filename ILIKE %s` (where `%s` is `%Blood Test%`).
**5. The Final Render:**
- The Backend returns the filtered JSON list.
- React calls `setDocuments(filteredData)`, and the table instantly shrinks to only show matching rows without reloading the browser page.

---

## 3. Feature: Uploading a Document (The Ingestion Pipeline)
**The User Action:** You drag and drop a PDF into the dotted box.
**1. The React Execution (`Dashboard.jsx`):**
- The `onDrop` event fires. React calls `setIsUploading(true)`, replacing the upload icon with a spinning loader.
- It packages the binary file into a `FormData` object.
**2. The API Hit (`api.js`):**
- Axios sends: `POST /documents/batch` with `Content-Type: multipart/form-data`.
**3. The Backend Process (`routers/documents.py` & Ingestion Engine):**
- **Save to disk:** FastAPI streams the file into the `uploads/` folder.
- **Deduplication (`dedup.py`):** Hashes the file to prevent duplicates.
- **OCR Parsing (`ocr_parser.py`):** Converts the PDF to text (using EasyOCR and PyTorch GPU if it's an image/scan).
- **Chunking (`chunker.py`):** Slices the text into 800-character overlapping blocks.
- **PII Redaction (`pii_redactor.py`):** Uses Microsoft Presidio (AI) to mask names and phone numbers.
- **Embeddings (`embeddings.py`):** Converts the text into 384-dimension vectors.
**4. The Database Queries:**
- **PostgreSQL (`database.py`):** `INSERT INTO documents (id, title, filename, status) VALUES (...)` (Initial status is 'processing').
- **ChromaDB (`vector_store.py`):** `collection.add(ids, documents, embeddings, metadatas)`.
- **PostgreSQL (Update):** `UPDATE documents SET status = 'completed' WHERE id = %s`.
**5. The Final Render:**
- Backend returns a `201 Created` JSON response.
- React receives success, triggers `fetchDocuments()` again, and the new file appears in the table with a green "Completed" badge.

---

## 4. Feature: Deleting a Document
**The User Action:** You click the red Trash Can icon next to a document.
**1. The React Execution (`Dashboard.jsx`):**
- React opens a confirmation prompt. If you click Yes, it calls `api.deleteDocument(id)`.
- It dynamically removes the item from the UI by filtering the state: `setDocuments(docs.filter(d => d.id !== id))` so the row vanishes instantly.
**2. The API Hit:**
- Axios sends: `DELETE /documents/{id}`.
**3. The Backend Process (`routers/documents.py`):**
- FastAPI receives the ID.
- It deletes the physical file from the `uploads/` folder using Python's `os.remove()`.
- It tells ChromaDB (`vector_store.py`) to purge all vectors belonging to this document: `collection.delete(where={"document_id": id})`.
**4. The Database Queries (`database.py`):**
- `DELETE FROM documents WHERE id = %s`
**5. The Final Render:**
- The row is already gone from the React UI (Optimistic UI), but if the backend fails, React would show a toast error notification.

---

## 5. Feature: Renaming a Document
**The User Action:** You click the Pencil icon to edit a document's title.
**1. The React Execution (`Dashboard.jsx`):**
- React sets `editingDocId` state, which turns the static text in that specific table row into an `<input>` text field.
- You type a new name and press Save.
**2. The API Hit:**
- Axios sends: `PUT /documents/{id}` with JSON body `{"title": "New Title"}`.
**3. The Backend Process (`routers/documents.py`):**
- FastAPI validates the payload using Pydantic `DocumentUpdate` schema.
**4. The Database Queries (`database.py`):**
- `UPDATE documents SET title = %s WHERE id = %s`.
**5. The Final Render:**
- React updates the local state array with the new title, and the `<input>` field turns back into static text.

---

## 6. Feature: Loading the Chat Sidebar (Sessions)
**The User Action:** You click "Chat" in the main navigation sidebar.
**1. The React Execution (`App.jsx` & `Chat.jsx`):**
- React Router dynamically swaps the `<Dashboard>` component out for the `<Chat>` component.
- The `Chat.jsx` `useEffect` fires immediately, calling `fetchSessions()`.
**2. The API Hit:**
- Axios sends: `GET /chat/sessions`.
**3. The Backend Process (`routers/chat.py`):**
- FastAPI catches the route.
**4. The Database Queries (`database.py`):**
- `SELECT id, title, created_at FROM chat_sessions ORDER BY created_at DESC LIMIT 50`.
**5. The Final Render:**
- React iterates over the sessions array and draws the clickable history list on the left side of the chat screen.

---

## 7. Feature: Selecting an Existing Chat Session
**The User Action:** You click a past conversation (e.g., "Heart Rate Inquiry") in the sidebar.
**1. The React Execution (`Chat.jsx`):**
- The `onClick` handler updates the `activeSessionId` state variable.
- React detects this state change and clears the current `messages` state (showing a blank chat window).
- It calls `fetchMessages(sessionId)`.
**2. The API Hit:**
- Axios sends: `GET /chat/sessions/{sessionId}/messages`.
**3. The Backend Process (`routers/chat.py`):**
- FastAPI catches the route and extracts the UUID from the URL.
**4. The Database Queries (`database.py`):**
- `SELECT role, content, citations FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC`.
**5. The Final Render:**
- React receives the array of past messages (both 'user' and 'assistant' roles). It sets the `messages` state. The UI instantly populates with the entire conversation history.

---

## 8. Feature: Sending a Chat Message (The RAG AI Pipeline)
**The User Action:** You type "What is the diagnosis?" in the text box and press Enter.
**1. The React Execution (`Chat.jsx`):**
- React pushes your message into the `messages` array instantly (Optimistic UI), rendering your blue bubble. It displays a "..." typing indicator.
**2. The API Hit:**
- Axios sends: `POST /chat` with JSON `{"query": "What is the diagnosis?", "session_id": "active-uuid"}`.
**3. The Backend Process & AI Logic (`routers/chat.py`, `retriever.py`, `llm.py`):**
- **Vector Search:** Converts your question to a vector. ChromaDB finds the top 20 chunks.
- **Reranker:** Cross-Encoder AI scores the 20 chunks against your question and keeps the top 5.
- **LLM Prompting:** Pastes those 5 chunks into a prompt and sends it to Google Gemini (or HuggingFace Mistral if Gemini fails).
**4. The Database Queries (`database.py`):**
- Save User Message: `INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'user', %s)`.
- Save AI Message (After Generation): `INSERT INTO chat_messages (session_id, role, content, citations) VALUES (%s, 'assistant', %s, %s)`.
**5. The Final Render:**
- Backend returns the AI's answer and citations. React adds it to the `messages` state.
- `messagesEndRef.scrollIntoView()` fires, automatically pulling your screen down to read the new text.

---

## 9. Feature: Expanding Citations in Chat
**The User Action:** You click the `[Source 1]` badge inside the AI's chat bubble.
**1. The React Execution (`Chat.jsx`):**
- As React drew the text, a Regex function (`renderMessageContent`) found `[Source 1]` and turned it into an interactive `<span onClick={...}>`.
- When clicked, React updates `activeCitations` with the metadata (Page #, Title, Snippet) linked to that badge.
- React updates `showCitationDrawer` from `false` to `true`.
**2. The API Hit / Backend Process:**
- **NONE.** This action is 100% Client-Side. The citation data was already sent to React in the previous step. Clicking the badge doesn't hit the server at all.
**3. The CSS Render (`index.css`):**
- Because `showCitationDrawer` is `true`, React appends the CSS class `.open` to the `<aside>` panel.
- The CSS rule `transform: translateX(0); transition: transform 0.3s ease;` tells the GPU to physically slide the drawer in from the right edge of the screen.

---

## 10. Feature: Document Annotations
**The User Action:** You highlight text on a document or submit a note (API feature).
**1. The React Execution:**
- You submit a note tied to a document and page number.
**2. The API Hit:**
- Axios sends: `POST /annotations` with JSON `{"document_id": "...", "page_number": 2, "note": "Check this"}`.
**3. The Backend Process (`routers/annotations.py`):**
- FastAPI validates the JSON.
**4. The Database Queries (`database.py`):**
- `INSERT INTO document_annotations (document_id, page_number, note) VALUES (%s, %s, %s)`.
**5. The Final Render:**
- Returns `201 Created`. React updates the UI to show a sticky note on that page. (Note: The API exists for this, ready for the UI layer to consume it).

---
*This map acts as the absolute source of truth for the directional flow of data in MedicalQuery. Every visual button click translates directly into a backend function, a Python pipeline, and a PostgreSQL or ChromaDB operation.*
