import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

const api = (path, opts) => apiFetch(path, opts).then(r => r.json())

const CATEGORIES = ['general','tech','security','osint','code','research','notes','reference']

export default function KnowledgeView() {
  const [entries,  setEntries]  = useState([])
  const [stats,    setStats]    = useState(null)
  const [query,    setQuery]    = useState('')
  const [catFilter,setCatFilter]= useState('')
  const [loading,  setLoading]  = useState(false)
  const [showAdd,  setShowAdd]  = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [list, s] = await Promise.all([
        api(`/knowledge/list?limit=100${catFilter ? `&category=${catFilter}` : ''}`),
        api('/knowledge/stats'),
      ])
      setEntries(list.entries || []); setStats(s)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [catFilter])

  const search = async () => {
    if (!query.trim()) { load(); return }
    setLoading(true)
    try {
      const res = await api(`/knowledge/search?q=${encodeURIComponent(query)}&limit=20`)
      setEntries(res.results || [])
    } finally { setLoading(false) }
  }

  const del = async (id) => {
    await api(`/knowledge/${id}`, { method: 'DELETE' })
    load()
  }

  return (
    <div className="panel-view">
      {/* Stats bar */}
      {stats && (
        <div className="kv-stats-bar">
          <span className="kv-stat-pill">📚 {stats.total_entries || 0} entrées</span>
          <span className="kv-stat-pill">📂 {stats.categories?.length || 0} catégories</span>
          {stats.most_used_category && (
            <span className="kv-stat-pill">🏷️ {stats.most_used_category}</span>
          )}
          <button className="cv-btn kv-add-btn" onClick={() => setShowAdd(v => !v)}>
            {showAdd ? '✕ Fermer' : '+ Ajouter'}
          </button>
        </div>
      )}

      {/* Formulaire ajout */}
      {showAdd && <AddForm onSaved={() => { setShowAdd(false); load() }} />}

      {/* Recherche + filtre */}
      <div className="kv-search-row">
        <input className="cv-input" value={query} onChange={e => setQuery(e.target.value)}
          placeholder="Rechercher dans la base…" onKeyDown={e => e.key==='Enter' && search()} />
        <button className="cv-btn" onClick={search}>🔍</button>
        <select className="cv-select" value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          <option value="">Toutes les catégories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="cv-btn-icon" onClick={load} title="Rafraîchir">↻</button>
      </div>

      {/* Liste */}
      <div className="kv-list">
        {loading && <div className="cv-hint">Chargement…</div>}
        {!loading && entries.length === 0 && (
          <div className="cv-hint">Aucune entrée. Ajoute tes premières connaissances.</div>
        )}
        {entries.map(e => (
          <div key={e.id} className="kv-entry">
            <div className="kv-entry-header">
              <span className="kv-entry-title">{e.title || '(sans titre)'}</span>
              <span className="kv-cat-badge">{e.category}</span>
              <button className="kv-del-btn" onClick={() => del(e.id)} title="Supprimer">✕</button>
            </div>
            <div className="kv-entry-body">
              {(e.summary || e.content || '').slice(0, 200)}{(e.summary || e.content || '').length > 200 ? '…' : ''}
            </div>
            {e.tags && e.tags.length > 0 && (
              <div className="kv-tags">
                {(typeof e.tags === 'string' ? JSON.parse(e.tags) : e.tags).map((t, i) => (
                  <span key={i} className="kv-tag">#{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function AddForm({ onSaved }) {
  const [title,    setTitle]    = useState('')
  const [text,     setText]     = useState('')
  const [category, setCategory] = useState('general')
  const [tags,     setTags]     = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const save = async () => {
    if (!text.trim()) { setError('Le contenu est requis.'); return }
    setLoading(true); setError('')
    try {
      const res = await api('/knowledge/ingest', {
        method: 'POST',
        body: JSON.stringify({
          text, title, category,
          tags: tags.split(',').map(t => t.trim()).filter(Boolean),
          importance: 0.7,
        }),
      })
      if (res.error) { setError(res.error) } else { onSaved() }
    } catch { setError('Erreur réseau') }
    finally { setLoading(false) }
  }

  return (
    <div className="kv-add-form">
      <div className="cv-row">
        <input className="cv-input" value={title} onChange={e => setTitle(e.target.value)}
          placeholder="Titre (optionnel)" />
        <select className="cv-select" value={category} onChange={e => setCategory(e.target.value)}>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <textarea className="cv-textarea" value={text} onChange={e => setText(e.target.value)}
        placeholder="Contenu à mémoriser…" rows={4} />
      <div className="cv-row">
        <input className="cv-input" value={tags} onChange={e => setTags(e.target.value)}
          placeholder="Tags séparés par virgule (ex: python, api, exploit)" />
        <button className="cv-btn cv-btn-green" onClick={save} disabled={loading}>
          {loading ? '…' : 'Sauvegarder'}
        </button>
      </div>
      {error && <div className="cv-error">{error}</div>}
    </div>
  )
}
