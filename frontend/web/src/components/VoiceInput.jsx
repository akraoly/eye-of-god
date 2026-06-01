import { useState, useRef, useEffect } from 'react'

const SR = window.SpeechRecognition || window.webkitSpeechRecognition

export default function VoiceInput({ onTranscript, onStateChange, disabled }) {
  const [active, setActive] = useState(false)
  const [supported] = useState(!!SR)
  const [interim, setInterim] = useState('')
  const recRef  = useRef(null)
  const canvasRef = useRef(null)
  const rafRef = useRef(null)
  const analyserRef = useRef(null)
  const streamRef = useRef(null)

  // Visualiseur audio
  const startVisualizer = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const src = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      src.connect(analyser)
      analyserRef.current = analyser

      const canvas = canvasRef.current
      if (!canvas) return
      const c = canvas.getContext('2d')
      const data = new Uint8Array(analyser.frequencyBinCount)

      const draw = () => {
        rafRef.current = requestAnimationFrame(draw)
        analyser.getByteFrequencyData(data)
        c.clearRect(0, 0, canvas.width, canvas.height)

        const W = canvas.width, H = canvas.height
        const bars = 40
        const bw = W / bars

        for (let i = 0; i < bars; i++) {
          const idx = Math.floor((i / bars) * data.length)
          const v = data[idx] / 255
          const h = v * H * 0.85
          const x = i * bw + bw / 2

          // Barre miroir verticale
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

        // Ligne centrale pulsante
        c.strokeStyle = `rgba(124,58,237,${0.3 + Math.sin(Date.now() / 300) * 0.2})`
        c.lineWidth = 1
        c.beginPath()
        c.moveTo(0, H / 2)
        c.lineTo(W, H / 2)
        c.stroke()
      }
      draw()
    } catch (e) {
      console.warn('Microphone non accessible:', e)
    }
  }

  const stopVisualizer = () => {
    cancelAnimationFrame(rafRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    const canvas = canvasRef.current
    if (canvas) {
      canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  const startRecording = () => {
    if (!supported || disabled) return
    const rec = new SR()
    rec.lang = 'fr-FR'
    rec.continuous = false
    rec.interimResults = true

    rec.onstart = () => {
      setActive(true)
      setInterim('')
      onStateChange?.('listening')
      startVisualizer()
    }

    rec.onresult = (e) => {
      let final = ''
      let inter = ''
      for (const result of e.results) {
        if (result.isFinal) final += result[0].transcript
        else inter += result[0].transcript
      }
      setInterim(inter || final)
      if (final) {
        onTranscript?.(final.trim())
      }
    }

    rec.onerror = (e) => {
      console.warn('Speech error:', e.error)
      stopAll()
    }

    rec.onend = () => stopAll()

    recRef.current = rec
    rec.start()
  }

  const stopAll = () => {
    recRef.current?.stop()
    recRef.current = null
    setActive(false)
    setInterim('')
    onStateChange?.('idle')
    stopVisualizer()
  }

  useEffect(() => () => stopAll(), [])

  if (!supported) return null

  return (
    <div className={`voice-input ${active ? 'voice-active' : ''}`}>
      {/* Visualiseur onde */}
      {active && (
        <div className="voice-visualizer">
          <canvas ref={canvasRef} width={280} height={48} />
          {interim && <div className="voice-interim">{interim}</div>}
        </div>
      )}

      <button
        className={`voice-btn ${active ? 'voice-btn-active' : ''}`}
        onClick={active ? stopAll : startRecording}
        disabled={disabled}
        title={active ? 'Arrêter' : 'Parler (fr)'}
      >
        {active ? '⏹' : '🎙️'}
      </button>
    </div>
  )
}
