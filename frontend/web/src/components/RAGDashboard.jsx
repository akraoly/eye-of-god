import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

const COLLECTIONS = [
  { id: 'conversations', label: 'Conversations', icon: '💬', color: '#4af' },
  { id: 'knowledge',     label: 'Knowledge',     icon: '📚', color: '#4f4' },
  { id: 'memories',      label: 'Mémoires',      icon: '🧠', color: '#f84' },
]

function StatCard({ icon, label, value, total, color }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : (value > 0 ? 100 : 0)
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px',
      border: `1px solid ${color}33`, flex: 1, minWidth: 160,
    }}>
      <div style={{ fontSize: '1.4rem', marginBottom: 6 }}>{icon}</div>
      <div style={{ color, fontWeight: 700, fontSize: '1.5rem' }}>{value.toLocaleString()}</div>
      {total > 0 && (
        <div style={{ color: '#888', fontSize: '0.75rem' }}>/ {total.toLocaleString()} — {pct}%</div>
      )}
      <div style={{ color: '#aaa', fontSize: '0.8rem', marginTop: 4 }}>{label}</div>
      {total > 0 && (
        <div style={{ background: '#222', borderRadius: 4, height: 4, marginTop: 8 }}>
          <div style={{ background: color, width: `${pct}%`, height: 4, borderRadius: 4, transition: 'width 0.6s' }} />
        </div>
      )}
    </div>
  )
}

function ResultCard({ result, idx }) {
  const [expanded, setExpanded] = useState(false)
  const meta = result.metadata || {}
  const collectionColors = { conversations: '#4af', knowledge: '#4f4', memories: '#f84' }
  const color = collectionColors[result.collection] || '#aaa'

  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)', borderRadius: 10,
      border: `1px solid ${color}44`, padding: '12px 16px', marginBottom: 10,
      cursor: 'pointer',
    }} onClick={() => setExpanded(e => !e)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{
            background: color + '22', color, borderRadius: 6,
            padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700,
          }}>{result.collection}</span>
          <span style={{ color: '#888', fontSize: '0.78rem' }}>
            {meta.title || meta.session_id?.slice(0, 8) || meta.key || `résultat ${idx + 1}`}
          </span>
        </div>
        <span style={{
          background: result.score > 0.7 ? '#0f04' : result.score > 0.4 ? '#ff84' : '#f004',
          color: result.score > 0.7 ? '#0f8' : result.score > 0.4 ? '#fa0' : '#f66',
          borderRadius: 6, padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700,
        }}>score {(result.score * 100).toFixed(0)}%</span>
      </div>
      <div style={{
        color: '#ccc', fontSize: '0.82rem', marginTop: 8,
        maxHeight: expanded ? 'none' : 64, overflow: 'hidden',
        display: '-webkit-box', WebkitLineClamp: expanded ? 'unset' : 3,
        WebkitBoxOrient: 'vertical',
      }}>
        {result.text}
      </div>
      {meta.date && (
        <div style={{ color: '#555', fontSize: '0.7rem', marginTop: 6 }}>
          {new Date(meta.date).toLocaleDateString('fr-FR')}
        </div>
      )}
    </div>
  )
}

