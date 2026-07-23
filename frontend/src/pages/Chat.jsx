import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  sendChatMessage,
  getChatSessions,
  getSessionMessages,
  deleteChatSession,
} from '../api';

function Chat() {
  const [searchParams] = useSearchParams();
  const documentId = searchParams.get('doc');

  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showCitationDrawer, setShowCitationDrawer] = useState(false);
  const [activeCitations, setActiveCitations] = useState([]);
  const [expandedCitationIndex, setExpandedCitationIndex] = useState(0);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // ─── Fetch sessions on mount ───
  useEffect(() => {
    fetchSessions();
  }, []);

  // ─── Fetch messages when active session changes ───
  useEffect(() => {
    if (activeSessionId) {
      fetchMessages(activeSessionId);
    }
  }, [activeSessionId]);

  // ─── Auto-scroll to bottom ───
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const fetchSessions = async () => {
    try {
      const res = await getChatSessions();
      setSessions(res.data);
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  };

  const fetchMessages = async (sessionId) => {
    try {
      const res = await getSessionMessages(sessionId);
      setMessages(res.data);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  };

  // ─── Send Message ───
  const handleSend = async () => {
    const query = inputValue.trim();
    if (!query || isLoading) return;

    // Optimistically add user message
    const userMsg = { role: 'user', content: query, sources: [], id: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await sendChatMessage(query, activeSessionId, documentId);
      const { answer, session_id, sources } = res.data;

      // Add assistant message
      const assistantMsg = { role: 'assistant', content: answer, sources, id: Date.now() + 1 };
      setMessages((prev) => [...prev, assistantMsg]);

      // Update session tracking
      if (!activeSessionId || activeSessionId !== session_id) {
        setActiveSessionId(session_id);
      }

      // Refresh sessions list
      await fetchSessions();
    } catch (err) {
      const errMsg = {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        sources: [],
        id: Date.now() + 1,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // ─── New Chat ───
  const startNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    inputRef.current?.focus();
  };

  // ─── Delete Session ───
  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    try {
      await deleteChatSession(sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
      await fetchSessions();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // ─── Citation Handling ───
  const openCitations = (sources, initialExpandedIndex = 0) => {
    setActiveCitations(sources);
    setExpandedCitationIndex(initialExpandedIndex);
    setShowCitationDrawer(true);
  };

  // ─── Render message content with clickable citation badges ───
  const renderMessageContent = (content, sources) => {
    if (!sources || sources.length === 0) return content;

    // Replace [Source N] with clickable badges
    const parts = content.split(/(\[Source\s+\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[Source\s+(\d+)\]/);
      if (match) {
        const idx = parseInt(match[1]);
        const sourceIndexInList = sources.findIndex((s) => s.source_index === idx);
        return (
          <span
            key={i}
            className="citation-badge"
            onClick={() => openCitations(sources, sourceIndexInList >= 0 ? sourceIndexInList : 0)}
            title={source ? `${source.document_title} — Page ${source.page_number || '?'}` : ''}
          >
            📎 Source {idx}
          </span>
        );

      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="chat-layout">
      {/* ─── Chat Sessions Sidebar ─── */}
      <div className="chat-sessions-panel">
        <div className="chat-sessions-header">
          <h3>History</h3>
          <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={startNewChat}>
            + New
          </button>
        </div>
        <div className="chat-sessions-list">
          {sessions.length === 0 ? (
            <p className="text-muted text-sm" style={{ padding: '12px', textAlign: 'center' }}>
              No conversations yet
            </p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
                onClick={() => setActiveSessionId(session.id)}
              >
                <span className="session-title">{session.title}</span>
                <button
                  className="btn-icon"
                  onClick={(e) => handleDeleteSession(session.id, e)}
                  style={{ padding: '4px', fontSize: '12px', color: 'var(--text-muted)' }}
                  title="Delete session"
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ─── Chat Main Area ─── */}
      <div className="chat-main">
        {/* Document Filter Banner */}
        {documentId && (
          <div style={{
            padding: '10px 24px',
            background: 'rgba(92, 200, 232, 0.08)',
            borderBottom: '1px solid var(--border-glass)',
            fontSize: '13px',
            color: 'var(--accent)',
          }}>
            🔗 Chatting with a specific document (ID: {documentId.slice(0, 8)}...)
          </div>
        )}

        {/* Messages */}
        <div className="chat-messages">
          {messages.length === 0 && !isLoading && (
            <div className="empty-state">
              <div className="empty-icon">🩺</div>
              <h3>MedicalQuery Assistant</h3>
              <p>
                Ask questions about your uploaded medical documents.
                I'll find the relevant information and cite my sources.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.role}`}>
              {msg.role === 'assistant'
                ? renderMessageContent(msg.content, msg.sources)
                : msg.content}
              {msg.role === 'assistant' && msg.sources?.length > 0 && (
                <div style={{ marginTop: '10px', borderTop: '1px solid var(--border-glass)', paddingTop: '8px' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '11px', padding: '4px 10px' }}
                    onClick={() => openCitations(msg.sources)}
                  >
                    📋 View all {msg.sources.length} source(s)
                  </button>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <input
              ref={inputRef}
              type="text"
              placeholder="Ask a question about your documents..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              disabled={isLoading}
            />
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
            >
              ➤
            </button>
          </div>
        </div>
      </div>

      {/* ─── Citation Drawer ─── */}
      <div className={`citation-drawer ${showCitationDrawer ? 'open' : ''}`}>
        <div className="citation-drawer-header">
          <h3>📎 Source Details</h3>
          <button className="btn-icon" onClick={() => setShowCitationDrawer(false)}>✕</button>
        </div>
        <div className="citation-drawer-body">
          {activeCitations.map((source, i) => {
            const isExpanded = expandedCitationIndex === i;
            return (
              <div
                key={i}
                className={`citation-detail ${isExpanded ? 'expanded' : ''}`}
                onClick={() => setExpandedCitationIndex(isExpanded ? null : i)}
                style={{ cursor: 'pointer', transition: 'all 0.3s ease' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <div className="citation-doc-title">
                      📄 {source.document_title}
                    </div>
                    {source.page_number && (
                      <div className="citation-page">Page {source.page_number}</div>
                    )}
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--accent)', fontWeight: 600, padding: '2px 6px', background: 'rgba(92, 200, 232, 0.1)', borderRadius: '4px' }}>
                    {isExpanded ? '▲ Collapse' : '▼ Expand'}
                  </span>
                </div>
                <div className={`citation-snippet ${isExpanded ? 'full' : 'preview'}`}>
                  {source.snippet}
                </div>
              </div>
            );
          })}
        </div>

      </div>

      {/* Drawer Backdrop */}
      {showCitationDrawer && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 999,
          }}
          onClick={() => setShowCitationDrawer(false)}
        />
      )}
    </div>
  );
}

export default Chat;
