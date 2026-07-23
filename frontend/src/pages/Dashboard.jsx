import { useState, useEffect, useRef, useCallback } from 'react';
import { useDebounce } from '../hooks/useDebounce';
import {
  getDocuments,
  uploadDocument,
  batchUploadDocuments,
  updateDocument,
  deleteDocument,
  getDocumentStats,
  downloadDocument,
} from '../api';
import { useNavigate } from 'react-router-dom';

function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({ total_documents: 0, total_chunks: 0, total_storage_bytes: 0 });
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [editingDoc, setEditingDoc] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [showEditModal, setShowEditModal] = useState(false);

  const debouncedSearch = useDebounce(searchQuery, 500);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  // ─── Fetch documents when search changes (debounced) ───
  useEffect(() => {
    fetchDocuments();
  }, [debouncedSearch]);

  // ─── Fetch stats on mount ───
  useEffect(() => {
    fetchStats();
  }, []);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const res = await getDocuments(debouncedSearch);
      setDocuments(res.data);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await getDocumentStats();
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  // ─── File Upload ───
  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);

    try {
      if (files.length === 1) {
        await uploadDocument(files[0]);
      } else {
        await batchUploadDocuments(Array.from(files));
      }
      await fetchDocuments();
      await fetchStats();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed';
      alert(msg);
    } finally {
      setIsUploading(false);
    }
  };

  // ─── Drag & Drop ───
  const handleDragOver = (e) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileUpload(e.dataTransfer.files);
  };

  // ─── Edit Document ───
  const openEditModal = (doc) => {
    setEditingDoc(doc);
    setEditTitle(doc.title);
    setShowEditModal(true);
  };

  const handleUpdate = async () => {
    if (!editingDoc || !editTitle.trim()) return;
    try {
      await updateDocument(editingDoc.id, editTitle);
      setShowEditModal(false);
      setEditingDoc(null);
      await fetchDocuments();
    } catch (err) {
      alert('Update failed');
    }
  };

  // ─── Delete Document ───
  const handleDelete = async (docId) => {
    if (!confirm('Are you sure you want to delete this document and all its chunks?')) return;
    try {
      await deleteDocument(docId);
      await fetchDocuments();
      await fetchStats();
    } catch (err) {
      alert('Delete failed');
    }
  };

  // ─── Helpers ───
  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileType = (filename) => {
    const ext = filename?.split('.').pop()?.toLowerCase();
    if (['pdf'].includes(ext)) return { label: 'PDF', className: 'file-type-pdf' };
    if (['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'].includes(ext)) return { label: 'IMG', className: 'file-type-image' };
    return { label: 'TXT', className: 'file-type-text' };
  };

  const getStatusBadge = (status) => {
    if (status === 'completed') return <span className="badge badge-success">✓ Indexed</span>;
    if (status === 'processing') return <span className="badge badge-warning">⏳ Processing</span>;
    return <span className="badge badge-danger">⚠ {status}</span>;
  };

  return (
    <div>
      {/* ─── Page Header ─── */}
      <div className="page-header">
        <h2>Documents</h2>
        <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>
          {isUploading ? <span className="spinner" /> : '⬆'} Upload
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff,.tif,.webp,.txt,.md,.csv"
          style={{ display: 'none' }}
          onChange={(e) => handleFileUpload(e.target.files)}
        />
      </div>

      {/* ─── Stats Cards ─── */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📄</div>
          <div className="stat-value">{stats.total_documents}</div>
          <div className="stat-label">Documents</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🧩</div>
          <div className="stat-value">{stats.total_chunks}</div>
          <div className="stat-label">Indexed Chunks</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">💾</div>
          <div className="stat-value">{formatBytes(stats.total_storage_bytes)}</div>
          <div className="stat-label">Storage Used</div>
        </div>
      </div>

      {/* ─── Upload Drop Zone ─── */}
      <div
        className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="upload-icon">{isUploading ? '⏳' : '📁'}</div>
        <p>{isUploading ? 'Processing...' : 'Drag & drop files here, or click to browse'}</p>
        <p className="upload-hint">Supports PDF, Images (PNG, JPG), and Text files</p>
      </div>

      {/* ─── Search Bar (Debounced) ─── */}
      <div className="search-bar">
        <span className="search-icon">🔍</span>
        <input
          type="text"
          placeholder="Search documents by title..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button className="btn-icon" onClick={() => setSearchQuery('')}>✕</button>
        )}
      </div>

      {/* ─── Document Table ─── */}
      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto' }} />
            <p className="mt-2">Loading documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <h3>No documents yet</h3>
            <p>Upload your first medical document to get started with intelligent Q&A.</p>
          </div>
        ) : (
          <table className="doc-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Size</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const fileType = getFileType(doc.filename);
                return (
                  <tr key={doc.id}>
                    <td className="doc-title">{doc.title}</td>
                    <td>
                      <span className={`file-type-pill ${fileType.className}`}>{fileType.label}</span>
                    </td>
                    <td>{formatBytes(doc.file_size)}</td>
                    <td className="text-accent">{doc.chunk_count}</td>
                    <td>{getStatusBadge(doc.status)}</td>
                    <td className="text-muted text-sm">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td>
                      <div className="doc-actions">
                        <button
                          className="btn-icon"
                          title="Chat with document"
                          onClick={() => navigate(`/chat?doc=${doc.id}`)}
                        >
                          💬
                        </button>
                        <a
                          className="btn-icon"
                          title="Download original"
                          href={downloadDocument(doc.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          ⬇
                        </a>
                        <button
                          className="btn-icon"
                          title="Edit title"
                          onClick={() => openEditModal(doc)}
                        >
                          ✏️
                        </button>
                        <button
                          className="btn-icon"
                          title="Delete"
                          onClick={() => handleDelete(doc.id)}
                          style={{ color: 'var(--danger)' }}
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ─── Edit Modal ─── */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Document Title</h2>
            <input
              className="modal-input"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              placeholder="Enter new title..."
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleUpdate()}
            />
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowEditModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleUpdate}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
