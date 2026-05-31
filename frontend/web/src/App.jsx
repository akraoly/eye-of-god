import { useState, useRef, useEffect } from 'react'
import Chat from './components/Chat'
import Sidebar from './components/Sidebar'
import './App.css'

export default function App() {
  const [sessionId] = useState(() => crypto.randomUUID())
  const [view, setView] = useState('chat')

  return (
    <div className="app">
      <Sidebar view={view} onNav={setView} />
      <main className="main">
        {view === 'chat' && <Chat sessionId={sessionId} />}
        {view === 'memory' && <MemoryView />}
      </main>
    </div>
  )
}

function MemoryView() {
  const [memories, setMemories] = useState([])
  const [deleting, setDeleting] = useState(null)

  const load = () =>
    fetch('/api/memory/get')
      .then(r => r.json())
      .then(setMemories)
      .catch(() => {})

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    setDeleting(id)
    await fetch(`/api/memory/${id}`, { method: 'DELETE' })
    await load()
    setDeleting(null)
  }

  return (
    <div className="memory-view">
      <h2>Mémoires <span className="mem-count">{memories.length}</span></h2>
      {memories.length === 0 ? (
        <p className="empty">Aucune mémoire enregistrée. Commence à parler !</p>
      ) : (
        <div className="memory-list">
          {memories.map(m => (
            <div key={m.id} className="memory-card">
              <span className="mem-type">{m.type}</span>
              <span className="mem-key">{m.key}</span>
              <span className="mem-value">{m.value}</span>
              <span className="mem-score">{(m.importance * 100).toFixed(0)}%</span>
              <button
                className="mem-delete"
                onClick={() => handleDelete(m.id)}
                disabled={deleting === m.id}
                title="Supprimer"
              >
                {deleting === m.id ? '…' : '✕'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
