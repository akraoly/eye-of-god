export default function Sidebar({ view, onNav }) {
  const nav = [
    { id: 'chat',   icon: '💬', label: 'Chat' },
    { id: 'memory', icon: '🧠', label: 'Mémoires' },
  ]

  const caps = [
    { icon: '⚔️', label: 'OSEE · Exploit Dev' },
    { icon: '🔬', label: 'Reverse Engineering' },
    { icon: '🛠️', label: 'Dev Autonome' },
    { icon: '🔴', label: 'Kali · 323 outils' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="brand-icon">👁️</div>
          <div className="brand-text">
            <div className="brand-name">L'Œil de Dieu</div>
            <div className="brand-version">v3.0 · OSEE + Dev</div>
          </div>
        </div>
        <div className="status-pill">
          <span className="status-dot" />
          En ligne
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <span className="nav-section-label">Navigation</span>
        </div>
        {nav.map(item => (
          <button
            key={item.id}
            className={`nav-btn ${view === item.id ? 'active' : ''}`}
            onClick={() => onNav(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}

        <div className="nav-section">
          <span className="nav-section-label">Capacités</span>
        </div>
        {caps.map(c => (
          <div key={c.label} className="nav-btn" style={{ cursor: 'default', opacity: 0.55, fontSize: '0.8rem', pointerEvents: 'none' }}>
            <span className="nav-icon">{c.icon}</span>
            {c.label}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="footer-info">
          Kali Linux · Port 8001<br />
          FastAPI + Claude API
        </div>
        <div className="footer-hint">
          <kbd>Enter</kbd> envoyer &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> saut de ligne
        </div>
      </div>
    </aside>
  )
}