export default function RAGDashboard() {
  const [stats, setStats] = useState(null)
  const [dbStats, setDbStats] = useState({ conversations: 227, knowledge: 53, memories: 8 })
  const [loading, setLoading] = useState(false)
  const [indexing, setIndexing] = useState(false)
  const [indexProgress, setIndexProgress] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [query, setQuery] = useState('')
  const [collection, setCollection] = useState('all')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [ragChat, setRagChat] = useState('')
  const [ragResponse, setRagResponse] = useState(null)
  const [chatLoading, setChatLoading] = useState(false)
  const [tab, setTab] = useState('stats')
  const [rebuildTarget, setRebuildTarget] = useState('')
  const [rebuildConfirm, setRebuildConfirm] = useState(false)
  const [error, setError] = useState('')

  const loadStats = useCallback(async () => {
    setLoading(true)
    try {
      const r = await apiFetch('/rag/stats')
      if (r.ok) setStats(await r.json())
    } catch (e) {
      setError('Impossible de charger les stats ChromaDB')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  // Poll task status
  useEffect(() => {
    if (!taskId) return
    const iv = setInterval(async () => {
      try {
        const r = await apiFetch(`/rag/index-status/${taskId}`)
        if (r.ok) {
          const data = await r.json()
          setIndexProgress(data)
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(iv)
            setIndexing(false)
            setTaskId(null)
            loadStats()
          }
        }
      } catch {}
    }, 1500)
    return () => clearInterval(iv)
  }, [taskId, loadStats])

  const handleIndexAll = async () => {
    setIndexing(true)
    setIndexProgress({ status: 'queued' })
    try {
      const r = await apiFetch('/rag/index-all', { method: 'POST' })
      if (r.ok) {
        const data = await r.json()
        setTaskId(data.task_id)
      } else {
        setIndexing(false)
        setError("Erreur au lancement de l'indexation")
      }
    } catch (e) {
      setIndexing(false)
      setError(String(e))
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    setResults([])
    try {
      const r = await apiFetch('/rag/query', {
        method: 'POST',
        body: JSON.stringify({ query, collection, n_results: 8 }),
      })
      if (r.ok) {
        const data = await r.json()
        setResults(data.results || [])
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setSearching(false)
    }
  }

  const handleRebuild = async () => {
    if (!rebuildTarget) return
    try {
      const r = await apiFetch(`/rag/rebuild/${rebuildTarget}`, { method: 'POST' })
      if (r.ok) {
        setRebuildConfirm(false)
        setRebuildTarget('')
        loadStats()
      }
    } catch (e) {
      setError(String(e))
    }
  }

  const handleRagChat = async (e) => {
    e.preventDefault()
    if (!ragChat.trim()) return
    setChatLoading(true)
    setRagResponse(null)
    try {
      const r = await apiFetch('/rag/chat-with-context', {
        method: 'POST',
        body: JSON.stringify({ query: ragChat, collection: 'conversations', n_results: 5 }),
      })
      if (r.ok) setRagResponse(await r.json())
    } catch (e) {
      setError(String(e))
    } finally {
      setChatLoading(false)
    }
  }

  const totalVectors = stats?.total_vectors ?? 0
  const chromaStatus = loading ? '⏳' : totalVectors > 0 ? '✅' : '🔴'

  return (
    <div style={{ padding: '24px 28px', color: '#ddd', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', color: '#fff' }}>
            🧠 RAG Semantic Engine
          </h2>
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '0.85rem' }}>
            ChromaDB {chromaStatus} · {totalVectors.toLocaleString()} vecteurs indexés
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={loadStats} disabled={loading} style={btnStyle('#333')}>
            {loading ? '⏳' : '🔄'} Actualiser
          </button>
          <button onClick={handleIndexAll} disabled={indexing} style={btnStyle('#1a4a2a')}>
            {indexing ? '⏳ Indexation...' : '⚡ Index All'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#ff000022', border: '1px solid #f44', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#f88' }}>
          ⚠️ {error} <button onClick={() => setError('')} style={{ marginLeft: 10, background: 'none', border: 'none', color: '#f88', cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* Index progress */}
      {indexProgress && (
        <div style={{ background: 'rgba(0,255,100,0.06)', border: '1px solid #0f44', borderRadius: 10, padding: '12px 16px', marginBottom: 20 }}>
          <div style={{ fontWeight: 700, color: indexProgress.status === 'failed' ? '#f66' : '#4f8' }}>
            {indexProgress.status === 'queued' && '⏳ En file...'}
            {indexProgress.status === 'running' && '🔄 Indexation en cours...'}
            {indexProgress.status === 'completed' && '✅ Indexation terminée'}
            {indexProgress.status === 'failed' && '❌ Erreur indexation'}
          </div>
          {indexProgress.result && (
            <div style={{ color: '#aaa', fontSize: '0.82rem', marginTop: 6 }}>
              Conversations: {indexProgress.result.conversations} chunks ·
              Knowledge: {indexProgress.result.knowledge} chunks ·
              Mémoires: {indexProgress.result.memories} chunks ·
              Total: {indexProgress.result.total_chunks} vecteurs
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #333', paddingBottom: 0 }}>
        {[['stats', '📊 Stats'], ['search', '🔍 Recherche'], ['chat', '💬 Chat RAG'], ['tools', '🔧 Outils']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: '8px 16px', background: 'none', border: 'none', cursor: 'pointer',
            color: tab === id ? '#4af' : '#888', borderBottom: tab === id ? '2px solid #4af' : '2px solid transparent',
            fontWeight: tab === id ? 700 : 400, transition: 'color 0.2s',
          }}>{label}</button>
        ))}
      </div>

      {/* Tab: Stats */}
      {tab === 'stats' && (
        <div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 24 }}>
            <StatCard icon="💬" label="Chunks conversations" value={stats?.conversations ?? 0} total={0} color="#4af" />
            <StatCard icon="📚" label="Chunks knowledge" value={stats?.knowledge ?? 0} total={0} color="#4f4" />
            <StatCard icon="🧠" label="Souvenirs indexés" value={stats?.memories ?? 0} total={0} color="#f84" />
            <StatCard icon="🌐" label="Total vecteurs" value={totalVectors} total={0} color="#aa4" />
          </div>

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px', flex: 1, minWidth: 200 }}>
              <div style={{ color: '#888', fontSize: '0.82rem', marginBottom: 8 }}>Source de données</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'Conversations DB', value: dbStats.conversations, color: '#4af' },
                  { label: 'Articles knowledge', value: dbStats.knowledge, color: '#4f4' },
                  { label: 'Souvenirs', value: dbStats.memories, color: '#f84' },
                ].map(r => (
                  <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#aaa', fontSize: '0.82rem' }}>{r.label}</span>
                    <span style={{ color: r.color, fontWeight: 700 }}>{r.value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px', flex: 1, minWidth: 200 }}>
              <div style={{ color: '#888', fontSize: '0.82rem', marginBottom: 8 }}>ChromaDB</div>
              <div style={{ color: '#fff', fontWeight: 700, fontSize: '1.1rem' }}>
                {stats?.backend || 'chromadb'}
              </div>
              <div style={{ color: '#888', fontSize: '0.8rem', marginTop: 4 }}>
                Disque : {stats?.disk_mb ?? 0} MB
              </div>
              <div style={{ color: '#888', fontSize: '0.8rem' }}>
                Statut : {totalVectors > 0 ? '✅ Peuplé' : '🔴 Vide — cliquer "Index All"'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Search */}
      {tab === 'search' && (
        <div>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Recherche sémantique... ex: 'configuration JWT', 'erreur uvicorn'"
              style={inputStyle}
            />
            <select value={collection} onChange={e => setCollection(e.target.value)}
              style={{ ...inputStyle, width: 'auto', padding: '8px 12px' }}>
              <option value="all">Toutes</option>
              {COLLECTIONS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
            <button type="submit" disabled={searching} style={btnStyle('#1a3a5a')}>
              {searching ? '⏳' : '🔍'} Search
            </button>
          </form>

          {results.length === 0 && !searching && (
            <div style={{ color: '#555', textAlign: 'center', padding: 40 }}>
              {query ? 'Aucun résultat — essayez un autre terme ou lancez "Index All"' : 'Tapez une requête et appuyez sur Search'}
            </div>
          )}

          {results.map((r, i) => <ResultCard key={r.id || i} result={r} idx={i} />)}
        </div>
      )}

      {/* Tab: Chat RAG */}
      {tab === 'chat' && (
        <div>
          <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 16 }}>
            Le chat RAG enrichit chaque message avec le contexte le plus pertinent de ChromaDB avant d'interroger Claude.
          </p>
          <form onSubmit={handleRagChat} style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <input
              value={ragChat}
              onChange={e => setRagChat(e.target.value)}
              placeholder="Pose une question... ex: 'Qu'avons-nous discuté sur le module AEGIS ?'"
              style={inputStyle}
            />
            <button type="submit" disabled={chatLoading} style={btnStyle('#1a2a4a')}>
              {chatLoading ? '⏳' : '💬'} Envoyer
            </button>
          </form>

          {ragResponse && (
            <div>
              <div style={{ background: 'rgba(68,170,255,0.08)', border: '1px solid #4af4', borderRadius: 12, padding: '16px 20px', marginBottom: 16 }}>
                <div style={{ color: '#4af', fontWeight: 700, marginBottom: 8 }}>Réponse ({ragResponse.context_used} sources)</div>
                <div style={{ color: '#ddd', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{ragResponse.response}</div>
              </div>
              {ragResponse.sources?.length > 0 && (
                <div>
                  <div style={{ color: '#666', fontSize: '0.8rem', marginBottom: 8 }}>Sources utilisées</div>
                  {ragResponse.sources.map((s, i) => (
                    <div key={i} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: '8px 12px', marginBottom: 6, fontSize: '0.78rem' }}>
                      <span style={{ color: '#888' }}>{s.source}</span> ·
                      <span style={{ color: s.score > 0.7 ? '#4f8' : '#fa0', marginLeft: 6 }}>score {(s.score * 100).toFixed(0)}%</span>
                      <div style={{ color: '#666', marginTop: 4 }}>{s.preview}...</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab: Tools */}
      {tab === 'tools' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px' }}>
            <div style={{ fontWeight: 700, marginBottom: 12 }}>🗑️ Reconstruire une collection</div>
            <p style={{ color: '#888', fontSize: '0.82rem', margin: '0 0 12px' }}>
              Supprime et réindexe une collection ChromaDB depuis la base SQLite.
            </p>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <select value={rebuildTarget} onChange={e => { setRebuildTarget(e.target.value); setRebuildConfirm(false) }}
                style={{ ...inputStyle, width: 'auto', padding: '8px 12px' }}>
                <option value="">-- Choisir --</option>
                {COLLECTIONS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                <option value="all">Toutes</option>
              </select>
              {rebuildTarget && !rebuildConfirm && (
                <button onClick={() => setRebuildConfirm(true)} style={btnStyle('#4a1a1a')}>
                  Reconstruire
                </button>
              )}
              {rebuildConfirm && (
                <>
                  <span style={{ color: '#f84', fontSize: '0.82rem' }}>Confirmer ?</span>
                  <button onClick={handleRebuild} style={btnStyle('#8a1a1a')}>✓ Oui</button>
                  <button onClick={() => setRebuildConfirm(false)} style={btnStyle('#333')}>✕ Annuler</button>
                </>
              )}
            </div>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 20px' }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>ℹ️ À propos du RAG</div>
            <ul style={{ color: '#888', fontSize: '0.82rem', lineHeight: 1.8, margin: 0, paddingLeft: 20 }}>
              <li>ChromaDB stocke les embeddings dans <code>./data/chroma</code></li>
              <li>L'indexation utilise les embeddings natifs ChromaDB (sentence-transformers)</li>
              <li>3 collections : conversations, knowledge, memories</li>
              <li>Chunking : 2000 chars (conv) / 3000 chars (knowledge) avec overlap</li>
              <li>Le middleware RAG indexe automatiquement chaque nouveau message</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

const btnStyle = (bg) => ({
  background: bg, color: '#fff', border: '1px solid #444',
  borderRadius: 8, padding: '9px 16px', cursor: 'pointer',
  fontSize: '0.85rem', fontWeight: 600, whiteSpace: 'nowrap',
})

const inputStyle = {
  flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid #444',
  borderRadius: 8, padding: '9px 14px', color: '#fff', fontSize: '0.85rem',
  outline: 'none',
}
