import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const TABS = [
  { id: 'memories', label: '🧠 Mémoires' },
  { id: 'search',   label: '🔍 Recherche' },
  { id: 'profile',  label: '👤 Profil'    },
  { id: 'stats',    label: '📊 Stats'     },
]

const TYPE_COLORS = {
  user: { bg: 'rgba(139,92,246,0.15)', border: 'rgba(139,92,246,0.4)', color: '#a78bfa' },
  long: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.35)', color: '#6ee7b7' },
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr + 'Z').getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'à l\'instant'
  if (m < 60) return `il y a ${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  return `il y a ${Math.floor(h / 24)}j`
}

function importanceBar(val) {
  const pct = Math.round(val * 100)
  const color = val >= 0.8 ? '#f59e0b' : val >= 0.5 ? '#818cf8' : '#64748b'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        width: 48, height: 4, borderRadius: 2,
        background: 'rgba(255,255,255,0.08)', overflow: 'hidden',
      }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: '0.67rem', color: '#64748b' }}>{pct}%</span>
    </div>
  )
}

/* ──────────────────────────── ONGLET MÉMOIRES ───────────────────────────── */
function TabMemories() {
  const [memories, setMemories]   = useState([])
  const [filter,   setFilter]     = useState('all')
  const [search,   setSearch]     = useState('')
  const [deleting, setDeleting]   = useState(null)
  const [showAdd,  setShowAdd]    = useState(false)
  const [form,     setForm]       = useState({ type: 'user', key: '', value: '', importance: 0.7 })
  const [saving,   setSaving]     = useState(false)

  const load = async () => {
    const params = filter !== 'all' ? `?memory_type=${filter}` : ''
    const r = await apiFetch(`/memory/get${params}`)
    if (r.ok) setMemories(await r.json())
  }

  useEffect(() => { load() }, [filter])

  const handleDelete = async (id) => {
    setDeleting(id)
    await apiFetch(`/memory/${id}`, { method: 'DELETE' })
    await load()
    setDeleting(null)
  }

  const handleAdd = async () => {
    if (!form.key.trim() || !form.value.trim()) return
    setSaving(true)
    await apiFetch('/memory/save', {
      method: 'POST',
      body: JSON.stringify({ memory_type: form.type, key: form.key, value: form.value, importance: parseFloat(form.importance) }),
    })
    setForm({ type: 'user', key: '', value: '', importance: 0.7 })
    setShowAdd(false)
    setSaving(false)
    load()
  }

  const visible = memories.filter(m =>
    !search || m.key.toLowerCase().includes(search.toLowerCase()) || m.value.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
      {/* Barre contrôles */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Filtre type */}
        <div style={{ display: 'flex', gap: 4 }}>
          {['all','user','long'].map(t => (
            <button key={t} onClick={() => setFilter(t)}
              className={filter === t ? 'mem-filter-btn active' : 'mem-filter-btn'}>
              {t === 'all' ? 'Tout' : t}
            </button>
          ))}
        </div>

        {/* Recherche locale */}
        <input
          className="mem-search-input"
          placeholder="Filtrer…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <span className="mem-badge">{visible.length}</span>
          <button className="mem-add-btn" onClick={() => setShowAdd(v => !v)}>
            {showAdd ? '✕ Annuler' : '+ Ajouter'}
          </button>
        </div>
      </div>

      {/* Formulaire d'ajout */}
      {showAdd && (
        <div className="mem-add-form">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <select className="mem-input" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))} style={{ width: 90 }}>
              <option value="user">user</option>
              <option value="long">long</option>
            </select>
            <input className="mem-input" placeholder="Clé / sujet" value={form.key}
              onChange={e => setForm(f => ({ ...f, key: e.target.value }))} style={{ flex: 1, minWidth: 120 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>Importance</span>
              <input type="range" min="0" max="1" step="0.05" value={form.importance}
                onChange={e => setForm(f => ({ ...f, importance: e.target.value }))}
                style={{ width: 70 }} />
              <span style={{ fontSize: '0.72rem', color: 'var(--text2)', width: 28 }}>{Math.round(form.importance * 100)}%</span>
            </div>
          </div>
          <textarea className="mem-input mem-textarea" placeholder="Valeur / contenu de la mémoire…"
            value={form.value} onChange={e => setForm(f => ({ ...f, value: e.target.value }))}
            rows={3} />
          <button className="mem-save-btn" onClick={handleAdd} disabled={saving || !form.key.trim() || !form.value.trim()}>
            {saving ? 'Enregistrement…' : '💾 Enregistrer'}
          </button>
        </div>
      )}

      {/* Liste */}
      <div className="memory-scroll">
        {visible.length === 0 ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">✨</div>
            <div>Aucune mémoire{search ? ' correspondante' : ''}.<br />Parle-moi pour que je mémorise.</div>
          </div>
        ) : (
          <div className="memory-grid">
            {visible.map(m => {
              const tc = TYPE_COLORS[m.type] || TYPE_COLORS.user
              return (
                <div key={m.id} className="memory-card">
                  <span className="mem-type-badge" style={{ background: tc.bg, borderColor: tc.border, color: tc.color }}>
                    {m.type}
                  </span>
                  <div className="mem-body">
                    <div className="mem-key-text">{m.key}</div>
                    <div className="mem-value-text">{m.value}</div>
                    <div style={{ marginTop: 6 }}>{importanceBar(m.importance)}</div>
                  </div>
                  <div className="mem-right">
                    <span style={{ fontSize: '0.67rem', color: 'var(--text3)' }}>{timeAgo(m.updated_at)}</span>
                    <button className="mem-del-btn" onClick={() => handleDelete(m.id)}
                      disabled={deleting === m.id} title="Supprimer">
                      {deleting === m.id ? '…' : '✕'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── ONGLET RECHERCHE ──────────────────────────── */
function TabSearch() {
  const [query,   setQuery]   = useState('')
  const [k,       setK]       = useState(5)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    const r = await apiFetch(`/memory/search?q=${encodeURIComponent(query)}&k=${k}`)
    if (r.ok) {
      setResults(await r.json())
    } else {
      const e = await r.json().catch(() => ({}))
      setError(e.detail || 'Erreur recherche vectorielle')
    }
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Barre recherche */}
      <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text3)', marginBottom: 10 }}>
          Recherche sémantique vectorielle — retrouve les mémoires par sens, pas seulement par mot-clé.
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input ref={inputRef} className="mem-search-input" style={{ flex: 1, fontSize: '0.9rem', padding: '9px 14px' }}
            placeholder="Que veux-tu retrouver ?"
            value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>Top</span>
            <select className="mem-input" value={k} onChange={e => setK(+e.target.value)} style={{ width: 55, padding: '6px 8px' }}>
              {[3,5,10,15,20].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <button className="mem-save-btn" onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? '…' : '🔍'}
          </button>
        </div>
        {error && <div style={{ marginTop: 8, fontSize: '0.78rem', color: '#f87171' }}>{error}</div>}
      </div>

      {/* Résultats */}
      <div className="memory-scroll">
        {results === null ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">🔮</div>
            <div>Lance une recherche pour explorer la mémoire vectorielle.</div>
          </div>
        ) : results.count === 0 ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">🌌</div>
            <div>Aucun résultat pour <strong>"{results.query}"</strong></div>
          </div>
        ) : (
          <div style={{ padding: '4px 0' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: 12 }}>
              {results.count} résultat{results.count > 1 ? 's' : ''} · moteur : <strong style={{ color: 'var(--text2)' }}>{results.backend}</strong>
            </div>
            <div className="memory-grid">
              {results.results.map((r, i) => (
                <div key={i} className="memory-card">
                  <div style={{
                    flexShrink: 0, width: 32, height: 32, borderRadius: 8,
                    background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.75rem', fontWeight: 700, color: '#a78bfa',
                  }}>#{i + 1}</div>
                  <div className="mem-body">
                    <div className="mem-key-text">{r.key || r.id}</div>
                    <div className="mem-value-text">{r.content || r.value || r.text}</div>
                  </div>
                  {r.score !== undefined && (
                    <div style={{ flexShrink: 0, textAlign: 'right' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>similarité</div>
                      <div style={{
                        fontSize: '0.85rem', fontWeight: 700,
                        color: r.score > 0.7 ? '#6ee7b7' : r.score > 0.4 ? '#a78bfa' : '#64748b',
                      }}>{(r.score * 100).toFixed(0)}%</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── ONGLET PROFIL ─────────────────────────────── */
function TabProfile() {
  const [profile,  setProfile]  = useState({})
  const [editing,  setEditing]  = useState(null)
  const [editVal,  setEditVal]  = useState('')
  const [newField, setNewField] = useState({ field: '', value: '' })
  const [showNew,  setShowNew]  = useState(false)
  const [saving,   setSaving]   = useState(false)

  const load = async () => {
    const r = await apiFetch('/memory/profile')
    if (r.ok) setProfile(await r.json())
  }

  useEffect(() => { load() }, [])

  const handleSave = async (field, value) => {
    setSaving(field)
    await apiFetch('/memory/profile', { method: 'POST', body: JSON.stringify({ field, value }) })
    setSaving(null)
    setEditing(null)
    load()
  }

  const handleAddField = async () => {
    if (!newField.field.trim() || !newField.value.trim()) return
    setSaving('new')
    await apiFetch('/memory/profile', { method: 'POST', body: JSON.stringify({ field: newField.field, value: newField.value }) })
    setSaving(null)
    setNewField({ field: '', value: '' })
    setShowNew(false)
    load()
  }

  const entries = Object.entries(profile)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text3)' }}>{entries.length} champ{entries.length > 1 ? 's' : ''}</span>
        <button className="mem-add-btn" onClick={() => setShowNew(v => !v)}>
          {showNew ? '✕ Annuler' : '+ Nouveau champ'}
        </button>
      </div>

      {showNew && (
        <div className="mem-add-form">
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="mem-input" placeholder="Nom du champ (ex: prénom)" style={{ flex: 1 }}
              value={newField.field} onChange={e => setNewField(f => ({ ...f, field: e.target.value }))} />
            <input className="mem-input" placeholder="Valeur" style={{ flex: 2 }}
              value={newField.value} onChange={e => setNewField(f => ({ ...f, value: e.target.value }))} />
          </div>
          <button className="mem-save-btn" onClick={handleAddField}
            disabled={saving === 'new' || !newField.field.trim() || !newField.value.trim()}>
            {saving === 'new' ? 'Enregistrement…' : '💾 Ajouter'}
          </button>
        </div>
      )}

      <div className="memory-scroll">
        {entries.length === 0 ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">👤</div>
            <div>Aucun champ de profil.<br />Parle à l'IA pour qu'elle apprenne à te connaître.</div>
          </div>
        ) : (
          <div className="memory-grid">
            {entries.map(([field, value]) => (
              <div key={field} className="memory-card">
                <div className="mem-body">
                  <div className="mem-key-text">{field}</div>
                  {editing === field ? (
                    <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                      <input className="mem-input" style={{ flex: 1 }}
                        value={editVal} onChange={e => setEditVal(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') handleSave(field, editVal); if (e.key === 'Escape') setEditing(null) }}
                        autoFocus />
                      <button className="mem-save-btn" style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                        onClick={() => handleSave(field, editVal)} disabled={saving === field}>
                        {saving === field ? '…' : '✓'}
                      </button>
                      <button className="mem-del-btn" onClick={() => setEditing(null)}>✕</button>
                    </div>
                  ) : (
                    <div className="mem-value-text" style={{ marginTop: 3 }}>{value}</div>
                  )}
                </div>
                {editing !== field && (
                  <button className="mem-edit-btn" onClick={() => { setEditing(field); setEditVal(value) }} title="Modifier">
                    ✏️
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── ONGLET STATS ──────────────────────────────── */
function TabStats() {
  const [memories,    setMemories]    = useState([])
  const [vectorStats, setVectorStats] = useState(null)
  const [reindexing,  setReindexing]  = useState(false)
  const [reindexMsg,  setReindexMsg]  = useState('')

  useEffect(() => {
    apiFetch('/memory/get?limit=500').then(r => r.ok && r.json()).then(d => d && setMemories(d))
    apiFetch('/memory/vector/stats').then(r => r.ok && r.json()).then(d => d && setVectorStats(d))
  }, [])

  const byType = memories.reduce((acc, m) => { acc[m.type] = (acc[m.type] || 0) + 1; return acc }, {})
  const avgImportance = memories.length ? (memories.reduce((s, m) => s + m.importance, 0) / memories.length) : 0
  const topMemories = [...memories].sort((a, b) => b.importance - a.importance).slice(0, 5)

  const handleReindex = async () => {
    setReindexing(true)
    setReindexMsg('')
    const r = await apiFetch('/memory/reindex', { method: 'POST' })
    if (r.ok) {
      const d = await r.json()
      setReindexMsg(`✅ ${d.indexed} mémoire${d.indexed > 1 ? 's' : ''} réindexée${d.indexed > 1 ? 's' : ''}`)
    } else {
      setReindexMsg('❌ Erreur lors de la réindexation')
    }
    setReindexing(false)
  }

  return (
    <div className="memory-scroll">
      {/* Grille de stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Total mémoires', value: memories.length, icon: '🧠', color: '#a78bfa' },
          { label: 'Importance moy.', value: `${Math.round(avgImportance * 100)}%`, icon: '⭐', color: '#f59e0b' },
          { label: 'Types distincts', value: Object.keys(byType).length, icon: '🏷️', color: '#6ee7b7' },
          { label: 'Vecteurs indexés', value: vectorStats?.total_documents ?? '…', icon: '🔮', color: '#38bdf8' },
        ].map(s => (
          <div key={s.label} style={{
            background: 'var(--glass2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '16px', display: 'flex', flexDirection: 'column', gap: 6, backdropFilter: 'blur(12px)',
          }}>
            <span style={{ fontSize: '1.4rem' }}>{s.icon}</span>
            <span style={{ fontSize: '1.5rem', fontWeight: 700, color: s.color }}>{s.value}</span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Répartition par type */}
      {Object.keys(byType).length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text2)', fontWeight: 600, marginBottom: 10 }}>Répartition par type</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {Object.entries(byType).map(([type, count]) => {
              const pct = Math.round((count / memories.length) * 100)
              const tc = TYPE_COLORS[type] || TYPE_COLORS.user
              return (
                <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 44, fontSize: '0.72rem', color: tc.color, fontWeight: 700, textTransform: 'uppercase' }}>{type}</span>
                  <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.07)' }}>
                    <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: tc.color, opacity: 0.75 }} />
                  </div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text3)', width: 48, textAlign: 'right' }}>{count} ({pct}%)</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Top mémoires */}
      {topMemories.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text2)', fontWeight: 600, marginBottom: 10 }}>Top 5 par importance</div>
          <div className="memory-grid">
            {topMemories.map((m, i) => (
              <div key={m.id} className="memory-card">
                <div style={{
                  flexShrink: 0, width: 26, height: 26, borderRadius: 6,
                  background: i === 0 ? 'rgba(245,158,11,0.2)' : 'rgba(139,92,246,0.12)',
                  border: `1px solid ${i === 0 ? 'rgba(245,158,11,0.4)' : 'rgba(139,92,246,0.25)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.72rem', fontWeight: 700,
                  color: i === 0 ? '#f59e0b' : '#a78bfa',
                }}>#{i + 1}</div>
                <div className="mem-body">
                  <div className="mem-key-text">{m.key}</div>
                  <div className="mem-value-text" style={{ fontSize: '0.8rem' }}>{m.value.slice(0, 120)}{m.value.length > 120 ? '…' : ''}</div>
                </div>
                <div style={{ flexShrink: 0 }}>{importanceBar(m.importance)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Moteur vectoriel */}
      <div style={{
        background: 'var(--glass2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
        padding: 16, backdropFilter: 'blur(12px)',
      }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text2)', fontWeight: 600, marginBottom: 10 }}>Moteur vectoriel</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
          {vectorStats && Object.entries(vectorStats).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
              <span style={{ color: 'var(--text3)' }}>{k}</span>
              <span style={{ color: 'var(--text2)', fontWeight: 600 }}>{String(v)}</span>
            </div>
          ))}
        </div>
        <button className="mem-save-btn" onClick={handleReindex} disabled={reindexing}>
          {reindexing ? '⏳ Réindexation…' : '🔄 Réindexer toutes les mémoires'}
        </button>
        {reindexMsg && <div style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text2)' }}>{reindexMsg}</div>}
      </div>
    </div>
  )
}

/* ──────────────────────────── COMPOSANT PRINCIPAL ───────────────────────── */
export default function MemoryView() {
  const [tab, setTab] = useState('memories')

  return (
    <div className="memory-view">
      {/* Header */}
      <div className="memory-header">
        <div className="memory-title">🧠 Mémoire cosmique</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {TABS.map(t => (
            <button key={t.id}
              className={tab === t.id ? 'mem-tab-btn active' : 'mem-tab-btn'}
              onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Contenu onglet */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'memories' && <TabMemories />}
        {tab === 'search'   && <TabSearch />}
        {tab === 'profile'  && <TabProfile />}
        {tab === 'stats'    && <TabStats />}
      </div>
    </div>
  )
}
