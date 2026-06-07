import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import EyeOfGod from './EyeOfGod'
import WelcomeNodes from './WelcomeNodes'
import VoiceInput from './VoiceInput'
import MatrixRain from './MatrixRain'
import { sendMessage, loadHistory, resetSession } from '../utils/api'
import { apiFetch } from '../utils/auth'

// ── Nettoyage texte avant TTS ─────────────────────────────────────────────────
function cleanForTTS(raw) {
  return raw
    // Blocs de code → annoncés verbalement
    .replace(/```[\s\S]*?```/g, ', exemple de code, ')
    .replace(/`[^`]+`/g, '')
    // Titres → lus comme du texte normal avec pause après
    .replace(/#{1,6}\s*(.+)/g, '$1. ')
    // Gras / italique / barré → garder le contenu
    .replace(/\*{1,3}([^*\n]+)\*{1,3}/g, '$1')
    .replace(/_{1,2}([^_\n]+)_{1,2}/g, '$1')
    .replace(/~~([^~\n]+)~~/g, '$1')
    // Listes à puces → chaque item ponctué pour une pause naturelle
    .replace(/^[-*+]\s+(.+)/gm, '$1. ')
    .replace(/^\d+\.\s+(.+)/gm, '$1. ')
    // Liens et images
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    // Tableaux
    .replace(/\|/g, ', ')
    .replace(/[-]{3,}/g, '')
    // Emojis et symboles graphiques
    .replace(/[✅❌⚠️🔴🟠🟡🟢🔵⭕✓✗→←↑↓►◄•·🎯🔥💡⚡🛡️🔒🔓]/g, '')
    .replace(/[*#_~`^<>{}[\]\\]/g, '')
    // Ponctuation répétée
    .replace(/([.!?])\1+/g, '$1')
    .replace(/\.{2,}/g, '.')
    .replace(/,{2,}/g, ',')
    // Deux points isolés en fin de segment → virgule (pause douce)
    .replace(/\s*:\s*\n/g, ', ')
    // Espaces et lignes
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ', ')
    .replace(/[ \t]{2,}/g, ' ')
    // Nettoyage final
    .replace(/[,\s]+\./g, '.')
    .replace(/\.\s*,/g, '.')
    .replace(/\.{2,}/g, '.')
    .replace(/\s+,/g, ',')
    .replace(/—/g, ', ')
    .trim()
    .slice(0, 3000)
}

// ── TTS voix homme ───────────────────────────────────────────────────────────
function ttsSpeak(text, onEnd) {
  if (!window.speechSynthesis || !text) return
  window.speechSynthesis.cancel()
  const utt = new SpeechSynthesisUtterance(cleanForTTS(text))
  utt.lang   = 'fr-FR'
  utt.pitch  = 0
  utt.rate   = 1.15
  utt.volume = 1.0
  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices()
    // Priorité : voix masculine explicite, puis Thomas/Pierre (Apple), puis fr générique
    return voices.find(v => v.lang.startsWith('fr') && /thomas/i.test(v.name))
      || voices.find(v => v.lang.startsWith('fr') && /pierre|henri|nicolas|male|man|homm/i.test(v.name))
      || voices.find(v => /fr/i.test(v.lang) && /standard-b|neural2-b|wavenet-b/i.test(v.name))
      || voices.find(v => v.lang.startsWith('fr') && !/amelie|céline|celine|florence|juliette|marie|female|femme|fille/i.test(v.name))
      || voices.find(v => v.lang === 'fr-FR')
      || voices.find(v => v.lang.startsWith('fr'))
  }
  const v = pickVoice()
  if (v) utt.voice = v
  if (onEnd) utt.onend = onEnd
  window.speechSynthesis.speak(utt)
}
function ttsStop() { window.speechSynthesis?.cancel() }

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

// ── Modal mot de passe SHANURA ────────────────────────────────────────────
const SHANURA_PWD = import.meta.env.VITE_SHANURA_PASSWORD || 'DIEU2026'
const SHANURA_SESSION_KEY = 'shanura_unlocked'

