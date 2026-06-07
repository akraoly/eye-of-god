/**
 * OSINT RECON — Reconnaissance passive et active sur cibles.
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch, auth } from '../utils/auth'

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button className="osint-copy-btn" onClick={copy} title="Copier">
      {copied ? '✓' : '⎘'}
    </button>
  )
}

function DnsPanel({ dns }) {
  if (!dns) return null
  const sections = [
    { key: 'A',   label: 'A Records',   color: '#38bdf8' },
    { key: 'MX',  label: 'MX Records',  color: '#a78bfa' },
    { key: 'NS',  label: 'NS Records',  color: '#4ade80' },
    { key: 'TXT', label: 'TXT Records', color: '#fbbf24' },
  ]
  return (
    <div className="osint-panel">
      <div className="osint-panel-header">DNS Results</div>
      <div className="osint-dns-grid">
        {sections.map(({ key, label, color }) => (
          <div key={key} className="osint-dns-section">
            <div className="osint-dns-label" style={{ color }}>{label}</div>
            {dns[key]?.length > 0 ? dns[key].map((rec, i) => (
              <div key={i} className="osint-dns-record">
                <span>{rec}</span>
                <CopyBtn text={rec} />
              </div>
            )) : <div className="osint-empty-line">—</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

function SubdomainsPanel({ subdomains }) {
  if (!subdomains?.length) return null
  return (
    <div className="osint-panel">
      <div className="osint-panel-header">
        Subdomains
        <span className="osint-count-badge">{subdomains.length}</span>
      </div>
      <div className="osint-list-scroll">
        {subdomains.map((sub, i) => (
          <div key={i} className="osint-list-row">
            <span className="osint-subdomain">{sub}</span>
            <CopyBtn text={sub} />
          </div>
        ))}
      </div>
    </div>
  )
}

function DorksPanel({ dorks }) {
  if (!dorks?.length) return null
  return (
    <div className="osint-panel">
      <div className="osint-panel-header">Google Dorks</div>
      <div className="osint-list-scroll">
        {dorks.map((d, i) => (
          <div key={i} className="osint-dork-row">
            <a
              href={`https://www.google.com/search?q=${encodeURIComponent(d)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="osint-dork-link"
            >
              {d}
            </a>
            <CopyBtn text={d} />
          </div>
        ))}
      </div>
    </div>
  )
}

function InfraPanel({ infra }) {
  if (!infra?.length) return null
  return (
    <div className="osint-panel">
      <div className="osint-panel-header">Infrastructure Map</div>
      <div className="osint-infra-grid">
        {infra.map((item, i) => (
          <div key={i} className="osint-infra-row">
            <span className="osint-infra-ip">{item.ip}</span>
            <span className="osint-infra-host">{item.hostname || item.host || '—'}</span>
            <span className="osint-infra-services">
              {(item.services || item.ports || []).join(', ') || '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function StreamPanel({ lines }) {
  const ref = useRef(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [lines])
  if (!lines?.length) return null
  return (
    <div className="osint-panel">
      <div className="osint-panel-header">Live Stream</div>
      <div className="osint-stream-log" ref={ref}>
        {lines.map((line, i) => (
          <div key={i} className="osint-stream-line">{line}</div>
        ))}
      </div>
    </div>
  )
}

export default function OsintView() {
  const [target, setTarget]       = useState('')
  const [running, setRunning]     = useState(false)
  const [streamLines, setStreamLines] = useState([])
  const [dns, setDns]             = useState(null)
  const [subdomains, setSubdomains] = useState(null)
  const [dorks, setDorks]         = useState(null)
  const [infra, setInfra]         = useState(null)
  const [history, setHistory]     = useState([])
  const [error, setError]         = useState(null)
  const esRef = useRef(null)

  const loadHistory = () => {
    apiFetch('/osint/recon/history').then(r => r.json()).then(d => setHistory(d.jobs || d || [])).catch(() => {})
  }

  useEffect(() => {
    loadHistory()
    const t = setInterval(loadHistory, 30000)
    return () => clearInterval(t)
  }, [])

  const launch = async () => {
    if (!target.trim()) return
    setRunning(true)
    setError(null)
    setStreamLines([])
    setDns(null)
    setSubdomains(null)
    setDorks(null)
    setInfra(null)
    esRef.current?.close()

    try {
      const res = await apiFetch('/osint/recon', {
        method: 'POST',
        body: JSON.stringify({ target: target.trim() }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Erreur ${res.status}`)
      }
      const { job_id } = await res.json()
      setStreamLines([`[${new Date().toLocaleTimeString()}] OSINT lancé sur : ${target} (job: ${job_id})`])

      const token = auth.getToken()
      const es = new EventSource(`/api/osint/stream/${job_id}${token ? `?token=${token}` : ''}`)
      esRef.current = es

      es.onmessage = e => {
        try {
          const data = JSON.parse(e.data)
          const msg = data.message || data.step || data.data?.message || JSON.stringify(data)
          setStreamLines(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])

          if (data.dns)        setDns(data.dns)
          if (data.subdomains) setSubdomains(data.subdomains)
          if (data.dorks)      setDorks(data.dorks)
          if (data.infra)      setInfra(data.infra)

          if (data.type === 'complete') {
            const r = data.data || data
            if (r.dns)        setDns(r.dns)
            if (r.subdomains) setSubdomains(r.subdomains)
            if (r.dorks)      setDorks(r.dorks)
            if (r.infra)      setInfra(r.infra)
            setRunning(false)
            loadHistory()
            es.close()
          }
          if (data.type === 'error') {
            setError(data.message || 'Erreur OSINT')
            setRunning(false)
            es.close()
          }
        } catch {}
      }
      es.onerror = () => { setRunning(false); es.close() }
    } catch (err) {
      setError(err.message)
      setRunning(false)
    }
  }

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🔍</span>
          <div>
            <div className="aegis-title">OSINT RECON</div>
            <div className="aegis-subtitle">Reconnaissance passive · DNS · Subdomains · Dorks · Infra</div>
          </div>
        </div>
        {running && (
          <div className="aegis-header-right">
            <span className="aegis-live-dot" />
            <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>SCANNING</span>
          </div>
        )}
      </div>

      <div className="osint-launch-bar">
        <input
          className="osint-target-input"
          placeholder="Cible : domaine, IP ou organisation…"
          value={target}
          onChange={e => setTarget(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !running && launch()}
          disabled={running}
        />
        <button
          className={`osint-launch-btn ${running ? 'running' : ''}`}
          onClick={running ? () => { esRef.current?.close(); setRunning(false) } : launch}
          disabled={!running && !target.trim()}
        >
          {running ? '⏹ Arrêter' : '▶ Lancer OSINT'}
        </button>
      </div>

      {error && (
        <div className="osint-error-banner">{error}</div>
      )}

      <div className="osint-grid">
        <StreamPanel lines={streamLines} />
        <DnsPanel dns={dns} />
        <SubdomainsPanel subdomains={subdomains} />
        <DorksPanel dorks={dorks} />
        <InfraPanel infra={infra} />

        {history.length > 0 && (
          <div className="osint-panel">
            <div className="osint-panel-header">Historique OSINT</div>
            <div className="osint-history-table">
              {history.slice(0, 10).map((job, i) => (
                <div key={i} className="osint-history-row">
                  <span className={`osint-status-badge ${job.status}`}>{job.status}</span>
                  <span className="osint-history-target">{job.target}</span>
                  <span className="osint-history-date">
                    {job.created_at ? new Date(job.created_at).toLocaleString('fr-FR') : '—'}
                  </span>
                  <button
                    className="osint-reload-btn"
                    onClick={() => setTarget(job.target)}
                    title="Relancer"
                  >
                    ↺
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
