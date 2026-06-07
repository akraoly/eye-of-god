/**
 * FORENSICS — Analyse de fichiers malveillants, désobfuscation PowerShell, cases.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

function Dropzone({ onFile, disabled }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }, [onFile])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)

  return (
    <div
      className={`forensics-dropzone ${dragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        style={{ display: 'none' }}
        onChange={e => e.target.files[0] && onFile(e.target.files[0])}
        disabled={disabled}
      />
      <div className="forensics-dropzone-icon">📁</div>
      <div className="forensics-dropzone-text">
        {disabled ? 'Analyse en cours…' : 'Glisser un fichier ici ou cliquer'}
      </div>
      <div className="forensics-dropzone-hint">
        EXE, DLL, PDF, JS, PS1, ZIP, PCAP…
      </div>
    </div>
  )
}

function AnalysisSteps({ steps }) {
  if (!steps?.length) return null
  const STATUS_ICON  = { pending: '○', running: '⟳', done: '✓', error: '✗' }
  const STATUS_COLOR = { pending: 'var(--text3)', running: '#fbbf24', done: '#4ade80', error: '#ef4444' }
  return (
    <div className="aegis-pipeline">
      {steps.map((s, i) => (
        <div key={i} className="aegis-step-row">
          <span style={{ color: STATUS_COLOR[s.status], fontSize: '0.75rem', fontWeight: 700, minWidth: 14 }}>
            {STATUS_ICON[s.status] || '○'}
          </span>
          <span className="aegis-step-name">{s.name}</span>
          {s.status === 'running' && <span className="aegis-spinner" />}
          {s.detail && <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>{s.detail}</span>}
        </div>
      ))}
    </div>
  )
}

function ResultsSection({ result }) {
  if (!result) return null
  const { file_info, iocs, mitre_ttps, sandbox } = result

  return (
    <div className="osint-grid">
      {file_info && (
        <div className="aegis-panel">
          <div className="aegis-panel-header"><span className="aegis-panel-icon">📋</span>Informations fichier</div>
          <div className="forensics-info-grid">
            {Object.entries(file_info).map(([k, v]) => (
              <div key={k} className="forensics-info-row">
                <span className="forensics-info-key">{k}</span>
                <span className="forensics-info-val" style={{ fontFamily: typeof v === 'string' && v.length > 30 ? 'monospace' : 'inherit' }}>
                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {iocs?.length > 0 && (
        <div className="aegis-panel">
          <div className="aegis-panel-header">
            <span className="aegis-panel-icon">🎯</span>
            <span>IOCs Extraits</span>
            <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: '#ef4444' }}>{iocs.length}</span>
          </div>
          <div className="aegis-feed">
            {iocs.map((ioc, i) => (
              <div key={i} className="aegis-feed-row">
                <span style={{ fontSize: '0.65rem', color: 'var(--accent)', fontFamily: 'monospace', minWidth: 60 }}>
                  {ioc.type || '?'}
                </span>
                <span className="aegis-feed-title">{ioc.value || ioc}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {mitre_ttps?.length > 0 && (
        <div className="aegis-panel">
          <div className="aegis-panel-header"><span className="aegis-panel-icon">🗺️</span>MITRE ATT&CK TTPs</div>
          <div className="aegis-feed">
            {mitre_ttps.map((t, i) => (
              <div key={i} className="aegis-feed-row">
                <span style={{ color: 'var(--accent)', fontFamily: 'monospace', fontSize: '0.7rem', minWidth: 70 }}>
                  {t.id || t.technique_id}
                </span>
                <span className="aegis-feed-title">{t.name || t.technique_name}</span>
                {t.tactic && <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>{t.tactic}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {sandbox && (
        <div className="aegis-panel">
          <div className="aegis-panel-header"><span className="aegis-panel-icon">🧪</span>Sandbox Output</div>
          <pre className="forensics-sandbox-output">{
            typeof sandbox === 'string' ? sandbox : JSON.stringify(sandbox, null, 2)
          }</pre>
        </div>
      )}
    </div>
  )
}

function PsDeobfuscate() {
  const [input, setInput]   = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const deobfuscate = async () => {
    if (!input.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/forensics/deobfuscate', {
        method: 'POST',
        body: JSON.stringify({ code: input, language: 'powershell' }),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setOutput(data.deobfuscated || data.result || data.output || JSON.stringify(data))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">🔧</span>Désobfuscation PowerShell</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 4 }}>Code obfusqué</div>
          <textarea
            className="forensics-ps-input"
            rows={8}
            placeholder="Coller le code PowerShell obfusqué…"
            value={input}
            onChange={e => setInput(e.target.value)}
          />
        </div>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 4 }}>Résultat désobfusqué</div>
          <textarea
            className="forensics-ps-input"
            rows={8}
            value={output}
            readOnly
            placeholder="Résultat ici…"
          />
        </div>
      </div>
      {error && <div className="osint-error-banner">{error}</div>}
      <button className="aegis-launch-btn" onClick={deobfuscate} disabled={loading || !input.trim()}>
        {loading ? '⏳ Désobfuscation…' : '▶ Désobfusquer'}
      </button>
    </div>
  )
}

export default function ForensicsView() {
  const [file,    setFile]    = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [steps,   setSteps]   = useState([])
  const [result,  setResult]  = useState(null)
  const [cases,   setCases]   = useState([])
  const [error,   setError]   = useState(null)

  useEffect(() => {
    apiFetch('/forensics/cases').then(r => r.json()).then(d => setCases(d.cases || d || [])).catch(() => {})
  }, [])

  const analyze = async (f) => {
    setFile(f)
    setAnalyzing(true)
    setError(null)
    setResult(null)
    setSteps([
      { name: 'Hachage & identification', status: 'running' },
      { name: 'Extraction strings',       status: 'pending' },
      { name: 'Analyse sandbox',          status: 'pending' },
      { name: 'Extraction IOCs',          status: 'pending' },
      { name: 'Mapping MITRE TTPs',       status: 'pending' },
    ])

    try {
      const fd = new FormData()
      fd.append('file', f)
      const token = localStorage.getItem('eye_token')
      const res = await fetch('/api/forensics/analyze', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      })

      // Simulate step progression for UX
      const simulate = (idx) => {
        if (idx >= 5) return
        setSteps(prev => prev.map((s, i) => {
          if (i === idx)     return { ...s, status: 'done' }
          if (i === idx + 1) return { ...s, status: 'running' }
          return s
        }))
      }
      let stepIdx = 0
      const stepTimer = setInterval(() => {
        stepIdx++
        simulate(stepIdx - 1)
        if (stepIdx >= 5) clearInterval(stepTimer)
      }, 600)

      if (!res.ok) throw new Error(`Erreur analyse : ${res.status}`)
      const data = await res.json()
      clearInterval(stepTimer)
      setSteps(prev => prev.map(s => ({ ...s, status: 'done' })))
      setResult(data)

      apiFetch('/forensics/cases').then(r => r.json()).then(d => setCases(d.cases || d || [])).catch(() => {})
    } catch (err) {
      setError(err.message)
      setSteps(prev => prev.map(s => ({ ...s, status: s.status === 'running' ? 'error' : s.status })))
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🧪</span>
          <div>
            <div className="aegis-title">FORENSICS</div>
            <div className="aegis-subtitle">Analyse malware · IOCs · MITRE TTPs · Désobfuscation PS1</div>
          </div>
        </div>
        {analyzing && (
          <div className="aegis-header-right">
            <span className="aegis-live-dot" />
            <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>ANALYSE</span>
          </div>
        )}
      </div>

      <div className="aegis-panel" style={{ marginBottom: 12 }}>
        <div className="aegis-panel-header"><span className="aegis-panel-icon">📤</span>Upload fichier</div>
        <Dropzone onFile={analyze} disabled={analyzing} />
        {file && (
          <div style={{ marginTop: 8, fontSize: '0.72rem', color: 'var(--text2)' }}>
            Fichier : <strong>{file.name}</strong> — {(file.size / 1024).toFixed(1)} KB
          </div>
        )}
        {steps.length > 0 && <AnalysisSteps steps={steps} />}
        {error && <div className="osint-error-banner" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      {result && <ResultsSection result={result} />}

      <PsDeobfuscate />

      {cases.length > 0 && (
        <div className="aegis-panel" style={{ marginTop: 12 }}>
          <div className="aegis-panel-header">
            <span className="aegis-panel-icon">📂</span>
            <span>Historique des analyses</span>
          </div>
          <div className="creds-vault-table">
            <div className="creds-vault-header" style={{ gridTemplateColumns: '1fr 80px 80px 100px' }}>
              <span>Fichier</span><span>Type</span><span>Statut</span><span>Date</span>
            </div>
            {cases.slice(0, 15).map((c, i) => (
              <div key={i} className="creds-vault-row" style={{ gridTemplateColumns: '1fr 80px 80px 100px' }}>
                <span className="creds-user">{c.filename || c.file_name || c.name || '—'}</span>
                <span className="creds-type">{c.file_type || c.type || '—'}</span>
                <span style={{
                  fontSize: '0.7rem', fontWeight: 700,
                  color: c.status === 'malicious' ? '#ef4444' : c.status === 'clean' ? '#4ade80' : 'var(--text2)',
                }}>
                  {c.status || '—'}
                </span>
                <span className="creds-date">
                  {c.analyzed_at ? new Date(c.analyzed_at).toLocaleDateString('fr-FR') : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