function ShanuraPasswordModal({ onSuccess, onCancel }) {
  const [pwd, setPwd]       = useState('')
  const [error, setError]   = useState(false)
  const [shake, setShake]   = useState(false)
  const inputRef            = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const verify = () => {
    if (pwd === SHANURA_PWD) {
      sessionStorage.setItem(SHANURA_SESSION_KEY, '1')
      onSuccess()
    } else {
      setError(true)
      setShake(true)
      setPwd('')
      setTimeout(() => setShake(false), 600)
    }
  }

  const onKey = e => {
    if (e.key === 'Enter') verify()
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div className="shanura-modal-backdrop" onClick={e => { if (e.target === e.currentTarget) onCancel() }}>
      <div className={`shanura-modal${shake ? ' shanura-modal-shake' : ''}`}>
        <div className="shanura-modal-eye">⚡</div>
        <div className="shanura-modal-title">MODE DIVIN</div>
        <div className="shanura-modal-sub">Authentification requise pour activer l'omnipotence</div>
        <div className="shanura-modal-divider" />
        <input
          ref={inputRef}
          type="password"
          className={`shanura-modal-input${error ? ' shanura-input-error' : ''}`}
          placeholder="Mot de passe divin…"
          value={pwd}
          onChange={e => { setPwd(e.target.value); setError(false) }}
          onKeyDown={onKey}
        />
        {error && <div className="shanura-modal-err">⛔ Accès refusé — Mot de passe incorrect</div>}
        <div className="shanura-modal-actions">
          <button className="shanura-modal-cancel" onClick={onCancel}>Annuler</button>
          <button className="shanura-modal-confirm" onClick={verify}>⚡ Activer</button>
        </div>
      </div>
    </div>
  )
}

