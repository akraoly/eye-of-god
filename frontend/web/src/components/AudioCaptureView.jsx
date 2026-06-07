/**
 * AudioCaptureView — Capture audio, enregistrements, détection de mots-clés
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

// ── Waveform Visualizer ───────────────────────────────────────────────────────
function WaveformBars({ active, bars = 24 }) {
  const [heights, setHeights] = useState(() => Array(bars).fill(8))
  const timerRef = useRef(null)

  useEffect(() => {
    if (!active) {
      setHeights(Array(bars).fill(8))
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(() => {
      setHeights(Array(bars).fill(0).map(() => 8 + Math.random() * 56))
    }, 80)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [active, bars])

  return (
    <div className="waveform-bars" style={{
      display: 'flex', alignItems: 'center', gap: 3, height: 72, padding: '0 12px',
      background: '#000820', borderRadius: 8, border: '1px solid var(--border)',
    }}>
      {heights.map((h, i) => (
        <div key={i} style={{
          flex: 1, height: h, borderRadius: 2,
          background: active
            ? `hsl(${180 + i * 4}, 90%, ${40 + (h / 64) * 30}%)`
            : 'var(--text3)',
          transition: active ? 'height 0.08s ease' : 'height 0.3s ease',
        }} />
      ))}
    </div>
  )
}

// ── Timer d'enregistrement ───────────────────────────────────────────────────
function RecordTimer({ running }) {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(null)

  useEffect(() => {
    if (running) {
      startRef.current = Date.now()
      setElapsed(0)
      const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 500)
      return () => clearInterval(t)
    } else {
      setElapsed(0)
    }
  }, [running])

  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const ss = String(elapsed % 60).padStart(2, '0')
  return <span style={{ color: '#ef4444', fontWeight: 800, fontSize: '1.1rem', fontFamily: 'monospace' }}>{mm}:{ss}</span>
}

// ── Composant principal ───────────────────────────────────────────────────────
export default function AudioCaptureView() {
  const [sessions,      setSessions]      = useState([])
  const [sessionId,     setSessionId]     = useState('')
  const [microphones,   setMicrophones]   = useState([])
  const [micLoading,    setMicLoading]    = useState(false)
  const [selectedMic,   setSelectedMic]   = useState('')
  const [duration,      setDuration]      = useState(30)
  const [quality,       setQuality]       = useState('medium')
  const [recording,     setRecording]     = useState(false)
  const [recordings,    setRecordings]    = useState([])
  const [keyword,       setKeyword]       = useState('')
  const [keywordActive, setKeywordActive] = useState(false)
  const [playingId,     setPlayingId]     = useState(null)
  const [error,         setError]         = useState('')
  const [loading,       setLoading]       = useState(false)
  const [recordJobId,   setRecordJobId]   = useState(null)
  const audioRef = useRef(null)
  const recordTimerRef = useRef(null)

  // Charger les sessions
  useEffect(() => {
    apiFetch('/pentest/jobs').then(r => r.json()).then(d => {
      setSessions(d.jobs || [])
    }).catch(() => {})
  }, [])

  // Charger les enregistrements
  const loadRecordings = useCallback(() => {
    const qs = sessionId ? `?session_id=${sessionId}` : ''
    apiFetch(`/audio/recordings${qs}`)
      .then(r => r.json()).then(d => setRecordings(d.recordings || [])).catch(() => {})
  }, [sessionId])

  useEffect(() => {
    loadRecordings()
    const t = setInterval(loadRecordings, 5000)
    return () => clearInterval(t)
  }, [loadRecordings])

  // Lister les micros
  const listMics = async () => {
    if (!sessionId) { setError('Sélectionner une session d\'abord'); return }
    setMicLoading(true)
    setError('')
    try {
      const r = await apiFetch(`/audio/microphones/${sessionId}`)
      const d = await r.json()
      setMicrophones(d.microphones || [])
    } catch { setError('Impossible de récupérer les microphones') }
    setMicLoading(false)
  }

  // Démarrer l'enregistrement
  const startRecording = async () => {
    if (!sessionId) { setError('Sélectionner une session'); return }
    setError('')
    setLoading(true)
    try {
      const r = await apiFetch('/audio/record/start', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          duration,
          quality,
          mic_id: selectedMic || undefined,
        }),
      })
      if (!r.ok) throw new Error('Erreur démarrage')
      const startData = await r.json().catch(() => ({}))
      setRecordJobId(startData.job_id || null)
      setRecording(true)
      recordTimerRef.current = setTimeout(() => {
        setRecording(false)
        loadRecordings()
      }, duration * 1000)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  // Arrêter l'enregistrement
  const stopRecording = async () => {
    if (recordTimerRef.current) clearTimeout(recordTimerRef.current)
    setRecording(false)
    try {
      if (recordJobId) await apiFetch(`/audio/record/stop/${recordJobId}`, { method: 'POST' }).catch(() => {})
    } catch {}
    loadRecordings()
  }

  // Lire un fichier audio
  const playAudio = (rec) => {
    if (playingId === rec.id) {
      audioRef.current?.pause()
      setPlayingId(null)
      return
    }
    if (audioRef.current) {
      const token = localStorage.getItem('eye_token') || ''
      audioRef.current.src = `/api/audio/download/${rec.id}?token=${token}`
      audioRef.current.play()
      setPlayingId(rec.id)
      audioRef.current.onended = () => setPlayingId(null)
    }
  }

  // Supprimer un enregistrement
  const deleteRecording = async (id) => {
    await apiFetch(`/audio/recordings/${id}`, { method: 'DELETE' }).catch(() => {})
    setRecordings(prev => prev.filter(r => r.id !== id))
  }

  // Test sonar
  const playSonar = () => {
    try {
      const ctx = new AudioContext()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      osc.frequency.setValueAtTime(880, ctx.currentTime)
      osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.8)
      gain.gain.setValueAtTime(0.3, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.9)
      osc.start(); osc.stop(ctx.currentTime + 0.9)
    } catch {}
  }

  const fmtDuration = s => s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${s % 60 ? `${s % 60}s` : ''}`
  const fmtSize = b => {
    if (!b) return ''
    if (b < 1024) return `${b}B`
    if (b < 1048576) return `${(b / 1024).toFixed(1)}KB`
    return `${(b / 1048576).toFixed(1)}MB`
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>🎤</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            AUDIO CAPTURE
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Enregistrement · Surveillance · Mots-clés
          </div>
        </div>
        <button onClick={playSonar} style={{
          marginLeft: 'auto', padding: '6px 16px', background: '#38bdf820',
          border: '1px solid #38bdf850', borderRadius: 8, color: '#38bdf8',
          cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700,
        }}>
          📡 Sonar Test
        </button>
      </div>

      {error && (
        <div style={{ background: '#ef444420', border: '1px solid #ef4444', borderRadius: 8, padding: '8px 14px', marginBottom: 16, color: '#ef4444', fontSize: '0.8rem' }}>
          ⚠ {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Colonne gauche */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Session */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 10 }}>SESSION CIBLE</div>
            <select
              value={sessionId}
              onChange={e => setSessionId(e.target.value)}
              style={{
                width: '100%', padding: '8px 12px', background: '#000820',
                border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)',
                fontSize: '0.8rem', marginBottom: 10,
              }}
            >
              <option value="">— Sélectionner une session —</option>
              {sessions.map(s => (
                <option key={s.job_id} value={s.job_id}>{s.target} ({s.job_id?.slice(0, 8)})</option>
              ))}
            </select>
            <button onClick={listMics} disabled={micLoading || !sessionId} style={{
              width: '100%', padding: '7px 0', background: 'var(--accent2)',
              border: 'none', borderRadius: 8, color: '#000', fontSize: '0.78rem',
              fontWeight: 700, cursor: 'pointer', opacity: !sessionId ? 0.4 : 1,
            }}>
              {micLoading ? '⟳ Chargement…' : '🎙 Lister les microphones'}
            </button>
            {microphones.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 6 }}>Microphones disponibles</div>
                {microphones.map((m, i) => {
                  const micId = m.id || m.name || String(i)
                  return (
                    <div key={i} onClick={() => setSelectedMic(micId)} style={{
                      padding: '6px 10px', borderRadius: 6, cursor: 'pointer', marginBottom: 4,
                      background: selectedMic === micId ? 'var(--glow2)' : '#ffffff08',
                      border: `1px solid ${selectedMic === micId ? 'var(--accent)' : 'var(--border)'}`,
                      fontSize: '0.75rem', color: 'var(--text)',
                    }}>
                      🎙 {m.name || m.id || `Mic ${i}`}
                      {m.default && <span style={{ color: 'var(--accent)', fontSize: '0.6rem', marginLeft: 8 }}>DEFAULT</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Paramètres */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>PARAMÈTRES</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text2)', marginBottom: 6 }}>
                <span>Durée</span>
                <span style={{ color: 'var(--accent)' }}>{fmtDuration(duration)}</span>
              </div>
              <input type="range" min={10} max={300} step={10} value={duration}
                onChange={e => setDuration(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem', color: 'var(--text3)' }}>
                <span>10s</span><span>5min</span>
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text2)', marginBottom: 6 }}>Qualité</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {['low', 'medium', 'high'].map(q => (
                  <button key={q} onClick={() => setQuality(q)} style={{
                    flex: 1, padding: '6px 0', borderRadius: 6,
                    border: `1px solid ${quality === q ? 'var(--accent)' : 'var(--border)'}`,
                    background: quality === q ? 'var(--glow2)' : 'transparent',
                    color: quality === q ? 'var(--accent)' : 'var(--text2)', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600,
                  }}>
                    {q === 'low' ? '🔇 Low' : q === 'medium' ? '🔉 Med' : '🔊 High'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Keyword detection */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>DÉTECTION MOTS-CLÉS</div>
              <div onClick={() => setKeywordActive(v => !v)} style={{
                width: 40, height: 22, borderRadius: 11, cursor: 'pointer',
                background: keywordActive ? 'var(--accent)' : '#ffffff20', position: 'relative', transition: 'background 0.2s',
              }}>
                <div style={{
                  position: 'absolute', top: 3, left: keywordActive ? 21 : 3, width: 16, height: 16,
                  borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                }} />
              </div>
            </div>
            <input type="text" placeholder="mot-clé, alarme, password…" value={keyword}
              onChange={e => setKeyword(e.target.value)} disabled={!keywordActive}
              style={{
                width: '100%', padding: '8px 12px', background: '#000820',
                border: `1px solid ${keywordActive ? 'var(--border2)' : 'var(--border)'}`,
                borderRadius: 8, color: keywordActive ? 'var(--text)' : 'var(--text3)', fontSize: '0.8rem',
              }}
            />
            {keywordActive && keyword && (
              <div style={{ marginTop: 8, fontSize: '0.7rem', color: '#4ade80' }}>
                ✓ Détection active pour : "{keyword}"
              </div>
            )}
          </div>
        </div>

        {/* Colonne droite */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Visualisation + contrôles */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>VISUALISATION EN DIRECT</div>
            <WaveformBars active={recording} />
            <div style={{ textAlign: 'center', marginTop: 10, marginBottom: 16 }}>
              {recording ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', animation: 'neon-pulse 1s infinite', display: 'inline-block' }} />
                  <RecordTimer running={recording} />
                  <span style={{ color: 'var(--text3)', fontSize: '0.7rem' }}>/ {fmtDuration(duration)}</span>
                </div>
              ) : (
                <span style={{ color: 'var(--text3)', fontSize: '0.75rem' }}>En attente…</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              {!recording ? (
                <button onClick={startRecording} disabled={loading || !sessionId} style={{
                  flex: 1, padding: '10px 0', background: '#ef444430',
                  border: '1px solid #ef4444', borderRadius: 8, color: '#ef4444',
                  cursor: 'pointer', fontWeight: 800, fontSize: '0.85rem',
                  opacity: !sessionId ? 0.4 : 1,
                }}>
                  ⏺ {loading ? 'Démarrage…' : 'Enregistrer'}
                </button>
              ) : (
                <button onClick={stopRecording} style={{
                  flex: 1, padding: '10px 0', background: '#fbbf2430',
                  border: '1px solid #fbbf24', borderRadius: 8, color: '#fbbf24',
                  cursor: 'pointer', fontWeight: 800, fontSize: '0.85rem',
                }}>
                  ⏹ Arrêter
                </button>
              )}
            </div>
          </div>

          {/* Liste des enregistrements */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16, flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>ENREGISTREMENTS</div>
              <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>{recordings.length} fichier(s)</span>
            </div>
            {recordings.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text3)', fontSize: '0.78rem' }}>
                Aucun enregistrement
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
                {recordings.map(rec => (
                  <div key={rec.id} style={{
                    padding: '10px 12px', background: '#ffffff06', border: '1px solid var(--border)',
                    borderRadius: 8, display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {rec.filename || `rec_${rec.id?.slice(0, 8)}`}
                      </div>
                      <div style={{ fontSize: '0.63rem', color: 'var(--text3)', marginTop: 2 }}>
                        {rec.duration ? `${rec.duration}s · ` : ''}
                        {rec.size ? `${fmtSize(rec.size)} · ` : ''}
                        {rec.created_at?.slice(11, 19)}
                      </div>
                      {rec.keyword_hits > 0 && (
                        <div style={{ fontSize: '0.6rem', color: '#fbbf24', marginTop: 2 }}>
                          🔑 {rec.keyword_hits} détection(s)
                        </div>
                      )}
                    </div>
                    <button onClick={() => playAudio(rec)} style={{
                      padding: '4px 10px', borderRadius: 6,
                      border: `1px solid ${playingId === rec.id ? '#ef4444' : 'var(--border2)'}`,
                      background: playingId === rec.id ? '#ef444420' : 'transparent',
                      color: playingId === rec.id ? '#ef4444' : 'var(--accent)', cursor: 'pointer', fontSize: '0.72rem',
                    }}>
                      {playingId === rec.id ? '⏸' : '▶'}
                    </button>
                    <a href={`/api/audio/download/${rec.id}`} download
                      style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)', color: 'var(--text2)', fontSize: '0.72rem', textDecoration: 'none' }}>
                      ⬇
                    </a>
                    <button onClick={() => deleteRecording(rec.id)} style={{
                      padding: '4px 8px', borderRadius: 6, border: '1px solid #ef444430',
                      background: 'transparent', color: '#ef4444', cursor: 'pointer', fontSize: '0.72rem',
                    }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
