import { useState, useEffect } from 'react'
import Chat from './components/Chat'
import Sidebar from './components/Sidebar'
import StarField from './components/StarField'
import './App.css'

export default function App() {
  // Session persistante — survit aux rechargements de page
  const [sessionId] = useState(() => {
    const stored = localStorage.getItem('eye_session_id')
    if (stored) return stored
    const id = crypto.randomUUID()
    localStorage.setItem('eye_session_id', id)
    return id
  })
  const [view,  setView]  = useState('chat')
  const [theme, setTheme] = useState('galactic')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <>
      <StarField theme={theme} />
      <div className="app">
        <Sidebar view={view} onNav={setView} theme={theme} onTheme={setTheme} />
        <main className="main">
          {view === 'chat'   && <Chat sessionId={sessionId} />}
          {view === 'memory' && <MemoryView />}
        </main>
      </div>
    </>
  )
}

function MemoryView() {
  const [memories, setMemories] = useState([])
  const [deleting, setDeleting] = useState(null)

  const load = () =>
    fetch('/api/memory/get').then(r => r.json()).then(setMemories).catch(() => {})

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    setDeleting(id)
    await fetch(`/api/memory/${id}`, { method: 'DELETE' })
    await load()
    setDeleting(null)
  }

  return (
    <div className="memory-view">
      <div className="memory-header">
        <div className="memory-title">
          🧠 Mémoire cosmique
          <span className="mem-badge">{memories.length}</span>
        </div>
      </div>
      <div className="memory-scroll">
        {memories.length === 0 ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">✨</div>
            <div>Aucune mémoire enregistrée.<br />Commence à parler pour que je mémorise.</div>
          </div>
        ) : (
          <div className="memory-grid">
            {memories.map(m => (
              <div key={m.id} className="memory-card">
                <span className="mem-type-badge">{m.type}</span>
                <div className="mem-body">
                  <div className="mem-key-text">{m.key}</div>
                  <div className="mem-value-text">{m.value}</div>
                </div>
                <div className="mem-right">
                  <span className="mem-importance">{(m.importance * 100).toFixed(0)}%</span>
                  <button className="mem-del-btn" onClick={() => handleDelete(m.id)}
                    disabled={deleting === m.id} title="Supprimer">
                    {deleting === m.id ? '…' : '✕'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
