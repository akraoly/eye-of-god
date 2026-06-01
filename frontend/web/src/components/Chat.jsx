import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import EyeOfGod from './EyeOfGod'
import WelcomeNodes from './WelcomeNodes'
import VoiceInput from './VoiceInput'
import { sendMessage } from '../utils/api'

const fmt = d => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

function PreBlock({ children }) {
  const [copied, setCopied] = useState(false)
  // Extraire le langage depuis la classe du <code> enfant
  const codeEl = children?.props
  const lang = /language-(\w+)/.exec(codeEl?.className || '')?.[1] || ''
  const code = String(codeEl?.children ?? '').replace(/\n$/, '')
  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <div style={{ margin: '0.7em 0' }}>
      <div className="code-block-header">
        <span className="code-lang">{lang || 'code'}</span>
        <button className="code-copy" onClick={copy}>{copied ? '✅ Copié' : '📋 Copier'}</button>
      </div>
      <pre style={{ margin: 0 }}>{children}</pre>
    </div>
  )
}

const MD_COMPONENTS = {
  pre: PreBlock,
  code: ({ inline, className, children }) =>
    inline ? <code className={className}>{children}</code> : <code className={className}>{children}</code>,
}

export default function Chat({ sessionId }) {
  const [messages,  setMessages]  = useState([])
  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [eyeState,  setEyeState]  = useState('idle')
  const bottomRef = useRef(null)
  const taRef     = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'
  }, [input])

  const send = useCallback(async (text) => {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg, ts: new Date() }])
    setLoading(true)
    setEyeState('thinking')
    try {
      const data = await sendMessage(msg, sessionId)
      setEyeState('responding')
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        ts: new Date(),
        tool: data.tool_executed,
        intent: data.intent,
        agents: data.agents_used,
      }])
      setTimeout(() => setEyeState('idle'), 1200)
    } catch {
      setEyeState('idle')
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Connexion backend perdue. Port 8001 ?',
        ts: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const onVoiceTranscript = (text) => {
    setInput(text)
    send(text)
  }

  // ── Écran accueil ──────────────────────────────────────────────────────
  if (messages.length === 0 && !loading) {
    return (
      <div className="chat">
        <div className="welcome-screen">
          {/* Constellation œil + nœuds orbitaux */}
          <WelcomeNodes eyeState={eyeState} onSend={send} />
          {/* Titre sous la constellation */}
          <div className="welcome-text">
            <div className="welcome-title">Bonjour, <span>Mr Vitch</span></div>
            <div className="welcome-sub">
              Je suis L'Œil de Dieu — expert OSEE, assistant de programmation autonome,
              compagnon numérique évolutif.
            </div>
          </div>
        </div>
        <InputBar
          input={input} setInput={setInput} loading={loading}
          onKey={onKey} taRef={taRef} onSend={send}
          eyeState={eyeState} onVoice={onVoiceTranscript}
          onVoiceState={setEyeState}
        />
      </div>
    )
  }

  // ── Vue conversation ───────────────────────────────────────────────────
  return (
    <div className="chat">
      {/* Œil en header compact */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '10px 20px 8px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--glass)',
        backdropFilter: 'blur(20px)',
        flexShrink: 0,
      }}>
        <EyeOfGod state={eyeState} size={52} />
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)' }}>L'Œil de Dieu</div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>
            {{ idle: 'En attente', listening: '👂 Écoute...', thinking: '⚡ Réflexion...', responding: '✨ Réponse...' }[eyeState]}
          </div>
        </div>
      </div>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg-group ${m.role}`}>
            <div className={`msg ${m.role}`}>
              {m.role === 'assistant' && <div className="avatar avatar-ai">👁️</div>}
              <div className="bubble-wrap">
                <div className="bubble-meta">
                  <span className="meta-name">{m.role === 'assistant' ? "L'Œil" : 'Mr Vitch'}</span>
                  {m.ts && <span className="meta-time">{fmt(m.ts)}</span>}
                  {m.tool && <span className="meta-tool">⚡ {m.agents?.join(', ') || 'outil'}</span>}
                </div>
                {m.role === 'assistant' ? (
                  <div className="bubble bubble-md">
                    <ReactMarkdown components={MD_COMPONENTS}>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="bubble">{m.content}</div>
                )}
              </div>
              {m.role === 'user' && <div className="avatar avatar-user">MV</div>}
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg-group assistant">
            <div className="msg assistant">
              <div className="avatar avatar-ai">👁️</div>
              <div className="bubble-wrap">
                <div className="typing-bubble"><span /><span /><span /></div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <InputBar
        input={input} setInput={setInput} loading={loading}
        onKey={onKey} taRef={taRef} onSend={send}
        eyeState={eyeState} onVoice={onVoiceTranscript}
        onVoiceState={setEyeState}
      />
    </div>
  )
}

function InputBar({ input, setInput, loading, onKey, taRef, onSend, onVoice, onVoiceState }) {
  return (
    <div className="input-area">
      <div className="input-box">
        <VoiceInput
          onTranscript={onVoice}
          onStateChange={onVoiceState}
          disabled={loading}
        />
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
        <button className="send-btn" onClick={() => onSend()} disabled={loading || !input.trim()} title="Envoyer">
          ➤
        </button>
      </div>
      <div className="input-hint">
        <span><kbd>Enter</kbd> envoyer</span>
        <span><kbd>Shift+Enter</kbd> nouvelle ligne</span>
        <span>🎙️ clic micro pour vocal</span>
      </div>
    </div>
  )
}