// ── Overlay Mode Divin SHANURA ────────────────────────────────────────────
function ShanuraOverlay() {
  return (
    <div className="shanura-overlay">
      <div className="shanura-particles">
        {Array.from({ length: 30 }).map((_, i) => (
          <div key={i} className="shanura-particle" style={{
            left: `${Math.random() * 100}%`,
            animationDelay: `${Math.random() * 3}s`,
            animationDuration: `${2 + Math.random() * 3}s`,
            width: `${2 + Math.random() * 4}px`,
            height: `${2 + Math.random() * 4}px`,
          }} />
        ))}
      </div>
      <div className="shanura-banner">
        <span className="shanura-bolt">⚡</span>
        <span className="shanura-title">MODE DIVIN ACTIVÉ</span>
        <span className="shanura-sub">OMNIPOTENCE TOTALE — TOUS LES AGENTS EN ACTION</span>
        <span className="shanura-bolt">⚡</span>
      </div>
    </div>
  )
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

// ── Bulle assistant avec bouton copier + lecture vocale ──────────────────
function AssistantBubble({ msg, isLast }) {
  const [copied,   setCopied]   = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const copyMsg = () => navigator.clipboard.writeText(msg.content)
    .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
  const handleSpeak = () => {
    if (speaking) { ttsStop(); setSpeaking(false); return }
    setSpeaking(true)
    ttsSpeak(msg.content, () => setSpeaking(false))
  }

  return (
    <div className={`bubble bubble-md bubble-assistant${msg.shanura ? ' bubble-shanura-response' : ''}`}>
      {/* Badge SHANURA mode */}
      {msg.shanura && (
        <div className="shanura-response-badge">
          ⚡ MODE SHANURA — {msg.agents?.length || 0} agents activés
        </div>
      )}
      {/* Badge outil si agent utilisé */}
      {msg.tool && !msg.shanura && (
        <div className="msg-agent-badge">
          <span className="agent-dot" />
          {msg.agents?.join(' · ') || 'outil exécuté'}
        </div>
      )}
      <ReactMarkdown components={MD}>{msg.content}</ReactMarkdown>
      {msg.streaming && <span className="stream-cursor" />}
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end', marginTop: 4 }}>
        <button className="msg-copy-btn" onClick={handleSpeak} title={speaking ? 'Stopper' : 'Lire en voix homme'} style={{ opacity: speaking ? 1 : 0.7 }}>
          {speaking ? '⏹' : '🔊'}
        </button>
        <button className="msg-copy-btn" onClick={copyMsg} title="Copier">
          {copied ? '✅' : '⎘'}
        </button>
      </div>
    </div>
  )
}

export default function Chat({ sessionId, onNewChat }) {
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState('')
  const [loading,       setLoading]       = useState(false)
  const [eyeState,      setEyeState]      = useState('idle')
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [cyberMode,      setCyberMode]      = useState(false)
  const [shanuraMode,    setShanuraMode]    = useState(false)
  const [shanuraModal,   setShanuraModal]   = useState(false)
  const [pendingShanura, setPendingShanura] = useState('')
  const [autoSpeak,      setAutoSpeak]      = useState(true)
  const [speaking,       setSpeaking]       = useState(false)
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

  const send = useCallback(async (text, isVocal = false, voiceEnergy = 'normal', voiceDuration = 0) => {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    const isShanura = msg.toUpperCase().includes('SHANURA:)')

    if (isShanura && !sessionStorage.getItem(SHANURA_SESSION_KEY)) {
      setPendingShanura(msg)
      setInput('')
      setShanuraModal(true)
      return
    }

    if (!isShanura) setShanuraMode(false)
    else setShanuraMode(true)
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg, ts: new Date(), shanura: isShanura }])
    setLoading(true)
    setEyeState(isShanura ? 'responding' : 'thinking')

    // ID unique pour la bulle streaming — permet de la retrouver dans le tableau
    const streamId = `stream-${Date.now()}`

    try {
      const res = await apiFetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({
          message: msg,
          session_id: sessionId,
          vocal_input: isVocal,
          voice_energy: voiceEnergy,
          voice_duration: voiceDuration,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulated = ''
      let bubbleAdded = false
      let finalMeta = {}

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // fragment incomplet en attente

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const parsed = JSON.parse(raw)
            if (parsed.error) throw new Error(parsed.error)

            if (parsed.chunk !== undefined) {
              accumulated += parsed.chunk
              if (!bubbleAdded) {
                // Premier chunk : insérer la bulle assistant dans le tableau
                setMessages(prev => [...prev, {
                  id: streamId, role: 'assistant', content: accumulated,
                  ts: new Date(), streaming: true, tool: false, agents: [], shanura: isShanura,
                }])
                bubbleAdded = true
                setEyeState('responding')
              } else {
                // Chunks suivants : mise à jour en place par ID
                setMessages(prev => prev.map(m =>
                  m.id === streamId ? { ...m, content: accumulated } : m
                ))
              }
            }
            if (parsed.done) finalMeta = parsed
          } catch (e) {
            console.warn('[stream] SSE parse:', e.message)
          }
        }
      }

      // Finaliser la bulle : enlever le flag streaming, injecter les métadonnées
      setMessages(prev => prev.map(m =>
        m.id === streamId ? {
          ...m, content: accumulated, streaming: false,
          tool: finalMeta.tool_executed || false,
          agents: finalMeta.agents_used || [],
          shanura: finalMeta.shanura_mode || isShanura,
        } : m
      ))

      if (finalMeta.shanura_mode) setShanuraMode(true)
      else if (!isShanura) setShanuraMode(false)

      setTimeout(() => setEyeState('idle'), 1200)

      // TTS lecture automatique voix homme après stream complet
      if (accumulated && autoSpeak) {
        setSpeaking(true)
        ttsSpeak(accumulated, () => setSpeaking(false))
      }

    } catch (err) {
      setEyeState('idle')
      setShanuraMode(false)
      setMessages(prev => {
        const hasStream = prev.some(m => m.id === streamId)
        if (hasStream) {
          return prev.map(m => m.id === streamId
            ? { ...m, content: '⚠️ Connexion perdue.', streaming: false }
            : m)
        }
        return [...prev, { role: 'assistant', content: '⚠️ Connexion backend perdue.', ts: new Date() }]
      })
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId, autoSpeak])

  const onKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }
  const onVoiceTranscript = (text, voiceMeta = {}) => {
    setInput(text)
    send(text, true, voiceMeta.energy || 'normal', voiceMeta.duration || 0)
  }
  const stopSpeak = () => { ttsStop(); setSpeaking(false) }

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
        {shanuraModal && (
          <ShanuraPasswordModal
            onSuccess={() => { setShanuraModal(false); send(pendingShanura) }}
            onCancel={() => { setShanuraModal(false); setPendingShanura('') }}
          />
        )}
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
          onVoice={onVoiceTranscript} onVoiceState={setEyeState}
          autoSpeak={autoSpeak} onToggleAutoSpeak={() => { setAutoSpeak(v => !v); stopSpeak() }}
          speaking={speaking} onStopSpeak={stopSpeak} />
      </div>
    )
  }

  // ── Vue conversation ──────────────────────────────────────────────────
  return (
    <div className={`chat ${cyberMode ? 'cyber-mode' : ''} ${shanuraMode ? 'shanura-mode' : ''}`}>
      {shanuraModal && (
        <ShanuraPasswordModal
          onSuccess={() => { setShanuraModal(false); send(pendingShanura) }}
          onCancel={() => { setShanuraModal(false); setPendingShanura('') }}
        />
      )}
      <MatrixRain active={cyberMode} />
      {shanuraMode && <ShanuraOverlay />}
      <ChatHeader eyeState={eyeState} msgCount={messages.length} onNew={onNewChat}
        cyberMode={cyberMode} onCyberToggle={() => setCyberMode(v => !v)} />

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
                      <div className={`bubble bubble-user${m.shanura ? ' bubble-shanura' : ''}`}>
                        {m.shanura && <span className="shanura-badge">⚡ SHANURA</span>}
                        {m.content}
                      </div>
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

        {loading && !messages.some(m => m.streaming) && (
          <div className="msg-group assistant group-last">
            <div className="msg assistant">
              <div className="avatar avatar-ai">👁️</div>
              <div className="bubble-wrap">
                <div className={`typing-bubble${shanuraMode ? ' typing-shanura' : ''}`}>
                  <span /><span /><span />
                  <span className="typing-label">
                    {shanuraMode ? '⚡ TOUS LES AGENTS EN ACTION…' : 'réflexion…'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <InputBar input={input} setInput={setInput} loading={loading}
        onKey={onKey} taRef={taRef} onSend={send}
        onVoice={onVoiceTranscript} onVoiceState={setEyeState}
        autoSpeak={autoSpeak} onToggleAutoSpeak={() => { setAutoSpeak(v => !v); stopSpeak() }}
        speaking={speaking} onStopSpeak={stopSpeak} />
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

function ChatHeader({ eyeState, msgCount, onNew, cyberMode, onCyberToggle }) {
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
      <button
        className={`cyber-toggle ${cyberMode ? 'active' : ''}`}
        onClick={onCyberToggle}
        title="Mode cyber / matrix"
      >
        <span className="toggle-dot" />
        {cyberMode ? 'CYBER ON' : 'CYBER'}
      </button>
      <button className="new-chat-btn" onClick={onNew} title="Nouvelle conversation">
        <span>+</span> Nouveau
      </button>
    </header>
  )
}

// ── Input bar ─────────────────────────────────────────────────────────────
function InputBar({ input, setInput, loading, onKey, taRef, onSend, onVoice, onVoiceState,
                    autoSpeak, onToggleAutoSpeak, speaking, onStopSpeak }) {
  const charCount = input.length
  return (
    <div className="input-area">
      {/* Barre contrôle voix */}
      <div className="voice-toolbar">
        <button
          className={`voice-auto-toggle ${autoSpeak ? 'voice-auto-on' : ''}`}
          onClick={onToggleAutoSpeak}
          title={autoSpeak ? 'Réponse vocale activée — cliquer pour désactiver' : 'Réponse vocale désactivée'}
        >
          {autoSpeak ? '🔊 Auto ON' : '🔇 Auto OFF'}
        </button>
        {speaking && (
          <button className="voice-stop-btn" onClick={onStopSpeak} title="Stopper la voix">
            ⏹ Stopper la voix
          </button>
        )}
      </div>

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
