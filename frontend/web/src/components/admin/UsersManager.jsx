import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

const ROLE_COLORS = {
  admin:   '#ff4444',
  auditor: '#ff8800',
  client:  '#4488ff',
  viewer:  '#888888',
}

const ROLE_LABELS = {
  admin:   '👑 Admin',
  auditor: '⚔️ Auditor',
  client:  '🏢 Client',
  viewer:  '👁️ Viewer',
}

function RoleBadge({ role }) {
  return (
    <span style={{
      background: (ROLE_COLORS[role] || '#666') + '22',
      color: ROLE_COLORS[role] || '#aaa',
      borderRadius: 6, padding: '2px 10px', fontSize: '0.75rem', fontWeight: 700,
    }}>{ROLE_LABELS[role] || role}</span>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: '#1a1a2e', borderRadius: 14, padding: '24px 28px',
        border: '1px solid #333', minWidth: 360, maxWidth: 480, width: '90%',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, color: '#fff' }}>{title}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function UsersManager() {
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [filterRole, setFilterRole] = useState('all')
  const [form, setForm] = useState({ username: '', password: '', display_name: '', email: '', role: 'auditor', organization: '' })

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const [uRes, rRes] = await Promise.all([
        apiFetch('/users'),
        apiFetch('/users/roles/list'),
      ])
      if (uRes.ok) setUsers(await uRes.json())
      if (rRes.ok) setRoles(await rRes.json())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  const showMsg = (msg, isError = false) => {
    if (isError) setError(msg); else setSuccess(msg)
    setTimeout(() => { setError(''); setSuccess('') }, 4000)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      const r = await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      if (r.ok) {
        showMsg(`Utilisateur "${form.username}" créé`)
        setShowCreate(false)
        setForm({ username: '', password: '', display_name: '', email: '', role: 'auditor', organization: '' })
        loadUsers()
      } else {
        const err = await r.json()
        showMsg(err.detail || 'Erreur création', true)
      }
    } catch (e) {
      showMsg(String(e), true)
    }
  }

  const handleRoleChange = async (userId, newRole) => {
    try {
      const r = await apiFetch(`/users/${userId}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: newRole }),
      })
      if (r.ok) {
        setUsers(us => us.map(u => u.id === userId ? { ...u, role: newRole } : u))
        showMsg('Rôle modifié')
      } else {
        const err = await r.json()
        showMsg(err.detail || 'Erreur', true)
      }
    } catch (e) {
      showMsg(String(e), true)
    }
  }

  const handleToggleActive = async (user) => {
    try {
      const r = await apiFetch(`/users/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      if (r.ok) {
        setUsers(us => us.map(u => u.id === user.id ? { ...u, is_active: !user.is_active } : u))
        showMsg(user.is_active ? 'Compte désactivé' : 'Compte activé')
      }
    } catch (e) {
      showMsg(String(e), true)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      const r = await apiFetch(`/users/${deleteTarget.id}`, { method: 'DELETE' })
      if (r.ok) {
        setUsers(us => us.filter(u => u.id !== deleteTarget.id))
        showMsg(`Utilisateur "${deleteTarget.username}" supprimé`)
        setDeleteTarget(null)
      } else {
        const err = await r.json()
        showMsg(err.detail || 'Erreur', true)
        setDeleteTarget(null)
      }
    } catch (e) {
      showMsg(String(e), true)
      setDeleteTarget(null)
    }
  }

  const filteredUsers = filterRole === 'all' ? users : users.filter(u => u.role === filterRole)

  return (
    <div style={{ padding: '24px 28px', color: '#ddd', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, color: '#fff' }}>👥 Gestion des utilisateurs</h2>
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '0.85rem' }}>
            {users.length} compte{users.length > 1 ? 's' : ''} · RBAC multi-rôles
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)}
            style={{ background: '#222', border: '1px solid #444', borderRadius: 8, padding: '8px 12px', color: '#fff', fontSize: '0.85rem' }}>
            <option value="all">Tous les rôles</option>
            {Object.keys(ROLE_LABELS).map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
          <button onClick={() => setShowCreate(true)} style={{ background: '#1a3a2a', color: '#4f8', border: '1px solid #4f8', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontWeight: 700 }}>
            + Ajouter
          </button>
        </div>
      </div>

      {(error || success) && (
        <div style={{ background: error ? '#ff000022' : '#00ff0011', border: `1px solid ${error ? '#f44' : '#4f4'}`, borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: error ? '#f88' : '#4f8' }}>
          {error || success}
        </div>
      )}

      {/* Roles summary */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {Object.entries(roles).map(([role, info]) => {
          const count = users.filter(u => u.role === role).length
          return (
            <div key={role} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px', border: `1px solid ${ROLE_COLORS[role] || '#333'}44` }}>
              <RoleBadge role={role} />
              <div style={{ color: '#fff', fontWeight: 700, fontSize: '1.2rem', marginTop: 4 }}>{count}</div>
              <div style={{ color: '#666', fontSize: '0.72rem' }}>{info.description}</div>
            </div>
          )
        })}
      </div>

      {/* Users table */}
      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 12, overflow: 'hidden', border: '1px solid #333' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.04)' }}>
              {['Utilisateur', 'Email', 'Rôle', 'Organisation', 'Dernière connexion', 'Statut', 'Actions'].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#888', fontSize: '0.78rem', fontWeight: 600, borderBottom: '1px solid #333' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ padding: 40, textAlign: 'center', color: '#555' }}>⏳ Chargement...</td></tr>
            ) : filteredUsers.length === 0 ? (
              <tr><td colSpan={7} style={{ padding: 40, textAlign: 'center', color: '#555' }}>Aucun utilisateur</td></tr>
            ) : filteredUsers.map(user => (
              <tr key={user.id} style={{ borderBottom: '1px solid #222', opacity: user.is_active ? 1 : 0.5 }}>
                <td style={{ padding: '10px 14px' }}>
                  <div style={{ fontWeight: 600, color: '#fff' }}>{user.display_name}</div>
                  <div style={{ color: '#666', fontSize: '0.75rem' }}>@{user.username}</div>
                </td>
                <td style={{ padding: '10px 14px', color: '#888', fontSize: '0.82rem' }}>{user.email || '—'}</td>
                <td style={{ padding: '10px 14px' }}>
                  <select
                    value={user.role || 'admin'}
                    onChange={e => handleRoleChange(user.id, e.target.value)}
                    style={{ background: '#222', border: '1px solid #444', borderRadius: 6, color: ROLE_COLORS[user.role] || '#fff', fontSize: '0.78rem', padding: '4px 8px' }}
                  >
                    {Object.keys(ROLE_LABELS).map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                  </select>
                </td>
                <td style={{ padding: '10px 14px', color: '#888', fontSize: '0.82rem' }}>{user.organization || '—'}</td>
                <td style={{ padding: '10px 14px', color: '#666', fontSize: '0.78rem' }}>
                  {user.last_login ? new Date(user.last_login).toLocaleString('fr-FR') : 'Jamais'}
                </td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{ color: user.is_active ? '#4f8' : '#f66', fontSize: '0.78rem', fontWeight: 700 }}>
                    {user.is_active ? '● Actif' : '○ Inactif'}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => handleToggleActive(user)} title={user.is_active ? 'Désactiver' : 'Activer'}
                      style={{ background: '#222', border: '1px solid #444', borderRadius: 6, color: '#aaa', cursor: 'pointer', padding: '4px 8px', fontSize: '0.8rem' }}>
                      {user.is_active ? '⏸' : '▶'}
                    </button>
                    <button onClick={() => setDeleteTarget(user)} title="Supprimer"
                      style={{ background: '#2a1a1a', border: '1px solid #f444', borderRadius: 6, color: '#f66', cursor: 'pointer', padding: '4px 8px', fontSize: '0.8rem' }}>
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      {showCreate && (
        <Modal title="Créer un utilisateur" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { key: 'username', label: 'Nom d\'utilisateur *', type: 'text', required: true },
              { key: 'password', label: 'Mot de passe * (min 6 chars)', type: 'password', required: true },
              { key: 'display_name', label: 'Nom affiché', type: 'text' },
              { key: 'email', label: 'Email', type: 'email' },
              { key: 'organization', label: 'Organisation', type: 'text' },
            ].map(f => (
              <div key={f.key}>
                <label style={{ color: '#888', fontSize: '0.78rem', display: 'block', marginBottom: 4 }}>{f.label}</label>
                <input
                  type={f.type}
                  required={f.required}
                  value={form[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  style={{ width: '100%', background: 'rgba(255,255,255,0.06)', border: '1px solid #444', borderRadius: 8, padding: '8px 12px', color: '#fff', fontSize: '0.85rem', boxSizing: 'border-box' }}
                />
              </div>
            ))}
            <div>
              <label style={{ color: '#888', fontSize: '0.78rem', display: 'block', marginBottom: 4 }}>Rôle *</label>
              <select value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value }))}
                style={{ width: '100%', background: 'rgba(255,255,255,0.06)', border: '1px solid #444', borderRadius: 8, padding: '8px 12px', color: ROLE_COLORS[form.role] || '#fff', fontSize: '0.85rem' }}>
                {Object.entries(ROLE_LABELS).map(([r, l]) => <option key={r} value={r}>{l}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              <button type="submit" style={{ flex: 1, background: '#1a4a2a', color: '#4f8', border: '1px solid #4f8', borderRadius: 8, padding: '10px', cursor: 'pointer', fontWeight: 700 }}>
                ✓ Créer
              </button>
              <button type="button" onClick={() => setShowCreate(false)} style={{ flex: 1, background: '#2a2a2a', color: '#888', border: '1px solid #444', borderRadius: 8, padding: '10px', cursor: 'pointer' }}>
                Annuler
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Delete confirm modal */}
      {deleteTarget && (
        <Modal title="Confirmer la suppression" onClose={() => setDeleteTarget(null)}>
          <p style={{ color: '#ddd', margin: '0 0 20px' }}>
            Supprimer l'utilisateur <strong style={{ color: '#f84' }}>@{deleteTarget.username}</strong> ?
            Cette action est irréversible.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={handleDelete} style={{ flex: 1, background: '#4a1a1a', color: '#f44', border: '1px solid #f44', borderRadius: 8, padding: '10px', cursor: 'pointer', fontWeight: 700 }}>
              🗑 Supprimer
            </button>
            <button onClick={() => setDeleteTarget(null)} style={{ flex: 1, background: '#2a2a2a', color: '#888', border: '1px solid #444', borderRadius: 8, padding: '10px', cursor: 'pointer' }}>
              Annuler
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
