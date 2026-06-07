/**
 * VoiceOrb — Orbe animée d'interface vocale.
 * États : idle · listening · processing · speaking
 * Utilise le pipeline faster-whisper local (aucun audio ne quitte la machine).
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { auth, apiFetch } from '../utils/auth'

const ORB_STATES = {
  idle:       { color: '#a78bfa', shadow: '#a78bfa40', scale: 1,    pulseSpeed: '4s',  label: 'En veille' },
  listening:  { color: '#38bdf8', shadow: '#38bdf880', scale: 1.15, pulseSpeed: '0.8s', label: 'Écoute…' },
  processing: { color: '#fbbf24', shadow: '#fbbf2480', scale: 1.05, pulseSpeed: '0.3s', label: 'Traitement…' },
  speaking:   { color: '#4ade80', shadow: '#4ade8060', scale: 1.1,  pulseSpeed: '1.2s', label: 'Réponse…' },
  error:      { color: '#ef4444', shadow: '#ef444440', scale: 1,    pulseSpeed: '2s',   label: 'Erreur' },
}

const SAMPLE_RATE = 16000
const CHUNK_MS    = 100   // envoi WebSocket toutes les 100ms
const CHUNK_SIZE  = Math.floor(SAMPLE_RATE * CHUNK_MS / 1000)  // 1600 samples

function useVoicePipeline({ onTranscript, onCommand, onError }) {
  const [state, setState] = useState('idle')
  const wsRef        = useRef(null)
  const processorRef = useRef(null)
  const audioCtxRef  = useRef(null)
  const streamRef    = useRef(null)
  const [transcript, setTranscript] = useState('')
  const [muted, setMuted] = useState(false)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const token = auth.getToken()
    if (!token) return
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/voice/ws/stream?token=${encodeURIComponent(token)}&language=fr&model=small`)
    wsRef.current = ws

    ws.onopen    = () => console.log('[VoiceOrb] WS connecté')
    ws.onclose   = () => { }
    ws.onerror   = () => onError?.('Connexion WebSocket vocale échouée')
    ws.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'final' && data.text) {
          setTranscript(data.text)
          setState('processing')
          onTranscript?.(data.text, data.intent)
          if (data.intent?.intent === 'voice_command' && data.voice_response) {
            onCommand?.(data.intent.command, data.voice_response)
            if (!muted && data.voice_response.text) {
              speakText(data.voice_response.text)
            }
          }
        } else if (data.type === 'silence') {
          setState(prev => prev === 'listening' ? 'idle' : prev)
        }
      } catch {}
    }
  }, [muted, onTranscript, onCommand, onError])

  const startListening = useCallback(async () => {
    if (state === 'listening') return
    try {
      connect()
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      streamRef.current = stream

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE })
      audioCtxRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)

      // ScriptProcessor pour capturer le PCM
      const processor = audioCtx.createScriptProcessor(CHUNK_SIZE, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = evt => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return
        const float32 = evt.inputBuffer.getChannelData(0)
        const int16 = new Int16Array(float32.length)
        for (let i = 0; i < float32.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768))
        }
        wsRef.current.send(int16.buffer)
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)
      setState('listening')
    } catch (e) {
      onError?.('Accès micro refusé : ' + e.message)
      setState('error')
    }
  }, [state, connect, onError])

  const stopListening = useCallback(() => {
    // Forcer la transcription du buffer restant
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ cmd: 'transcribe' }))
    }
    processorRef.current?.disconnect()
    audioCtxRef.current?.close()
    streamRef.current?.getTracks().forEach(t => t.stop())
    processorRef.current = null
    audioCtxRef.current = null
    streamRef.current = null
    setState('idle')
  }, [])

  const speakText = useCallback(async (text) => {
    if (muted || !text) return
    try {
      const res = await apiFetch('/voice/local/tts', {
        method: 'POST',
        body: JSON.stringify({ text, voice: 'fr_FR-upmc-medium' }),
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const audio = new Audio(url)
      setState('speaking')
      audio.onended = () => { setState('idle'); URL.revokeObjectURL(url) }
      audio.play()
    } catch (e) {
      console.warn('[VoiceOrb] TTS erreur:', e)
    }
  }, [muted])

  const toggleMute = useCallback(() => setMuted(m => !m), [])

  useEffect(() => {
    return () => {
      wsRef.current?.close()
      processorRef.current?.disconnect()
      audioCtxRef.current?.close()
      streamRef.current?.getTracks().forEach(t => t.stop())
    }
  }, [])

  return { state, setState, transcript, startListening, stopListening, speakText, muted, toggleMute }
}


export default function VoiceOrb({ onTranscript, onCommand, compact = false }) {
  const [error, setError] = useState(null)
  const { state, transcript, startListening, stopListening, speakText, muted, toggleMute } =
    useVoicePipeline({
      onTranscript,
      onCommand,
      onError: msg => setError(msg),
    })

  const orbState = ORB_STATES[state] || ORB_STATES.idle
  const isListening = state === 'listening'

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
      userSelect: 'none',
    }}>
      {/* Orbe principale */}
      <div style={{ position: 'relative', width: compact ? 48 : 72, height: compact ? 48 : 72 }}>
        {/* Aura pulsante */}
        <div style={{
          position: 'absolute', inset: -8,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${orbState.shadow} 0%, transparent 70%)`,
          animation: `orb-pulse ${orbState.pulseSpeed} ease-in-out infinite`,
        }} />
        {/* Corps de l'orbe */}
        <button
          onClick={isListening ? stopListening : startListening}
          style={{
            width: '100%', height: '100%',
            borderRadius: '50%',
            background: `radial-gradient(circle at 35% 35%, ${orbState.color}dd, ${orbState.color}88)`,
            border: `2px solid ${orbState.color}`,
            boxShadow: `0 0 ${compact ? 16 : 24}px ${orbState.shadow}, inset 0 1px 0 rgba(255,255,255,0.2)`,
            cursor: 'pointer',
            transform: `scale(${orbState.scale})`,
            transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: compact ? '1.2rem' : '1.8rem',
          }}
          title={isListening ? 'Arrêter l\'écoute' : 'Démarrer l\'écoute vocale'}
        >
          {state === 'listening'  ? '🎙️' :
           state === 'processing' ? '⟳' :
           state === 'speaking'   ? '🔊' :
           state === 'error'      ? '⚠' : '🎤'}
        </button>

        {/* Indicateur de niveau audio (listening only) */}
        {isListening && (
          <div style={{
            position: 'absolute', bottom: -4, left: '50%', transform: 'translateX(-50%)',
            display: 'flex', gap: 2, alignItems: 'flex-end',
          }}>
            {[...Array(5)].map((_, i) => (
              <div key={i} style={{
                width: 3, background: '#38bdf8',
                borderRadius: 1,
                height: `${4 + Math.sin((Date.now() / 150) + i) * 4}px`,
                animation: `voice-bar ${0.3 + i * 0.1}s ease-in-out infinite alternate`,
                opacity: 0.8,
              }} />
            ))}
          </div>
        )}
      </div>

      {/* Label état */}
      {!compact && (
        <span style={{ fontSize: '0.65rem', color: orbState.color, fontWeight: 600, letterSpacing: 1 }}>
          {orbState.label.toUpperCase()}
        </span>
      )}

      {/* Transcription temps réel */}
      {!compact && transcript && state !== 'idle' && (
        <div style={{
          maxWidth: 280, padding: '6px 10px', background: '#38bdf810',
          border: '1px solid #38bdf830', borderRadius: 6,
          fontSize: '0.68rem', color: 'var(--text1)', textAlign: 'center',
          fontStyle: 'italic',
        }}>
          "{transcript}"
        </div>
      )}

      {/* Erreur */}
      {error && (
        <div style={{ fontSize: '0.62rem', color: '#ef4444', maxWidth: 200, textAlign: 'center' }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 6, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* Contrôles */}
      {!compact && (
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={toggleMute}
            style={{ padding: '3px 10px', fontSize: '0.62rem', background: muted ? '#ef444420' : 'var(--bg2)',
              color: muted ? '#ef4444' : 'var(--text3)', border: `1px solid ${muted ? '#ef444440' : 'var(--border)'}`,
              borderRadius: 4, cursor: 'pointer' }}>
            {muted ? '🔇 Muet' : '🔈 Son'}
          </button>
        </div>
      )}

      <style>{`
        @keyframes orb-pulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.15); opacity: 1; }
        }
        @keyframes voice-bar {
          from { transform: scaleY(0.5); }
          to   { transform: scaleY(1.5); }
        }
      `}</style>
    </div>
  )
}
