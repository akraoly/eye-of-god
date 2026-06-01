import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendMessage } from '../utils/api'

const SUGGESTIONS = [
  { icon: '🔍', title: 'Explorer un projet', desc: 'explore /chemin/du/projet', prompt: 'explore /home/kali/eye-of-god' },
  { icon: '⚔️', title: 'ROP chain', desc: 'Aide exploit dev', prompt: 'Explique-moi comment construire une ROP chain x64 avec pwntools' },
  { icon: '🛡️', title: 'Checksec', desc: 'Analyser un binaire', prompt: 'checksec /usr/bin/python3' },
  { icon: '🔴', title: 'Scan réseau', desc: 'Nmap sur une cible', prompt: 'nmap -sV --open 127.0.0.1' },
]

function fmt(d) {
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function CodeBlock({ node, inline, className, children, ...props }) {
  const [copied, setCopied] = useState(false)
  const lang = /language-(\w+)/.exec(className || '')?.[1] || ''
  const code = String(children).replace(/\n$/, '')

  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  if (inline) {
    return <code className={className} {...props}>{children}</code>
  }

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-lang">{lang || 'code'}</span>
        <button className="code-copy" onClick={copy}>
          {copied ? '✅ Copié' : '📋 Copier'}
        </button>
      </div>
      <pre><code {...props}>{code}</code></pre>
    </div>
  )
}

const MD_COMPONENTS = { code: CodeBlock }

export default function Chat({ sessionId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const taRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Auto-resize textarea
  useEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [input])

  const send = useCallback(async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg, ts: new Date() }])
    setLoading(true)
    try {
      const data = await sendMessage(msg, sessionId)
      setMessages(prev => [...prev, { role: 'assistant', content: data.response, ts: new Date(), tool: data.tool_executed }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Erreur de connexion. Vérifie que le backend tourne sur le port 8001.',
        ts: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  // Écran d'accueil si aucun message
  if (messages.length === 0 && !loading) {
    return (
      <div className="chat">
        <div className="messages" style={{ justifyContent: 'center' }}>
          <div className="welcome-screen">
            <div className="welcome-eye">👁️</div>
            <div>
              <div className="welcome-title">Bonjour, <span>Mr Vitch</span></div>
              <div className="welcome-sub" style={{ marginTop: 8 }}>
                Je suis L'Œil de Dieu — expert OSEE, assistant de programmation autonome,
                et accès complet aux outils Kali.
              </div>
            </div>
            <div className="welcome-cards">
              {SUGGESTIONS.map(s => (
                <button key={s.title} className="welcome-card" onClick={() => send(s.prompt)}>
                  <div className="wc-icon">{s.icon}</div>
                  <div className="wc-title">{s.title}</div>
                  <div className="wc-desc">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
        <InputBar input={input} setInput={setInput} loading={loading} onKey={onKey} taRef={taRef} onSend={send} />
      </div>
    )
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg-group ${m.role}`}>
            <div className={`msg ${m.role}`}>
              {m.role === 'assistant' && (
                <div className="avatar avatar-ai">👁️</div>
              )}
              <div className="bubble-wrap">
                <div className="bubble-meta">
                  <span className="meta-name">{m.role === 'assistant' ? "L'Œil de Dieu" : 'Mr Vitch'}</span>
                  {m.ts && <span className="meta-time">{fmt(m.ts)}</span>}
                  {m.tool && <span style={{ fontSize: '0.67rem', color: '#34d399' }}>⚡ outil exécuté</span>}
                </div>
                {m.role === 'assistant' ? (
                  <div className="bubble bubble-md">
                    <ReactMarkdown components={MD_COMPONENTS}>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="bubble">{m.content}</div>
                )}
              </div>
              {m.role === 'user' && (
                <div className="avatar avatar-user">MV</div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg-group assistant">
            <div className="msg assistant">
              <div className="avatar avatar-ai">👁️</div>
              <div className="bubble-wrap">
                <div className="typing-bubble">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <InputBar input={input} setInput={setInput} loading={loading} onKey={onKey} taRef={taRef} onSend={send} />
    </div>
  )
}

function InputBar({ input, setInput, loading, onKey, taRef, onSend }) {
  return (
    <div className="input-area">
      <div className="input-box">
        <textarea
          ref={taRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Message, commande, ou question..."
          rows={1}
          disabled={loading}
          autoFocus
        />
        <button className="send-btn" onClick={() => onSend()} disabled={loading || !input.trim()} title="Envoyer (Enter)">
          ➤
        </button>
      </div>
      <div className="input-hint">
        <span><kbd>Enter</kbd> envoyer</span>
        <span><kbd>Shift+Enter</kbd> nouvelle ligne</span>
      </div>
    </div>
  )
}
