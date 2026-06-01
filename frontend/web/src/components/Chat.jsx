import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import EyeOfGod from './EyeOfGod'
import WelcomeNodes from './WelcomeNodes'
import VoiceInput from './VoiceInput'
import { sendMessage, loadHistory, resetSession } from '../utils/api'

const fmtTime = d => d instanceof Date
  ? d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  : ''

const fmtDate = d => d instanceof Date
  ? d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })
  : ''

const isSameDay = (a, b) =>
  a instanceof Date && b instanceof Date &&
  a.toDateString() === b.toDateString()

// ── CodeBlock avec copie ──────────────────────────────────────────────────
function PreBlock({ children }) {
  const [copied, setCopied] = useState(false)
  const codeEl = children?.props
  const lang = /language-(\w+)/.exec(codeEl?.className || '')?.[1] || ''
  const code = String(codeEl?.children ?? '').replace(/\n$/, '')
  const copy = () => navigator.clipboard.writeText(code)
    .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
  return (
    <div style={{ margin: '0.75em 0' }}>
      <div className="code-block-header">
        <span className="code-lang">{lang || 'code'}</span>
        <button className="code-copy" onClick={copy}>{copied ? '✅ Copié' : '📋 Copier'}</button>
      </div>
      <pre style={{ margin: 0 }}>{children}</pre>
    </div>
  )
}
const MD = {
  pre: PreBlock,
  code: ({ inline, className, children }) =>
    <code className={className}>{children}</code>,
}

// ── Séparateur de date ────────────────────────────────────────────────────
function DateSep({ date }) {
  return (
    <div className="date-sep">
      <span className="date-sep-line" />
      <span className="date-sep-label">{fmtDate(date)}</span>
      <span className="date-sep-line" />
    </div>
  )
}

// ── Bulle assistant avec bouton copier ────────────────────────────────────
function AssistantBubble({ msg, isLast }) {
  const [copied, setCopied] = useState(false)
  const copyMsg = () => navigator.clipboard.writeText(msg.content)
    .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })

  return (
    <div className="bubble bubble-md bubble-assistant">
      {/* Badge outil si agent utilisé */}
      {msg.tool && (
        <div className="msg-agent-badge">
          <span className="agent-dot" />
          {msg.agents?.join(' · ') || 'outil exécuté'}
        </div>
      )}
      <ReactMarkdown components={MD}>{msg.content}</ReactMarkdown>
      <button className="msg-copy-btn" onClick={copyMsg} title="Copier">
        {copied ? '✅' : '⎘'}
      </button>
    </div>
  )
}

