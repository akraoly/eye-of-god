export default function Sidebar({ view, onNav }) {
  const items = [
    { id: 'chat', label: '💬 Chat', title: 'Conversation' },
    { id: 'memory', label: '🧠 Mémoires', title: 'Mes mémoires' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-icon">🧠</span>
        <div>
          <div className="logo-title">L'Œil de Dieu</div>
          <div className="logo-sub">v1.0 MVP</div>
        </div>
      </div>
      <nav>
        {items.map(item => (
          <button
            key={item.id}
            className={`nav-item ${view === item.id ? 'active' : ''}`}
            onClick={() => onNav(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        Kali Linux · Port 8001
      </div>
    </aside>
  )
}
