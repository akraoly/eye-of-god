import { useState, useRef, useEffect } from 'react'
import { auth } from '../utils/auth'

const BASE = import.meta.env.VITE_API_URL || '/api'

async function transcribeViaBackend(blob, mimeType) {
  const token = auth.getToken()
  const ext   = mimeType.includes('ogg') ? 'ogg' : 'webm'
  const form  = new FormData()
  form.append('file', blob, `audio.${ext}`)
  form.append('language', 'fr-FR')
  const res = await fetch(`${BASE}/voice/transcribe`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`STT ${res.status} — ${detail.slice(0, 120)}`)
  }
  const data = await res.json()
  if (data.error && !data.text) throw new Error(data.error)
  // Retourner texte + métadonnées vocales
  return { text: data.text || '', voice_energy: data.voice_energy || 'normal', voice_duration: data.voice_duration || 0 }
}

export default function VoiceInput({ onTranscript, onStateChange, disabled }) {
  const [active,   setActive]   = useState(false)
  const [status,   setStatus]   = useState('')   // label affiché sous le bouton
  const [error,    setError]    = useState('')
  const mrRef      = useRef(null)
  const chunksRef  = useRef([])
  const canvasRef  = useRef(null)
  const rafRef     = useRef(null)
  const streamRef  = useRef(null)
  const mimeRef    = useRef('audio/webm')

  // ── Visualiseur onde ──────────────────────────────────────────────────
  const startVisualizer = (stream) => {
    try {
      const ctx      = new (window.AudioContext || window.webkitAudioContext)()
      const src      = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      src.connect(analyser)
      const canvas = canvasRef.current
      if (!canvas) return
      const c    = canvas.getContext('2d')
      const data = new Uint8Array(analyser.frequencyBinCount)
      const draw = () => {
        rafRef.current = requestAnimationFrame(draw)
        analyser.getByteFrequencyData(data)
        c.clearRect(0, 0, canvas.width, canvas.height)
        const W = canvas.width, H = canvas.height
        const bars = 40, bw = W / bars
        for (let i = 0; i < bars; i++) {
          const v = data[Math.floor((i / bars) * data.length)] / 255
          const h = v * H * 0.85
          const x = i * bw + bw / 2
          const g = c.createLinearGradient(0, H / 2 - h / 2, 0, H / 2 + h / 2)
          g.addColorStop(0,   'rgba(167,139,250,0)')
          g.addColorStop(0.4, 'rgba(124,58,237,0.9)')
          g.addColorStop(0.5, 'rgba(196,181,253,1)')
          g.addColorStop(0.6, 'rgba(124,58,237,0.9)')
          g.addColorStop(1,   'rgba(167,139,250,0)')
          c.fillStyle = g
          const rw = Math.max(1.5, bw - 2)
          c.beginPath()
          c.roundRect(x - rw / 2, H / 2 - h / 2, rw, h, 2)
          c.fill()
        }
        const pulse = 0.3 + Math.sin(Date.now() / 300) * 0.2
        c.strokeStyle = `rgba(124,58,237,${pulse})`
        c.lineWidth = 1
        c.beginPath(); c.moveTo(0, H / 2); c.lineTo(W, H / 2); c.stroke()
      }
      draw()
    } catch {}
  }

  const stopVisualizer = () => {
    cancelAnimationFrame(rafRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    const canvas = canvasRef.current
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
  }

  const startRecording = async () => {
    setError('')
    setStatus('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      setActive(true)
      setStatus('🔴 Enregistrement… cliquer ⏹ pour envoyer')
      onStateChange?.('listening')
      startVisualizer(stream)

      // Choisir le meilleur format supporté
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
        .find(t => MediaRecorder.isTypeSupported(t)) || 'audio/webm'
      mimeRef.current = mime

      chunksRef.current = []
      const mr = new MediaRecorder(stream, { mimeType: mime })
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        setStatus('⏳ Transcription en cours…')
        try {
          const blob = new Blob(chunksRef.current, { type: mimeRef.current })
          if (blob.size < 1000) {
            setStatus('Audio trop court — réessaie')
            setTimeout(() => { setActive(false); setStatus(''); onStateChange?.('idle') }, 2000)
            return
          }
          const result = await transcribeViaBackend(blob, mimeRef.current)
          const text = result?.text ?? result
          const voiceMeta = { energy: result?.voice_energy || 'normal', duration: result?.voice_duration || 0 }
          if (text) {
            setStatus(`✓ "${text.slice(0, 60)}${text.length > 60 ? '…' : ''}"`)
            onTranscript?.(text, voiceMeta)
          } else {
            setStatus('Rien capté — parle plus près du micro')
          }
        } catch (err) {
          setError(err.message)
          setStatus('')
        }
        setTimeout(() => { setActive(false); setStatus(''); onStateChange?.('idle') }, 2200)
      }
      mrRef.current = mr
      mr.start(250) // chunk toutes les 250ms
    } catch (err) {
      const msg = err.name === 'NotAllowedError'
        ? 'Permission micro refusée'
        : err.name === 'NotFoundError'
          ? 'Aucun micro détecté'
          : `Erreur : ${err.message}`
      setError(msg)
      setActive(false)
      onStateChange?.('idle')
    }
  }

  const stopRecording = () => {
    if (mrRef.current && mrRef.current.state !== 'inactive') {
      mrRef.current.stop()
      mrRef.current = null
    }
    stopVisualizer()
  }

  const toggle = () => {
    if (disabled) return
    if (active) stopRecording()
    else startRecording()
  }

  useEffect(() => () => {
    stopRecording()
    stopVisualizer()
  }, [])

  return (
    <div className={`voice-input ${active ? 'voice-active' : ''}`}>
      {active && (
        <div className="voice-visualizer">
          <canvas ref={canvasRef} width={280} height={48} />
          {status && <div className="voice-interim">{status}</div>}
        </div>
      )}
      {!active && status && <div className="voice-interim" style={{ fontSize: '0.7rem', maxWidth: 200 }}>{status}</div>}
      {error && <div className="voice-error" title={error} style={{ fontSize: '0.72rem', color: 'var(--red)', maxWidth: 200 }}>⚠️ {error}</div>}
      <button
        className={`voice-btn ${active ? 'voice-btn-active' : ''}`}
        onClick={toggle}
        disabled={disabled}
        title={active ? 'Arrêter et transcrire' : 'Parler en français (cliquer pour démarrer, re-cliquer pour envoyer)'}
      >
        {active ? '⏹' : '🎙️'}
      </button>
    </div>
  )
}
