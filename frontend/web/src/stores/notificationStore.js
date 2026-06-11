/**
 * Zustand store — notifications globales L'Œil de Dieu
 * Toasts éphémères + centre de notifications persistant
 */
import { create } from 'zustand'

let _id = 0

export const useNotificationStore = create((set, get) => ({
  // Centre de notifications (historique persistant)
  notifications: [],
  unreadCount: 0,

  // Toasts visibles à l'écran
  toasts: [],

  // Ajouter une notification (et un toast)
  add: (notif) => {
    // Déduplication : même dedupeKey ou même (title+source) déjà visible à l'écran → skip
    const dedupeKey = notif.dedupeKey || `${notif.title}::${notif.source || ''}`
    const alreadyVisible = get().toasts.some(t =>
      t.dedupeKey === dedupeKey ||
      (!notif.dedupeKey && t.title === notif.title && t.source === (notif.source || ''))
    )
    if (alreadyVisible) return null

    const id = ++_id
    const entry = {
      id,
      dedupeKey,
      type: notif.type || 'info',    // info | warning | critical
      title: notif.title || '',
      body: notif.body || '',
      ts: new Date(),
      read: false,
      persistent: notif.persistent || notif.type === 'critical',
      source: notif.source || '',
    }
    set(s => ({
      notifications: [entry, ...s.notifications].slice(0, 200),
      unreadCount: s.unreadCount + 1,
      toasts: [...s.toasts, { ...entry, removing: false }].slice(-6),
    }))

    // Auto-dismiss pour non-critiques
    if (!entry.persistent) {
      const delay = notif.type === 'warning' ? 6000 : 4000
      setTimeout(() => get().dismissToast(id), delay)
    }
    return id
  },

  dismissToast: (id) => {
    set(s => ({ toasts: s.toasts.filter(t => t.id !== id) }))
  },

  markRead: (id) => {
    set(s => ({
      notifications: s.notifications.map(n => n.id === id ? { ...n, read: true } : n),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }))
  },

  markAllRead: () => {
    set(s => ({
      notifications: s.notifications.map(n => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },

  clear: () => set({ notifications: [], unreadCount: 0, toasts: [] }),
}))

// Helper raccourci pour ajouter depuis n'importe où
export const notify = (type, title, body = '', opts = {}) => {
  useNotificationStore.getState().add({ type, title, body, ...opts })
}
