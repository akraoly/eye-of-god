/**
 * NotificationSystem — Toasts + Centre de notifications
 * Toasts en haut à droite, cloche dans la sidebar, centre glissant
 */
import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useNotificationStore } from '../stores/notificationStore'

const TYPE_COLOR = {
  info:     { bg: '#0ea5e920', border: '#0ea5e9', icon: 'ℹ', text: '#38bdf8' },
  warning:  { bg: '#f97316', border: '#f97316',  icon: '⚠', text: '#fbbf24' },
  critical: { bg: '#ef444420', border: '#ef4444', icon: '🔴', text: '#ef4444' },
}

// ── Toast unique ──────────────────────────────────────────────────────────────
function Toast({ toast, onDismiss }) {
  const c = TYPE_COLOR[toast.type] || TYPE_COLOR.info
  return (
    <motion.div
      initial={{ opacity: 0, x: 80, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.85 }}
      transition={{ type: 'spring', stiffness: 280, damping: 24 }}
      style={{
        background: `color-mix(in srgb, var(--glass) 90%, ${c.border} 10%)`,
        border: `1.5px solid ${c.border}`,
        borderRadius: 10, padding: '10px 14px',
        display: 'flex', alignItems: 'flex-start', gap: 10,
        minWidth: 280, maxWidth: 360,
        boxShadow: `0 4px 24px ${c.border}30`,
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* barre gauche colorée */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: c.border }} />
      <span style={{ fontSize: '1rem', lineHeight: 1, marginLeft: 4 }}>{c.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: c.text }}>{toast.title}</div>
        {toast.body && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: 2, lineHeight: 1.4 }}>{toast.body.slice(0, 120)}</div>}
        {toast.source && <div style={{ fontSize: '0.58rem', color: 'var(--text3)', marginTop: 2, opacity: 0.6 }}>{toast.source}</div>}
      </div>
      <button onClick={() => onDismiss(toast.id)} style={{
        background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer',
        fontSize: '0.8rem', padding: 2, lineHeight: 1,
      }}>✕</button>
    </motion.div>
  )
}

// ── Centre de notifications ────────────────────────────────────────────────────
function NotifCenter({ onClose }) {
  const { notifications, markRead, markAllRead, clear } = useNotificationStore()

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      style={{
        position: 'fixed', top: 50, right: 16, width: 360, maxHeight: '70vh',
        background: 'var(--glass)', border: '1px solid var(--border2)',
        borderRadius: 14, zIndex: 1000,
        boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}
    >
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ flex: 1, fontWeight: 700, fontSize: '0.8rem', color: 'var(--accent)' }}>Notifications</span>
        <button onClick={markAllRead} style={{ fontSize: '0.65rem', padding: '3px 8px', background: 'var(--glow2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer' }}>Tout lire</button>
        <button onClick={clear} style={{ fontSize: '0.65rem', padding: '3px 8px', background: '#ef444410', border: '1px solid #ef4444', borderRadius: 6, color: '#ef4444', cursor: 'pointer' }}>Vider</button>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer', fontSize: '1rem' }}>✕</button>
      </div>
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {notifications.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 30, color: 'var(--text3)', fontSize: '0.78rem' }}>Aucune notification</div>
        ) : notifications.map(n => {
          const c = TYPE_COLOR[n.type] || TYPE_COLOR.info
          return (
            <div key={n.id} onClick={() => markRead(n.id)} style={{
              padding: '10px 14px', borderBottom: '1px solid var(--border)',
              cursor: 'pointer', opacity: n.read ? 0.5 : 1,
              background: n.read ? 'transparent' : `${c.border}08`,
              borderLeft: `3px solid ${n.read ? 'transparent' : c.border}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span>{c.icon}</span>
                <span style={{ fontWeight: 700, fontSize: '0.72rem', color: c.text }}>{n.title}</span>
                {!n.read && <span style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: c.border, display: 'inline-block' }} />}
              </div>
              {n.body && <div style={{ fontSize: '0.68rem', color: 'var(--text3)', lineHeight: 1.4 }}>{n.body.slice(0, 100)}</div>}
              <div style={{ fontSize: '0.58rem', color: 'var(--text3)', marginTop: 3, opacity: 0.5 }}>
                {n.ts?.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })} · {n.source || '—'}
              </div>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

// ── Bell icon (à insérer dans Sidebar) ───────────────────────────────────────
export function NotifBell() {
  const [open, setOpen] = useState(false)
  const { unreadCount, toasts, dismissToast } = useNotificationStore()

  // Fermer en cliquant hors
  useEffect(() => {
    if (!open) return
    const close = (e) => {
      if (!e.target.closest('[data-notif-center]') && !e.target.closest('[data-notif-bell]'))
        setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <>
      <button data-notif-bell onClick={() => setOpen(o => !o)} style={{
        position: 'relative', background: 'none', border: 'none',
        cursor: 'pointer', color: unreadCount > 0 ? '#fbbf24' : 'var(--text3)',
        fontSize: '1.1rem', padding: '4px', display: 'flex', alignItems: 'center',
      }} title="Notifications">
        🔔
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: 0, right: 0, background: '#ef4444',
            color: '#fff', fontSize: '0.5rem', fontWeight: 900,
            borderRadius: '50%', width: 14, height: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>
      <AnimatePresence>
        {open && <div data-notif-center><NotifCenter onClose={() => setOpen(false)} /></div>}
      </AnimatePresence>
    </>
  )
}

// ── Toast container (à placer à la racine de l'app) ───────────────────────────
export function ToastContainer() {
  const { toasts, dismissToast } = useNotificationStore()
  return (
    <div style={{
      position: 'fixed', top: 16, right: 16, zIndex: 9000,
      display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end',
      pointerEvents: 'none',
    }}>
      <AnimatePresence>
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents: 'auto' }}>
            <Toast toast={t} onDismiss={dismissToast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}
