import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/* ─── Documents ──────────────────────────────────────────────── */

export const getDocuments = (search = '') => {
  const params = search ? { search } : {};
  return api.get('/documents', { params });
};

export const getDocument = (id) => api.get(`/documents/${id}`);

export const uploadDocument = (file, title) => {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  return api.post('/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const batchUploadDocuments = (files) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  return api.post('/documents/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const updateDocument = (id, title) =>
  api.put(`/documents/${id}`, { title });

export const deleteDocument = (id) => api.delete(`/documents/${id}`);

export const getDocumentStats = () => api.get('/documents/stats');

export const downloadDocument = (id) =>
  `${API_BASE_URL}/documents/${id}/download`;

/* ─── Chat ───────────────────────────────────────────────────── */

export const sendChatMessage = (query, sessionId = null, documentId = null) =>
  api.post('/chat', {
    query,
    session_id: sessionId,
    document_id: documentId,
  });

export const getChatSessions = () => api.get('/chat/sessions');

export const getSessionMessages = (sessionId) =>
  api.get(`/chat/sessions/${sessionId}/messages`);

export const deleteChatSession = (sessionId) =>
  api.delete(`/chat/sessions/${sessionId}`);

/* ─── Annotations ────────────────────────────────────────────── */

export const createAnnotation = (annotation) =>
  api.post('/annotations', annotation);

export const getAnnotations = (documentId) =>
  api.get(`/annotations/document/${documentId}`);

export const deleteAnnotation = (id) => api.delete(`/annotations/${id}`);

export default api;
