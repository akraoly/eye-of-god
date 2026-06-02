import { useState, useRef, useEffect } from 'react'
import { logout, auth } from '../utils/auth'

const THEMES = [
  { id: 'galactic',  icon: '🌌', label: 'Galactique' },
  { id: 'divine',    icon: '✨', label: 'Divin'      },
  { id: 'cyberpunk', icon: '⚡', label: 'Cyberpunk'  },
  { id: 'alien',     icon: '🛸', label: 'Civilisation extraterrestre' },
  { id: 'temple',    icon: '🔥', label: 'Temple numérique' },
]

const NAV = [
  { id: 'chat',      icon: '💬', label: 'Chat'      },
  { id: 'soc',       icon: '🔴', label: 'SOC'       },
  { id: 'offensive', icon: '⚔️', label: 'Offensif'  },
  { id: 'memory',    icon: '🧠', label: 'Mémoire'   },
  { id: 'code',      icon: '🛠️', label: 'Code'      },
  { id: 'knowledge', icon: '📚', label: 'Know'      },
  { id: 'life',      icon: '🎯', label: 'Life'      },
  { id: 'vision',    icon: '👁️', label: 'Vision'    },
  { id: 'autonomy',  icon: '⏰', label: 'Auto'      },
]

export default function Sidebar({ view, onNav, theme, onTheme, onNewChat, alertCount = 0 }) {
  const [showThemes,  setShowThemes]  = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const userMenuRef = useRef(null)
  const user = auth.getUser()
  const initials = (user?.display_name || user?.username || '?')
    .split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)

  // Fermer le menu user en cliquant ailleurs
  useEffect(() => {
    const close = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false)
      }
    }
    if (showUserMenu) document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [showUserMenu])

  return (
    <>
      {/* Panel thème */}
      {showThemes && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowThemes(false)} />
          <div className="theme-overlay">
            <div className="theme-panel">
              {THEMES.map(t => (
                <button key={t.id}
                  className={`theme-option ${theme === t.id ? 'selected' : ''}`}
                  onClick={() => { onTheme(t.id); setShowThemes(false) }}
                >
                  <span style={{ fontSize: '1.1rem' }}>{t.icon}</span>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">👁️</div>
        <div className="status-dot-sidebar" title="En ligne" />

        {/* ── Nouveau chat ── */}
        <button className="sidebar-new-chat" onClick={onNewChat} title="Nouveau chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          <span className="nav-label">Nouveau</span>
        </button>

        <div className="sidebar-divider" style={{ margin: '6px 0' }} />

        {/* Navigation principale */}
        {NAV.map(item => (
          <button key={item.id}
            className={`nav-btn ${view === item.id ? 'active' : ''}`}
            onClick={() => onNav(item.id)}
            title={item.label}
            style={{ position: 'relative' }}
          >
            <span style={{ fontSize: '1.2rem' }}>{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {item.id === 'autonomy' && alertCount > 0 && (
              <span className="sidebar-alert-badge">{alertCount > 9 ? '9+' : alertCount}</span>
            )}
          </button>
        ))}

        <div className="sidebar-spacer" />

        {/* Theme switcher */}
        <button className="theme-btn" onClick={() => setShowThemes(v => !v)} title="Changer de thème">
          {THEMES.find(t => t.id === theme)?.icon || '🌌'}
        </button>

        {/* ── Zone utilisateur ── */}
        <div className="sidebar-user-zone" ref={userMenuRef}>
          {showUserMenu && (
            <div className="sidebar-user-menu">
              <div className="sidebar-user-menu-name">
                {user?.display_name || user?.username}
              </div>
              <button className="sidebar-user-menu-logout" onClick={logout}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Se déconnecter
              </button>
            </div>
          )}
          <button
            className="sidebar-user-btn"
            onClick={() => setShowUserMenu(v => !v)}
            title={user?.username}
          >
            <div className="sidebar-user-avatar">{initials}</div>
          </button>
        </div>
      </aside>
    </>
  )
}