export default function Chat({ sessionId }) {
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState('')
  const [loading,       setLoading]       = useState(false)
  const [eyeState,      setEyeState]      = useState('idle')
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const bottomRef = useRef(null)
  const taRef     = useRef(null)

  // Chargement historique au montage
  useEffect(() => {
    if (!sessionId) return
    loadHistory(sessionId, 40).then(msgs => {
      if (msgs.length > 0) {
        setMessages(msgs.map(m => ({ ...m, ts: m.ts ? new Date(m.ts) : new Date(), fromHistory: true })))
      }
      setHistoryLoaded(true)
    }).catch(() => setHistoryLoaded(true))
  }, [sessionId])

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
        role: 'assistant', content: data.response, ts: new Date(),
        tool: data.tool_executed, intent: data.intent, agents: data.agents_used,
      }])
      setTimeout(() => setEyeState('idle'), 1200)
    } catch {
      setEyeState('idle')
      setMessages(prev => [...prev, {
        role: 'assistant', content: '⚠️ Connexion backend perdue. Port 8001 ?', ts: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const onKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }
  const onVoiceTranscript = text => { setInput(text); send(text) }
  const handleNewChat = () => { resetSession(); window.location.reload() }

  // ── Spinner ───────────────────────────────────────────────────────────
  if (!historyLoaded) {
    return (
      <div className="chat chat-loading">
        <EyeOfGod state="thinking" size={72} />
        <div className="chat-loading-label">CHARGEMENT DE LA MÉMOIRE…</div>
      </div>
    )
  }

  // ── Écran accueil ─────────────────────────────────────────────────────
  if (messages.length === 0 && !loading) {
    return (
      <div className="chat">
        <div className="welcome-screen">
          <WelcomeNodes eyeState={eyeState} onSend={send} />
          <div className="welcome-text">
            <div className="welcome-title">Bonjour, <span>Mr Vitch</span></div>
            <div className="welcome-sub">
              Je suis L'Œil de Dieu — expert OSEE, assistant de programmation autonome,
              compagnon numérique évolutif.
            </div>
          </div>
        </div>
        <InputBar input={input} setInput={setInput} loading={loading}
          onKey={onKey} taRef={taRef} onSend={send}
          onVoice={onVoiceTranscript} onVoiceState={setEyeState} />
      </div>
    )
  }

  // ── Vue conversation ──────────────────────────────────────────────────
  return (
    <div className="chat">
      <ChatHeader eyeState={eyeState} msgCount={messages.length} onNew={handleNewChat} />

      <div className="messages">
        {messages.map((m, i) => {
          const prev = messages[i - 1]
          // Séparateur de date
          const showDate = !prev || (m.ts && prev.ts && !isSameDay(m.ts, prev.ts))
          // Groupement : premier message d'un groupe si rôle change ou date change
          const isFirstInGroup = !prev || prev.role !== m.role || showDate
          // Dernier message d'un groupe
          const next = messages[i + 1]
          const isLastInGroup = !next || next.role !== m.role

          return (
            <div key={i}>
              {showDate && m.ts && <DateSep date={m.ts} />}
              <div className={`msg-group ${m.role} ${isFirstInGroup ? 'group-first' : ''} ${isLastInGroup ? 'group-last' : ''}`}>
                <div className={`msg ${m.role}`}>
                  {/* Avatar IA — seulement sur le dernier du groupe */}
                  {m.role === 'assistant' && (
                    <div className={`avatar avatar-ai ${!isLastInGroup ? 'avatar-hidden' : ''}`}>
                      {isLastInGroup ? '👁️' : ''}
                    </div>
                  )}

                  <div className="bubble-wrap">
                    {/* Méta : affiché sur hover, uniquement sur premier du groupe */}
                    {isFirstInGroup && (
                      <div className="bubble-meta">
                        <span className="meta-name">{m.role === 'assistant' ? "L'Œil de Dieu" : 'Mr Vitch'}</span>
                        {m.ts && <span className="meta-time">{fmtTime(m.ts)}</span>}
                        {m.fromHistory && <span className="meta-history">↩ historique</span>}
                      </div>
                    )}

                    {m.role === 'assistant' ? (
                      <AssistantBubble msg={m} isLast={isLastInGroup} />
                    ) : (
                      <div className="bubble bubble-user">{m.content}</div>
                    )}
                  </div>

                  {/* Avatar user — seulement sur le dernier du groupe */}
                  {m.role === 'user' && (
                    <div className={`avatar avatar-user ${!isLastInGroup ? 'avatar-hidden' : ''}`}>
                      {isLastInGroup ? 'MV' : ''}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {loading && (
          <div className="msg-group assistant group-last">
            <div className="msg assistant">
              <div className="avatar avatar-ai">👁️</div>
              <div className="bubble-wrap">
                <div className="typing-bubble">
                  <span /><span /><span />
                  <span className="typing-label">réflexion…</span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <InputBar input={input} setInput={setInput} loading={loading}
        onKey={onKey} taRef={taRef} onSend={send}
        onVoice={onVoiceTranscript} onVoiceState={setEyeState} />
    </div>
  )
}

// ── Header ────────────────────────────────────────────────────────────────
const STATE_COLORS = {
  idle:       '#50507a',
  listening:  '#38bdf8',
  thinking:   '#fde68a',
  responding: '#a78bfa',
}
const STATE_LABELS = {
  idle: 'En attente', listening: 'Écoute…', thinking: 'Réflexion…', responding: 'Réponse…',
}

function ChatHeader({ eyeState, msgCount, onNew }) {
  return (
    <header className="chat-header">
      <EyeOfGod state={eyeState} size={48} />
      <div className="chat-header-info">
        <div className="chat-header-name">L'Œil de Dieu</div>
        <div className="chat-header-state">
          <span className="state-dot" style={{ background: STATE_COLORS[eyeState] }} />
          {STATE_LABELS[eyeState]}
          {msgCount > 0 && <span className="msg-count">{msgCount} messages</span>}
        </div>
      </div>
      <button className="new-chat-btn" onClick={onNew} title="Nouvelle conversation">
        <span>+</span> Nouveau
      </button>
    </header>
  )
}

// ── Input bar ─────────────────────────────────────────────────────────────
function InputBar({ input, setInput, loading, onKey, taRef, onSend, onVoice, onVoiceState }) {
  const charCount = input.length
  return (
    <div className="input-area">
      <div className="input-box">
        <VoiceInput onTranscript={onVoice} onStateChange={onVoiceState} disabled={loading} />
        <textarea
          ref={taRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Message, commande, ou question…"
          rows={1}
          disabled={loading}
          autoFocus
        />
        {charCount > 200 && (
          <span style={{ fontSize: '0.62rem', color: charCount > 2000 ? 'var(--red)' : 'var(--text3)', alignSelf: 'flex-end', paddingBottom: 10, flexShrink: 0 }}>
            {charCount}
          </span>
        )}
        <button className="send-btn" onClick={() => onSend()} disabled={loading || !input.trim()} title="Envoyer">
          ➤
        </button>
      </div>
      <div className="input-hint">
        <span><kbd>Enter</kbd> envoyer</span>
        <span><kbd>Shift+Enter</kbd> saut de ligne</span>
        <span>🎙️ vocal</span>
      </div>
    </div>
  )
}
