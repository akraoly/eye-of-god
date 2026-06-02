import { useState } from 'react'

const THEMES = [
  { id: 'galactic', icon: '🌌', label: 'Galactique' },
  { id: 'divine',   icon: '✨', label: 'Divin'      },
  { id: 'cyberpunk',icon: '⚡', label: 'Cyberpunk'  },
  { id: 'alien',    icon: '🛸', label: 'Civilisation extraterrestre' },
  { id: 'temple',   icon: '🔥', label: 'Temple numérique' },
]

const NAV = [
  { id: 'chat',      icon: '💬', label: 'Chat' },
  { id: 'soc',       icon: '🔴', label: 'SOC' },
  { id: 'offensive', icon: '⚔️', label: 'Offensive' },
  { id: 'memory',    icon: '🧠', label: 'Mémoire' },
]

const CAPS = [
  { icon: '⚔️', label: 'OSEE'  },
  { icon: '🔬', label: 'RE'    },
  { icon: '🛠️', label: 'Dev'   },
  { icon: '📚', label: 'Know'  },
  { icon: '🎯', label: 'Life'  },
]

export default function Sidebar({ view, onNav, theme, onTheme }) {
  const [showThemes, setShowThemes] = useState(false)

  return (
    <>
      {/* Panel thème */}
      {showThemes && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 99 }}
            onClick={() => setShowThemes(false)}
          />
          <div className="theme-overlay">
            <div className="theme-panel">
              {THEMES.map(t => (
                <button
                  key={t.id}
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

        {/* Navigation principale */}
        {NAV.map(item => (
          <button
            key={item.id}
            className={`nav-btn ${view === item.id ? 'active' : ''}`}
            onClick={() => onNav(item.id)}
            title={item.label}
          >
            <span style={{ fontSize: '1.2rem' }}>{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}

        <div className="sidebar-divider" />

        {/* Capacités (non-cliquables) */}
        {CAPS.map(c => (
          <div key={c.icon} className="nav-btn" title={c.label}
            style={{ cursor: 'default', opacity: 0.45, pointerEvents: 'none' }}>
            <span style={{ fontSize: '1rem' }}>{c.icon}</span>
            <span className="nav-label">{c.label}</span>
          </div>
        ))}

        <div className="sidebar-spacer" />

        {/* Theme switcher */}
        <button className="theme-btn" onClick={() => setShowThemes(v => !v)} title="Changer de thème">
          {THEMES.find(t => t.id === theme)?.icon || '🌌'}
        </button>
      </aside>
    </>
  )
}
