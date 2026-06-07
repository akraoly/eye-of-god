/**
 * AEGIS Dashboard — Vue unifiée temps réel.
 * 4 panneaux : Réseau live · Système · Opérations offensives · Alertes
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, auth } from '../utils/auth'

// ── Utilitaires ───────────────────────────────────────────────────────────────
const fmtBytes = b => {
  if (b == null) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`
  return `${(b / 1024 ** 3).toFixed(2)} GB`
}

const SEV_COLOR = {
  INFO:     '#38bdf8',
  LOW:      '#4ade80',
  MEDIUM:   '#fbbf24',
  HIGH:     '#f97316',
  CRITICAL: '#ef4444',
}

const SEV_BG = {
  INFO:     '#38bdf820',
  LOW:      '#4ade8020',
  MEDIUM:   '#fbbf2420',
  HIGH:     '#f9731620',
  CRITICAL: '#ef444420',
}

function SevBadge({ sev }) {
  return (
    <span style={{
      background: SEV_BG[sev] || '#ffffff10',
      color: SEV_COLOR[sev] || 'var(--text2)',
      border: `1px solid ${SEV_COLOR[sev] || '#ffffff30'}`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', fontWeight: 700,
    }}>
      {sev}
    </span>
  )
}

// ── Hook WebSocket réseau ─────────────────────────────────────────────────────
function useNetworkWS() {
  const [events,  setEvents]  = useState([])
  const [stats,   setStats]   = useState(null)
  const [status,  setStatus]  = useState('disconnected')
  const wsRef = useRef(null)
  const MAX   = 80

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    setStatus('connecting')
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/network/ws`)
    wsRef.current = ws

    ws.onopen  = () => setStatus('connected')
    ws.onclose = () => {
      setStatus('disconnected')
      setTimeout(connect, 3000)
    }
    ws.onerror = () => setStatus('error')
    ws.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'ping') return
        if (data.type === 'stats') {
          setStats(data)
          return
        }
        if (data.type === 'network_event') {
          setEvents(prev => [data, ...prev].slice(0, MAX))
        }
      } catch {}
    }
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return { events, stats, status }
}

// ── Panneau 1 : Réseau Live ───────────────────────────────────────────────────
function NetworkPanel() {
  const { events, stats, status } = useNetworkWS()
  const [snapshot, setSnapshot] = useState(null)

  useEffect(() => {
    apiFetch('/network/snapshot').then(r => r.json()).then(setSnapshot).catch(() => {})
    const t = setInterval(() => {
      apiFetch('/network/snapshot').then(r => r.json()).then(setSnapshot).catch(() => {})
    }, 5000)
    return () => clearInterval(t)
  }, [])

  const dot = status === 'connected' ? '#4ade80' : status === 'connecting' ? '#fbbf24' : '#ef4444'

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🌐</span>
        <span>Réseau Live</span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: dot, display: 'inline-block' }} />
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>{status}</span>
        </span>
      </div>

      {/* Stats snapshot */}
      {snapshot && (
        <div className="aegis-stats-row">
          <div className="aegis-stat-box">
            <div className="aegis-stat-val">{snapshot.conn_count}</div>
            <div className="aegis-stat-label">Connexions</div>
          </div>
          <div className="aegis-stat-box">
            <div className="aegis-stat-val" style={{ color: '#a78bfa' }}>{snapshot.established}</div>
            <div className="aegis-stat-label">Établies</div>
          </div>
          <div className="aegis-stat-box">
            <div className="aegis-stat-val" style={{ color: '#38bdf8' }}>{snapshot.listening}</div>
            <div className="aegis-stat-label">En écoute</div>
          </div>
          {stats && (
            <div className="aegis-stat-box">
              <div className="aegis-stat-val" style={{ color: '#4ade80' }}>{fmtBytes(stats.bytes_recv)}</div>
              <div className="aegis-stat-label">Reçus total</div>
            </div>
          )}
        </div>
      )}

      {/* Flux d'événements */}
      <div className="aegis-feed">
        {events.length === 0 ? (
          <div className="aegis-feed-empty">En attente d'événements réseau…</div>
        ) : events.map((evt, i) => (
          <div key={i} className={`aegis-feed-row${evt.is_suspicious ? ' aegis-suspicious' : ''}`}>
            <SevBadge sev={evt.severity} />
            <span className="aegis-feed-time">{evt.timestamp?.slice(11, 19)}</span>
            <span className="aegis-feed-title">{evt.title}</span>
            {evt.source_ip && (
              <span className="aegis-feed-ip">{evt.source_ip}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Panneau 2 : Système ───────────────────────────────────────────────────────
function SystemPanel() {
  const [metrics, setMetrics] = useState(null)
  const [history, setHistory] = useState([])
  const MAX_HIST = 30

  useEffect(() => {
    const fetch = () => {
      apiFetch('/system/metrics').then(r => r.json()).then(m => {
        setMetrics(m)
        setHistory(prev => [...prev, {
          ts:  Date.now(),
          cpu: m.cpu?.percent ?? 0,
          ram: m.memory?.percent ?? 0,
        }].slice(-MAX_HIST))
      }).catch(() => {})
    }
    fetch()
    const t = setInterval(fetch, 2000)
    return () => clearInterval(t)
  }, [])

  const SparkBar = ({ values, color }) => (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 28, marginTop: 4 }}>
      {values.map((v, i) => (
        <div key={i} style={{
          flex: 1, background: color, opacity: 0.5 + 0.5 * (i / values.length),
          height: `${Math.max(2, v)}%`, borderRadius: 1,
        }} />
      ))}
    </div>
  )

  const cpuHist = history.map(h => h.cpu)
  const ramHist = history.map(h => h.ram)

  const Bar = ({ val, color }) => (
    <div style={{ position: 'relative', height: 6, background: '#ffffff10', borderRadius: 3, overflow: 'hidden', marginTop: 4 }}>
      <div style={{ width: `${val}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.5s' }} />
    </div>
  )

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">💻</span>
        <span>Système</span>
        {metrics?.uptime && (
          <span style={{ marginLeft: 'auto', fontSize: '0.62rem', color: 'var(--text3)' }}>
            uptime {metrics.uptime}
          </span>
        )}
      </div>

      {metrics ? (
        <div className="aegis-sys-grid">
          {/* CPU */}
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">CPU</div>
            <div className="aegis-sys-val" style={{ color: metrics.cpu?.percent > 80 ? '#ef4444' : '#a78bfa' }}>
              {metrics.cpu?.percent?.toFixed(1)}%
            </div>
            <Bar val={metrics.cpu?.percent} color="#a78bfa" />
            <SparkBar values={cpuHist} color="#a78bfa" />
          </div>

          {/* RAM */}
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">RAM</div>
            <div className="aegis-sys-val" style={{ color: metrics.memory?.percent > 85 ? '#ef4444' : '#38bdf8' }}>
              {metrics.memory?.percent?.toFixed(1)}%
            </div>
            <Bar val={metrics.memory?.percent} color="#38bdf8" />
            <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginTop: 2 }}>
              {fmtBytes(metrics.memory?.used)} / {fmtBytes(metrics.memory?.total)}
            </div>
          </div>

          {/* Disque */}
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">Disque</div>
            <div className="aegis-sys-val" style={{ color: metrics.disk?.percent > 90 ? '#ef4444' : '#4ade80' }}>
              {metrics.disk?.percent?.toFixed(1)}%
            </div>
            <Bar val={metrics.disk?.percent} color="#4ade80" />
            <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginTop: 2 }}>
              {fmtBytes(metrics.disk?.used)} / {fmtBytes(metrics.disk?.total)}
            </div>
          </div>

          {/* Processus */}
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">Processus</div>
            <div className="aegis-sys-val" style={{ color: '#fbbf24' }}>
              {metrics.process_count ?? '—'}
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginTop: 4 }}>
              actifs
            </div>
          </div>
        </div>
      ) : (
        <div className="aegis-feed-empty">Chargement des métriques…</div>
      )}

      {/* Top processus CPU */}
      {metrics?.top_processes?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text3)', marginBottom: 4 }}>Top CPU</div>
          {metrics.top_processes.slice(0, 5).map((p, i) => (
            <div key={i} className="aegis-proc-row">
              <span className="aegis-proc-name">{p.name}</span>
              <span className="aegis-proc-cpu">{p.cpu?.toFixed(1)}%</span>
              <span className="aegis-proc-mem">{p.memory?.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Panneau 3 : Opérations Offensives ─────────────────────────────────────────
function PentestPanel() {
  const [jobs,   setJobs]   = useState([])
  const [target, setTarget] = useState('')
  const [running, setRunning] = useState(null)   // job_id en cours
  const [steps,  setSteps]  = useState([])
  const [log,    setLog]    = useState([])
  const esRef = useRef(null)
  const logRef = useRef(null)

  const loadJobs = () => {
    apiFetch('/pentest/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
  }

  useEffect(() => { loadJobs(); const t = setInterval(loadJobs, 10000); return () => clearInterval(t) }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  const launch = async () => {
    if (!target.trim()) return
    const res = await apiFetch('/pentest/run', {
      method: 'POST',
      body: JSON.stringify({ target: target.trim() }),
    })
    const { job_id } = await res.json()
    setRunning(job_id)
    setSteps([])
    setLog([`[${new Date().toLocaleTimeString()}] Opération lancée — cible : ${target} (job: ${job_id})`])

    esRef.current?.close()
    const token = auth.getToken()
    const url   = `/api/pentest/stream/${job_id}`
    const es    = new EventSource(url + (token ? `?token=${token}` : ''))
    esRef.current = es

    es.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] [${data.type}] ${
          data.data?.message || data.message || data.step?.name || ''
        }`])

        if (data.type === 'step_start') {
          setSteps(prev => {
            const idx = prev.findIndex(s => s.name === data.step?.name)
            const s = { ...data.step, status: 'running' }
            return idx >= 0 ? prev.map((x, i) => i === idx ? s : x) : [...prev, s]
          })
        }
        if (data.type === 'step_done') {
          setSteps(prev => prev.map(s => s.name === data.step?.name ? data.step : s))
        }
        if (data.type === 'progress') {
          setLog(prev => [...prev, `  → ${data.message}`])
        }
        if (data.type === 'complete') {
          setRunning(null)
          setLog(prev => [...prev, `✅ Opération terminée — ${data.data?.summary?.open_ports?.length || 0} ports, ${data.data?.cves?.length || 0} CVEs`])
          loadJobs()
          es.close()
        }
        if (data.type === 'error') {
          setLog(prev => [...prev, `❌ Erreur : ${data.message}`])
          setRunning(null)
          es.close()
        }
      } catch {}
    }
    es.onerror = () => { setRunning(null); es.close() }
  }

  const stop = () => {
    if (!running) return
    apiFetch(`/pentest/jobs/${running}/stop`, { method: 'POST' }).catch(() => {})
    esRef.current?.close()
    setRunning(null)
    setLog(prev => [...prev, '⏹ Opération interrompue'])
  }

  const STEP_ICON = { pending: '○', running: '⟳', done: '✓', error: '✗', skipped: '—' }
  const STEP_COLOR = { pending: 'var(--text3)', running: '#fbbf24', done: '#4ade80', error: '#ef4444', skipped: 'var(--text3)' }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">⚔️</span>
        <span>Opérations Offensives</span>
        {running && <span className="aegis-running-badge">EN COURS</span>}
      </div>

      {/* Lancer une opération */}
      <div className="aegis-launch-row">
        <input
          className="aegis-target-input"
          placeholder="Cible : IP ou domaine…"
          value={target}
          onChange={e => setTarget(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !running && launch()}
          disabled={!!running}
        />
        {running ? (
          <button className="aegis-stop-btn" onClick={stop}>⏹ Stop</button>
        ) : (
          <button className="aegis-launch-btn" onClick={launch} disabled={!target.trim()}>
            ▶ Lancer
          </button>
        )}
      </div>

      {/* Pipeline en cours */}
      {steps.length > 0 && (
        <div className="aegis-pipeline">
          {steps.map((s, i) => (
            <div key={i} className="aegis-step-row">
              <span style={{ color: STEP_COLOR[s.status], fontSize: '0.75rem', fontWeight: 700, minWidth: 14 }}>
                {STEP_ICON[s.status]}
              </span>
              <span className="aegis-step-name">{s.name}</span>
              {s.duration && <span className="aegis-step-dur">{s.duration}s</span>}
              {s.status === 'running' && <span className="aegis-spinner" />}
            </div>
          ))}
        </div>
      )}

      {/* Log temps réel */}
      {log.length > 0 && (
        <div className="aegis-log" ref={logRef}>
          {log.map((l, i) => <div key={i} className="aegis-log-line">{l}</div>)}
        </div>
      )}

      {/* Historique des jobs */}
      {jobs.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text3)', marginBottom: 4 }}>Historique</div>
          {jobs.slice(0, 5).map(j => (
            <div key={j.job_id} className="aegis-job-row">
              <span className={`aegis-job-status ${j.status}`}>{j.status}</span>
              <span className="aegis-job-target">{j.target}</span>
              <span className="aegis-job-ports">
                {j.summary?.open_ports?.length || 0} ports
              </span>
              <span className="aegis-job-cves">
                {j.summary?.cves_count || 0} CVEs
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Panneau 4 : Alertes & Détections ─────────────────────────────────────────
function AlertsPanel() {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('ALL')

  useEffect(() => {
    const load = () => {
      apiFetch('/soc/alerts?limit=50').then(r => r.json()).then(d => {
        setAlerts(d.alerts || [])
      }).catch(() => {})
    }
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const filtered = filter === 'ALL'
    ? alerts
    : alerts.filter(a => a.severity === filter)

  const counts = alerts.reduce((acc, a) => {
    acc[a.severity] = (acc[a.severity] || 0) + 1
    return acc
  }, {})

  const ack = async (id) => {
    await apiFetch(`/soc/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'ACK' }) }).catch(() => {})
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'ACK' } : a))
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🚨</span>
        <span>Alertes & Détections</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>
          {alerts.length} alertes
        </span>
      </div>

      {/* Compteurs par sévérité */}
      <div className="aegis-stats-row" style={{ flexWrap: 'wrap' }}>
        {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
          <button
            key={sev}
            className={`aegis-sev-filter ${filter === sev ? 'active' : ''}`}
            style={{ borderColor: SEV_COLOR[sev], color: filter === sev ? SEV_COLOR[sev] : 'var(--text3)' }}
            onClick={() => setFilter(filter === sev ? 'ALL' : sev)}
          >
            <span style={{ color: SEV_COLOR[sev] }}>{counts[sev] || 0}</span> {sev}
          </button>
        ))}
      </div>

      {/* Liste alertes */}
      <div className="aegis-feed">
        {filtered.length === 0 ? (
          <div className="aegis-feed-empty">Aucune alerte {filter !== 'ALL' ? filter : ''}</div>
        ) : filtered.slice(0, 30).map((a, i) => (
          <div key={i} className={`aegis-feed-row ${a.status === 'NEW' ? 'aegis-alert-new' : ''}`}>
            <SevBadge sev={a.severity} />
            <span className="aegis-feed-time">{a.timestamp?.slice(11, 19)}</span>
            <span className="aegis-feed-title" style={{ flex: 1 }}>{a.title}</span>
            {a.source_ip && <span className="aegis-feed-ip">{a.source_ip}</span>}
            {a.status === 'NEW' && (
              <button className="aegis-ack-btn" onClick={() => ack(a.id)}>ACK</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Vue principale AEGIS ──────────────────────────────────────────────────────
export default function AegisView() {
  return (
    <div className="aegis-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">⚡</span>
          <div>
            <div className="aegis-title">AEGIS COMMAND CENTER</div>
            <div className="aegis-subtitle">Surveillance · Arsenal · Mémoire · Alertes</div>
          </div>
        </div>
        <div className="aegis-header-right">
          <span className="aegis-live-dot" />
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>LIVE</span>
        </div>
      </div>

      <div className="aegis-grid">
        <NetworkPanel />
        <SystemPanel />
        <PentestPanel />
        <AlertsPanel />
      </div>
    </div>
  )
}
