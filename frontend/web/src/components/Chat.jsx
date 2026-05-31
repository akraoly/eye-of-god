import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../utils/api'

const WELCOME = "Bonjour. Je suis L'Œil de Dieu, ton compagnon numérique personnel.\nParle-moi de toi, pose une question, ou donne-moi un ordre."

export default function Chat({ sessionId }) {
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const data = await sendMessage(text, sessionId)
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Erreur de connexion au backend. Vérifie que le serveur tourne sur le port 8001.',
      }])
    } finally {
      setLoading(false)
    }
  }

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="msg assistant">
            <div className="bubble typing"><span /><span /><span /></div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-bar">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Parle-moi de toi, pose une question, donne un ordre..."
          rows={2}
          disabled={loading}
          autoFocus
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          Envoyer
        </button>
      </div>
    </div>
  )
}
