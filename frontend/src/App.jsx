import { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard.jsx';
import Chat from './pages/Chat.jsx';

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* ─── Sidebar Navigation ─── */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="logo-icon">🩺</div>
            <div>
              <h1>MedicalQuery</h1>
              <span>RAG System</span>
            </div>
          </div>

          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            <span className="icon">📄</span>
            Documents
          </NavLink>

          <NavLink
            to="/chat"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            <span className="icon">💬</span>
            Chat
          </NavLink>
        </aside>

        {/* ─── Main Content ─── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:sessionId" element={<Chat />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
