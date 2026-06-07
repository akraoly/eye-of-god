import { useState, useRef, useEffect, useCallback } from 'react'
import { logout, auth } from '../utils/auth'

// ── Helpers temps ─────────────────────────────────────────────────────────────
const STATS_KEY = 'eye_time_stats'

function getStats() {
  try { return JSON.parse(localStorage.getItem(STATS_KEY) || '{}') } catch { return {} }
}

function saveMinute() {
  const today = new Date().toDateString()
  const s = getStats()
  s[today] = (s[today] || 0) + 60
  localStorage.setItem(STATS_KEY, JSON.stringify(s))
  return s
}

function fmtSec(s) {
  if (s < 60)  return `${s}s`
  if (s < 3600) return `${Math.floor(s/60)}m ${s%60}s`
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60)
  return `${h}h ${m}m`
}

function fmtShort(s) {
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), ss = s%60
  return h > 0 ? `${h}h${String(m).padStart(2,'0')}` : `${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
}

function calcPeriods(stats, sessionSec) {
  const now   = new Date()
  const today = now.toDateString()

  const dayMs   = 86400000
  const weekMs  = 7 * dayMs
  const monthMs = 30 * dayMs
  const yearMs  = 365 * dayMs

  let week = 0, month = 0, year = 0, total = 0
  for (const [key, val] of Object.entries(stats)) {
    const d = new Date(key)
    const diff = now - d
    if (diff <= weekMs)  week  += val
    if (diff <= monthMs) month += val
    if (diff <= yearMs)  year  += val
    total += val
  }
  const todaySaved = stats[today] || 0
  return {
    session: fmtSec(sessionSec),
    today:   fmtSec(todaySaved + sessionSec),
    week:    fmtSec(week + sessionSec),
    month:   fmtSec(month + sessionSec),
    year:    fmtSec(year + sessionSec),
    total:   fmtSec(total + sessionSec),
  }
}

// ── Timer de session ──────────────────────────────────────────────────────────
function useSessionTimer() {
  const startRef = useRef(Date.now())
  const [elapsed, setElapsed] = useState(0)
  const [stats, setStats] = useState(getStats)

  useEffect(() => {
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000)
    return () => clearInterval(tick)
  }, [])

  useEffect(() => {
    const save = setInterval(() => setStats(saveMinute()), 60000)
    return () => clearInterval(save)
  }, [])

  return { elapsed, periods: calcPeriods(stats, elapsed), short: fmtShort(elapsed) }
}

// ── Fuseau horaire & horloge live ─────────────────────────────────────────────
function useTimezone() {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone  // ex: "Africa/Abidjan"
  const locale = navigator.language || 'fr-FR'

  // Calcul offset UTC ex: "UTC+0" ou "UTC+2"
  const offsetMin = -new Date().getTimezoneOffset()
  const sign = offsetMin >= 0 ? '+' : '-'
  const absH  = Math.floor(Math.abs(offsetMin) / 60)
  const absM  = Math.abs(offsetMin) % 60
  const utcLabel = absM === 0 ? `UTC${sign}${absH}` : `UTC${sign}${absH}:${String(absM).padStart(2,'0')}`

  // Abréviation locale ex: "WAT", "CET", "EST"
  const abbr = (() => {
    try {
      const parts = new Intl.DateTimeFormat(locale, { timeZoneName: 'short' }).formatToParts(new Date())
      return parts.find(p => p.type === 'timeZoneName')?.value || utcLabel
    } catch { return utcLabel }
  })()

  // Pays/région lisible ex: "Abidjan", "Paris", "New York"
  const region = tz.split('/').pop().replace(/_/g, ' ')
  const continent = tz.split('/')[0]

  return { tz, utcLabel, abbr, region, continent, locale }
}

function useClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return now
}

// ── Panneau statistiques de temps ─────────────────────────────────────────────
function StatsPanel({ periods, onClose }) {
  const { tz, utcLabel, abbr, region, continent } = useTimezone()
  const now = useClock()

  const timeStr  = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const dateStr  = now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  const timeRows = [
    { label: 'Session actuelle', value: periods.session, icon: '⚡' },
    { label: "Aujourd'hui",      value: periods.today,   icon: '☀️' },
    { label: 'Cette semaine',    value: periods.week,    icon: '📅' },
    { label: 'Ce mois',         value: periods.month,   icon: '🗓️' },
    { label: 'Cette année',     value: periods.year,    icon: '📆' },
    { label: 'Total cumul',     value: periods.total,   icon: '∞'  },
  ]

  return (
    <div className="stats-panel">
      <div className="compass-panel-header">
        <span>⏱ Temps sur la plateforme</span>
        <button className="compass-close" onClick={onClose}>✕</button>
      </div>

      {/* ── Horloge locale ── */}
      <div className="stats-clock-block">
        <div className="stats-clock-time">{timeStr}</div>
        <div className="stats-clock-date">{dateStr}</div>
        <div className="stats-clock-tz">
          <span className="stats-tz-badge">{abbr}</span>
          <span className="stats-tz-region">{continent} / {region}</span>
          <span className="stats-tz-utc">{utcLabel}</span>
        </div>
      </div>

      <div className="stats-divider" />

      {timeRows.map(r => (
        <div key={r.label} className="stats-row">
          <span className="stats-row-icon">{r.icon}</span>
          <span className="stats-row-label">{r.label}</span>
          <span className="stats-row-val">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

// ── Boussole ──────────────────────────────────────────────────────────────────
function CompassPanel({ onClose }) {
  const [heading, setHeading] = useState(null)
  const [permDenied, setPermDenied] = useState(false)

  const subscribe = useCallback(() => {
    const handler = (e) => {
      const h = e.webkitCompassHeading ?? (e.alpha !== null ? (360 - e.alpha) % 360 : null)
      if (h !== null) setHeading(Math.round(h))
    }
    if (typeof DeviceOrientationEvent !== 'undefined') {
      if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        DeviceOrientationEvent.requestPermission()
          .then(s => { if (s === 'granted') { window.addEventListener('deviceorientation', handler) } else { setPermDenied(true) } })
          .catch(() => setPermDenied(true))
      } else {
        window.addEventListener('deviceorientation', handler)
      }
    }
    return () => window.removeEventListener('deviceorientation', handler)
  }, [])

  useEffect(() => { const unsub = subscribe(); return unsub }, [subscribe])

  const deg = heading ?? 0
  const dirs = ['N','NE','E','SE','S','SO','O','NO']
  const dirLabel = dirs[Math.round(deg / 45) % 8]

  return (
    <div className="compass-panel">
      <div className="compass-panel-header">
        <span>🧭 Boussole</span>
        <button className="compass-close" onClick={onClose}>✕</button>
      </div>
      <div className="compass-ring">
        {/* Cadran */}
        <svg viewBox="0 0 120 120" className="compass-svg">
          <circle cx="60" cy="60" r="56" fill="none" stroke="var(--border2)" strokeWidth="1.5"/>
          <circle cx="60" cy="60" r="46" fill="none" stroke="var(--border)" strokeWidth="0.5" strokeDasharray="2 4"/>
          {['N','E','S','O'].map((d,i) => {
            const a = i * 90, r = Math.PI * a / 180
            const x = 60 + 40 * Math.sin(r), y = 60 - 40 * Math.cos(r)
            return <text key={d} x={x} y={y} textAnchor="middle" dominantBaseline="central"
              fill={d === 'N' ? '#e8c14a' : 'var(--text3)'} fontSize={d === 'N' ? '11' : '9'} fontWeight="700">{d}</text>
          })}
          {/* Aiguille tournante */}
          <g transform={`rotate(${deg} 60 60)`}>
            <polygon points="60,12 63,58 57,58" fill="#e8c14a"/>
            <polygon points="60,108 63,62 57,62" fill="var(--text3)" opacity="0.6"/>
          </g>
          <circle cx="60" cy="60" r="4" fill="var(--accent)" opacity="0.9"/>
        </svg>
      </div>
      <div className="compass-info">
        {heading !== null
          ? <><span className="compass-deg">{heading}°</span><span className="compass-dir">{dirLabel}</span></>
          : permDenied
            ? <span className="compass-unavail">Permission refusée</span>
            : <span className="compass-unavail">Capteur non détecté<br/><small>Disponible sur mobile</small></span>
        }
      </div>
    </div>
  )
}

const THEMES = [
  { id: 'galactic',  icon: '🌌', label: 'Galactique' },
  { id: 'divine',    icon: '✨', label: 'Divin'      },
  { id: 'cyberpunk', icon: '⚡', label: 'Cyberpunk'  },
  { id: 'alien',     icon: '🛸', label: 'Civilisation extraterrestre' },
  { id: 'temple',    icon: '🔥', label: 'Temple numérique' },
]

const NAV = [
  { id: 'chat',         icon: '🏠', label: 'Accueil'  },
  { id: 'soc',          icon: '🔴', label: 'SOC'      },
  { id: 'offensive',    icon: '⚔️', label: 'Offensif' },
  { id: 'memory',       icon: '🧠', label: 'Mémoire'  },
  { id: 'code',         icon: '🛠️', label: 'Code'     },
  { id: 'knowledge',    icon: '📚', label: 'Know'     },
  { id: 'life',         icon: '🎯', label: 'Life'     },
  { id: 'vision',       icon: '👁️', label: 'Vision'   },
  { id: 'autonomy',     icon: '⏰', label: 'Auto'     },
  { id: 'observe',      icon: '🔭', label: 'Observe'  },
  { id: 'diagnostic',   icon: '🩺', label: 'Diag'     },
  { id: 'aegis',        icon: '🛡️', label: 'AEGIS'    },
  { id: 'osint',        icon: '🔍', label: 'OSINT'    },
  { id: 'credentials',  icon: '🔑', label: 'Creds'    },
  { id: 'threat-intel', icon: '🌐', label: 'Intel'    },
  { id: 'forensics',    icon: '🧪', label: 'Forensic' },
  { id: 'privesc',      icon: '⬆️', label: 'PrivEsc'  },
  { id: 'lateral',      icon: '↔️', label: 'Lateral'  },
  { id: 'lab',          icon: '🧬', label: 'Lab'      },
  { id: 'reports',      icon: '📄', label: 'Reports'  },
  { id: 'self-improve', icon: '🧠', label: 'Learn'    },
  { id: 'terminal',     icon: '💻', label: 'Terminal' },
  { id: 'audio',        icon: '🎤', label: 'Audio'    },
  { id: 'cameras',      icon: '📷', label: 'Cams'     },
  { id: 'post-exploit', icon: '🎯', label: 'PostEx'   },
  { id: 'sniffer',      icon: '📡', label: 'Sniffer'  },
  { id: 'triggers',     icon: '⚡', label: 'Triggers' },
  { id: 'exfil',        icon: '📤', label: 'Exfil'    },
  { id: 'omniscience',  icon: '🌍', label: 'Omni'     },
  { id: 'ble',          icon: '🔵', label: 'BLE'      },
  { id: 'sdr',          icon: '📻', label: 'SDR'      },
  { id: 'rfid',         icon: '💳', label: 'RFID'     },
  { id: 'mitre',        icon: '🎯', label: 'MITRE'    },
  { id: 'audit-reports',icon: '📋', label: 'Audit'    },
]

export default function Sidebar({ view, onNav, theme, onTheme, onNewChat, alertCount = 0 }) {
  const [showThemes,   setShowThemes]   = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showCompass,  setShowCompass]  = useState(false)
  const [showStats,    setShowStats]    = useState(false)
  const userMenuRef = useRef(null)
  const { short, periods } = useSessionTimer()
  const { utcLabel, abbr } = useTimezone()
  const now = useClock()
  const localTime = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
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

      {/* Panneaux flottants — hors de <aside> pour éviter le clipping backdrop-filter */}
      {showStats   && <StatsPanel   periods={periods} onClose={() => setShowStats(false)} />}
      {showCompass && <CompassPanel onClose={() => setShowCompass(false)} />}

      <aside className="sidebar">
        {/* Logo — clic = retour accueil */}
        <button
          className="sidebar-logo"
          onClick={onNewChat}
          title="Accueil"
          style={{ cursor: 'pointer', border: 'none', padding: 0, fontFamily: 'inherit' }}
        >👁️</button>
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
            onClick={() => item.id === 'chat' ? onNewChat() : onNav(item.id)}
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

        {/* ── Timer de session ── */}
        <div className="sidebar-divider" style={{ margin: '4px 0' }} />
        <button
          className={`sidebar-timer ${showStats ? 'active-timer' : ''}`}
          onClick={() => { setShowStats(v => !v); setShowCompass(false) }}
          title={`Session: ${short} | ${abbr} ${utcLabel}`}
        >
          <span className="sidebar-timer-icon">⏱</span>
          <span className="sidebar-timer-val">{short}</span>
          <span className="sidebar-timer-label">session</span>
          <span className="sidebar-timer-clock">{localTime}</span>
          <span className="sidebar-timer-tz">{abbr}</span>
        </button>
        {/* ── Boussole ── */}
        <button
          className={`nav-btn compass-btn ${showCompass ? 'active' : ''}`}
          onClick={() => { setShowCompass(v => !v); setShowStats(false) }}
          title="Boussole"
        >
          <span style={{ fontSize: '1.2rem' }}>🧭</span>
          <span className="nav-label">Bousole</span>
        </button>

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
