/**
 * SDRPanel — Software Defined Radio control interface.
 * Hardware detection, frequency scan, listen, capture IQ, decode, gate detect, replay.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

const MODULATIONS = ['FM', 'AM', 'LSB', 'USB', 'NFM', 'WFM']
const SPAN_OPTIONS = [
  { label: '1 MHz',   value: 1 },
  { label: '5 MHz',   value: 5 },
  { label: '10 MHz',  value: 10 },
  { label: '20 MHz',  value: 20 },
  { label: '50 MHz',  value: 50 },
  { label: '100 MHz', value: 100 },
]

// ── Hardware Badge ────────────────────────────────────────────────────────────
function HardwareBadge({ hw }) {
  if (!hw) return <span style={badge('gray')}>⬜ Detecting…</span>
  if (hw.hackrf)  return <span style={badge('#22c55e')}>🟢 HackRF</span>
  if (hw.rtlsdr)  return <span style={badge('#eab308')}>🟡 RTL-SDR</span>
  return <span style={badge('#ef4444')}>🔴 Simulation</span>
}

function badge(color) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    background: color + '1a', border: `1px solid ${color}60`,
    color, borderRadius: 6, padding: '3px 10px',
    fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.03em',
  }
}

// ── Waterfall ─────────────────────────────────────────────────────────────────
function WaterfallDisplay({ waterfallData, startMhz, endMhz }) {
  const canvasRef = useRef(null)
  const rowsRef   = useRef([])
  const animRef   = useRef(null)

  // Scroll simulation: add animated noise rows
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height
    const ROW_H = 8
    const N_COLS = W

    function powerToColor(dbm) {
      const norm = Math.min(Math.max((dbm + 90) / 60, 0), 1)
      if (norm < 0.33) {
        const t = norm / 0.33
        return `rgb(0,${Math.round(t * 80)},${Math.round(80 + t * 175)})`
      } else if (norm < 0.66) {
        const t = (norm - 0.33) / 0.33
        return `rgb(${Math.round(t * 255)},${Math.round(80 + t * 175)},${Math.round(255 - t * 200)})`
      } else {
        const t = (norm - 0.66) / 0.34
        return `rgb(255,${Math.round(255 - t * 150)},${Math.round(55 - t * 55)})`
      }
    }

    function addRow(data) {
      const rowData = data || Array.from({ length: N_COLS }, (_, i) => {
        const freq = startMhz + (i / N_COLS) * (endMhz - startMhz)
        const knownPeaks = [88.0, 92.1, 95.3, 98.7, 103.4, 107.9, 162.4]
        let power = -88 + Math.random() * 6
        for (const p of knownPeaks) {
          const d = Math.abs(freq - p)
          if (d < 0.3) power = Math.max(power, -50 + (1 - d / 0.3) * 40 + Math.random() * 6)
        }
        return power
      })
      rowsRef.current.push(rowData)
      if (rowsRef.current.length > Math.floor(H / ROW_H) + 2) {
        rowsRef.current.shift()
      }
    }

    // Seed with provided waterfall data
    if (waterfallData?.length) {
      for (const row of waterfallData) addRow(row)
    }

    let lastTick = 0
    function frame(ts) {
      if (ts - lastTick > 200) {
        addRow(null)
        lastTick = ts
      }
      ctx.clearRect(0, 0, W, H)
      const rows = rowsRef.current
      for (let r = 0; r < rows.length; r++) {
        const y = H - (rows.length - r) * ROW_H
        if (y < 0) continue
        const row = rows[r]
        for (let c = 0; c < N_COLS; c++) {
          const idx = Math.floor(c / N_COLS * row.length)
          ctx.fillStyle = powerToColor(row[idx] ?? -90)
          ctx.fillRect(c, y, 1, ROW_H)
        }
      }
      animRef.current = requestAnimationFrame(frame)
    }
    animRef.current = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(animRef.current)
  }, [waterfallData, startMhz, endMhz])

  return (
    <div style={{ position: 'relative', background: '#000', borderRadius: 6, overflow: 'hidden', border: '1px solid #1a3a5c' }}>
      <canvas ref={canvasRef} width={600} height={120} style={{ display: 'block', width: '100%', height: 120 }} />
      <div style={{ position: 'absolute', bottom: 4, left: 8, right: 8, display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem', color: '#6b8aaa', pointerEvents: 'none' }}>
        <span>{startMhz} MHz</span>
        <span>{((startMhz + endMhz) / 2).toFixed(1)} MHz</span>
        <span>{endMhz} MHz</span>
      </div>
    </div>
  )
}

// ── Signal Peaks Bar ──────────────────────────────────────────────────────────
function PeaksBar({ peaks, startMhz, endMhz }) {
  if (!peaks?.length) return null
  const span = endMhz - startMhz
  return (
    <div style={{ position: 'relative', height: 28, background: '#050a14', border: '1px solid #1a3a5c', borderRadius: 4, marginTop: 4 }}>
      {peaks.map((p, i) => {
        const pct = Math.min(100, Math.max(0, ((p.frequency_mhz - startMhz) / span) * 100))
        return (
          <div
            key={i}
            style={{
              position: 'absolute', left: `${pct}%`, top: 0, bottom: 0,
              width: 2, background: '#00d4ff',
              transform: 'translateX(-50%)',
            }}
          >
            <div style={{
              position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
              background: '#0a1628', border: '1px solid #00d4ff44', borderRadius: 3,
              padding: '1px 4px', fontSize: '0.55rem', color: '#00d4ff', whiteSpace: 'nowrap', marginBottom: 2,
            }}>
              {p.frequency_mhz} MHz
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Recording Row ─────────────────────────────────────────────────────────────
function RecordingRow({ rec, onReplay, onDecode, onDelete }) {
  return (
    <tr style={{ borderBottom: '1px solid #1a3a5c10' }}>
      <td style={td}>{rec.frequency_mhz} MHz</td>
      <td style={td}><span style={modBadge}>{(rec.modulation || '—').toUpperCase()}</span></td>
      <td style={td}>{rec.duration ?? '—'}s</td>
      <td style={td}>{rec.protocol || '—'}</td>
      <td style={td}>
        <span style={{ color: rec.simulated ? '#eab308' : '#22c55e', fontSize: '0.65rem' }}>
          {rec.simulated ? 'SIM' : 'HW'}
        </span>
      </td>
      <td style={{ ...td, display: 'flex', gap: 4 }}>
        <ActionBtn label="▶ Replay"  onClick={() => onReplay(rec)} color="#00d4ff" />
        <ActionBtn label="Decode"    onClick={() => onDecode(rec)} color="#a78bfa" />
        <ActionBtn label="✕"         onClick={() => onDelete(rec)} color="#ef4444" />
      </td>
    </tr>
  )
}

const td = { padding: '5px 8px', fontSize: '0.72rem', color: '#e0e8f0', verticalAlign: 'middle' }
const modBadge = { background: '#00d4ff18', color: '#00d4ff', border: '1px solid #00d4ff40', borderRadius: 4, padding: '1px 5px', fontSize: '0.62rem' }

function ActionBtn({ label, onClick, color = '#00d4ff' }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: color + '18', border: `1px solid ${color}50`, color, borderRadius: 4,
        padding: '2px 7px', fontSize: '0.62rem', cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function SDRPanel() {
  const [hw,          setHw]          = useState(null)
  const [freqMhz,     setFreqMhz]     = useState('100.3')
  const [span,        setSpan]        = useState(20)
  const [gain,        setGain]        = useState(40)
  const [modulation,  setModulation]  = useState('FM')
  const [scanning,    setScanning]    = useState(false)
  const [scanProgress,setScanProgress]= useState(0)
  const [listening,   setListening]   = useState(false)
  const [listenTimer, setListenTimer] = useState(0)
  const [spectrum,    setSpectrum]    = useState(null)
  const [recordings,  setRecordings]  = useState([])
  const [loadingRecs, setLoadingRecs] = useState(false)
  const [status,      setStatus]      = useState('')
  const [gateResult,  setGateResult]  = useState(null)

  const listenRef   = useRef(null)
  const progressRef = useRef(null)

  // Derived frequency bounds from center + span
  const centerMhz = parseFloat(freqMhz) || 100.3
  const startMhz  = Math.max(0.1, centerMhz - span / 2)
  const endMhz    = centerMhz + span / 2

  useEffect(() => {
    loadHardware()
    loadRecordings()
  }, [])

  async function loadHardware() {
    try {
      const r = await apiFetch('/sdr/hardware')
      const d = await r.json()
      setHw(d)
    } catch (e) {
      setHw({ simulation_mode: true })
    }
  }

  async function loadRecordings() {
    setLoadingRecs(true)
    try {
      const r = await apiFetch('/sdr/recordings')
      const d = await r.json()
      setRecordings(d.recordings || [])
    } catch {
      setRecordings([])
    } finally {
      setLoadingRecs(false)
    }
  }

  const handleScan = useCallback(async () => {
    setScanning(true)
    setScanProgress(0)
    setStatus('Scanning…')
    // Animate progress bar
    let p = 0
    progressRef.current = setInterval(() => {
      p = Math.min(p + 2, 90)
      setScanProgress(p)
    }, 100)
    try {
      const r = await apiFetch('/sdr/scan', {
        method: 'POST',
        body: JSON.stringify({ start_mhz: startMhz, end_mhz: endMhz, step_hz: 10000, gain }),
      })
      const d = await r.json()
      setSpectrum(d)
      setStatus(`Scan complete — ${d.signals?.length ?? 0} samples`)
    } catch (e) {
      setStatus(`Scan failed: ${e.message}`)
    } finally {
      clearInterval(progressRef.current)
      setScanProgress(100)
      setTimeout(() => setScanProgress(0), 800)
      setScanning(false)
    }
  }, [startMhz, endMhz, gain])

  const handleListen = useCallback(async () => {
    setListening(true)
    setListenTimer(0)
    setStatus('Listening…')
    const duration = 10
    listenRef.current = setInterval(() => setListenTimer(t => t + 1), 1000)
    try {
      const r = await apiFetch('/sdr/listen', {
        method: 'POST',
        body: JSON.stringify({ frequency_mhz: centerMhz, modulation: modulation.toLowerCase(), duration, gain }),
      })
      const d = await r.json()
      setStatus(`Listen OK — ${d.file_size ? (d.file_size / 1024).toFixed(1) + ' KB' : 'simulated'}`)
      loadRecordings()
    } catch (e) {
      setStatus(`Listen failed: ${e.message}`)
    } finally {
      clearInterval(listenRef.current)
      setListening(false)
      setListenTimer(0)
    }
  }, [centerMhz, modulation, gain])

  const handleCaptureIQ = useCallback(async () => {
    setStatus('Capturing IQ…')
    try {
      const r = await apiFetch('/sdr/capture-iq', {
        method: 'POST',
        body: JSON.stringify({ frequency_mhz: centerMhz, sample_rate: 2000000, duration: 5 }),
      })
      const d = await r.json()
      setStatus(`IQ captured — ${d.file_size ? (d.file_size / 1024).toFixed(1) + ' KB' : 'simulated'}`)
      loadRecordings()
    } catch (e) {
      setStatus(`IQ capture failed: ${e.message}`)
    }
  }, [centerMhz])

  const handleGateDetect = useCallback(async () => {
    setStatus('Listening on 433.92 MHz…')
    setGateResult(null)
    try {
      const r = await apiFetch('/sdr/gate-detect', {
        method: 'POST',
        body: JSON.stringify({ frequency_mhz: 433.92 }),
      })
      const d = await r.json()
      setGateResult(d)
      setStatus(`Gate codes: ${(d.captured_codes || []).join(', ') || 'none'}`)
    } catch (e) {
      setStatus(`Gate detect failed: ${e.message}`)
    }
  }, [])

  const handleReplay = useCallback(async (rec) => {
    const freq = parseFloat(prompt('Replay on frequency (MHz)?', String(rec.frequency_mhz)))
    if (!freq) return
    try {
      const r = await apiFetch(`/sdr/recordings/${rec.id}/replay`, {
        method: 'POST',
        body: JSON.stringify({ frequency_mhz: freq, repeat: 1 }),
      })
      const d = await r.json()
      setStatus(d.simulated ? 'Replay simulated (no HackRF)' : 'Replay transmitted')
    } catch (e) {
      setStatus(`Replay failed: ${e.message}`)
    }
  }, [])

  const handleDecode = useCallback(async (rec) => {
    try {
      const r = await apiFetch(`/sdr/recordings/${rec.id}/decode?protocol=automatic`, { method: 'POST' })
      const d = await r.json()
      setStatus(`Decoded ${d.count} messages (${d.protocol})`)
      loadRecordings()
    } catch (e) {
      setStatus(`Decode failed: ${e.message}`)
    }
  }, [])

  const handleDelete = useCallback(async (rec) => {
    if (!confirm(`Delete recording ${rec.frequency_mhz} MHz?`)) return
    try {
      await apiFetch(`/sdr/recordings/${rec.id}`, { method: 'DELETE' })
      loadRecordings()
    } catch {
      setStatus('Delete failed')
    }
  }, [])

  const peaks = spectrum?.peaks || []

  return (
    <div style={{ background: 'var(--bg)', color: 'var(--text)', fontFamily: 'monospace' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '1rem', fontWeight: 700, color: '#00d4ff', letterSpacing: '0.06em' }}>SDR CONTROL</span>
        </div>
        <HardwareBadge hw={hw} />
      </div>

      {/* Simulation Banner */}
      {hw?.simulation_mode && (
        <div style={{
          background: '#eab30818', border: '1px solid #eab30840',
          borderRadius: 6, padding: '6px 12px', marginBottom: 10,
          fontSize: '0.72rem', color: '#eab308',
        }}>
          ⚠ No SDR hardware detected — running in simulation mode. Connect RTL-SDR or HackRF for real signals.
        </div>
      )}

      {/* Controls Row */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        {/* Frequency */}
        <label style={lbl}>
          Frequency (MHz)
          <input
            type="number" value={freqMhz} onChange={e => setFreqMhz(e.target.value)}
            style={inp}
            step="0.1"
          />
        </label>

        {/* Span */}
        <label style={lbl}>
          Span
          <select value={span} onChange={e => setSpan(Number(e.target.value))} style={inp}>
            {SPAN_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>

        {/* Gain */}
        <label style={{ ...lbl, flex: 2, minWidth: 140 }}>
          Gain: {gain} dB
          <input
            type="range" min={0} max={60} step={1} value={gain}
            onChange={e => setGain(Number(e.target.value))}
            style={{ width: '100%', accentColor: '#00d4ff' }}
          />
        </label>
      </div>

      {/* Modulation Buttons */}
      <div style={{ display: 'flex', gap: 5, marginBottom: 10, flexWrap: 'wrap' }}>
        {MODULATIONS.map(m => (
          <button key={m} onClick={() => setModulation(m)} style={{
            background: modulation === m ? '#00d4ff22' : '#0a1628',
            border: `1px solid ${modulation === m ? '#00d4ff' : '#1a3a5c'}`,
            color: modulation === m ? '#00d4ff' : '#6b8aaa',
            borderRadius: 5, padding: '4px 12px', fontSize: '0.72rem',
            cursor: 'pointer', fontWeight: modulation === m ? 700 : 400,
          }}>
            {m}
          </button>
        ))}
      </div>

      {/* Waterfall */}
      <WaterfallDisplay waterfallData={spectrum?.waterfall_data} startMhz={startMhz} endMhz={endMhz} />
      <PeaksBar peaks={peaks} startMhz={startMhz} endMhz={endMhz} />

      {/* Scan Progress */}
      {scanning && (
        <div style={{ margin: '6px 0', height: 4, background: '#0a1628', borderRadius: 2 }}>
          <div style={{ width: `${scanProgress}%`, height: '100%', background: '#00d4ff', borderRadius: 2, transition: 'width 0.1s' }} />
        </div>
      )}

      {/* Status */}
      {status && (
        <div style={{ fontSize: '0.68rem', color: '#6b8aaa', margin: '4px 0 8px', fontFamily: 'monospace' }}>
          › {status}
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        <button onClick={handleScan} disabled={scanning} style={actionBtn('#00d4ff')}>
          {scanning ? '⟳ Scanning…' : '📡 Scan'}
        </button>
        <button onClick={handleListen} disabled={listening} style={actionBtn('#22c55e')}>
          {listening ? `🎧 ${listenTimer}s…` : '🎧 Listen'}
        </button>
        <button onClick={handleCaptureIQ} style={actionBtn('#a78bfa')}>
          📦 Capture IQ
        </button>
        <button onClick={handleGateDetect} style={actionBtn('#f97316')}>
          🔑 Gate Detect
        </button>
      </div>

      {/* Gate Result */}
      {gateResult && (
        <div style={{ background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 6, padding: '8px 12px', marginBottom: 10 }}>
          <div style={{ fontSize: '0.7rem', color: '#00d4ff', marginBottom: 4, fontWeight: 700 }}>Gate/Remote Capture</div>
          <div style={{ fontSize: '0.68rem', color: '#e0e8f0' }}>Protocol: {gateResult.protocol_detected}</div>
          <div style={{ fontSize: '0.68rem', color: '#e0e8f0' }}>Rolling code: {gateResult.rolling_code ? 'Yes' : 'No'}</div>
          <div style={{ fontSize: '0.68rem', color: '#e0e8f0', marginTop: 4 }}>
            Codes: {(gateResult.captured_codes || []).map(c => (
              <span key={c} style={{ background: '#ff6b3518', border: '1px solid #ff6b3540', borderRadius: 3, padding: '1px 5px', marginRight: 4, color: '#ff6b35' }}>{c}</span>
            ))}
          </div>
          {gateResult.simulated && <div style={{ fontSize: '0.63rem', color: '#eab308', marginTop: 4 }}>⚠ Simulated data</div>}
        </div>
      )}

      {/* Top Signals */}
      {peaks.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: '0.68rem', color: '#6b8aaa', marginBottom: 4 }}>STRONGEST SIGNALS</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {peaks.map((p, i) => (
              <div key={i} style={{ background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 5, padding: '4px 10px' }}>
                <div style={{ fontSize: '0.75rem', color: '#00d4ff', fontWeight: 700 }}>{p.frequency_mhz} MHz</div>
                <div style={{ fontSize: '0.62rem', color: '#6b8aaa' }}>{p.power_dbm} dBm</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recordings Table */}
      <div style={{ fontSize: '0.68rem', color: '#6b8aaa', marginBottom: 6 }}>RECORDINGS ({recordings.length})</div>
      {loadingRecs ? (
        <div style={{ color: '#6b8aaa', fontSize: '0.7rem' }}>Loading…</div>
      ) : recordings.length === 0 ? (
        <div style={{ color: '#3a5a7a', fontSize: '0.7rem', fontStyle: 'italic' }}>No recordings yet.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1a3a5c' }}>
                {['Frequency', 'Mod', 'Duration', 'Protocol', 'Source', 'Actions'].map(h => (
                  <th key={h} style={{ ...td, color: '#6b8aaa', textAlign: 'left', fontWeight: 600, fontSize: '0.65rem' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recordings.map(rec => (
                <RecordingRow
                  key={rec.id}
                  rec={rec}
                  onReplay={handleReplay}
                  onDecode={handleDecode}
                  onDelete={handleDelete}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const lbl = { display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.65rem', color: '#6b8aaa', flex: 1, minWidth: 100 }
const inp = { background: '#0a1628', border: '1px solid #1a3a5c', color: '#e0e8f0', borderRadius: 5, padding: '5px 8px', fontSize: '0.75rem', width: '100%' }
function actionBtn(color) {
  return {
    background: color + '18', border: `1px solid ${color}50`, color,
    borderRadius: 6, padding: '6px 14px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600,
  }
}
