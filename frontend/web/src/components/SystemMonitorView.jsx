/**
 * SystemMonitorView — Surveillance système temps réel (Sentinel)
 * Score santé · Métriques · Processus · Ports · Intégrité · Logs · Règles
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, auth } from '../utils/auth'

const SEV = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24',
  LOW: '#4ade80', INFO: '#38bdf8',
}

// ── Gauge circulaire ─────────────────────────────────────────────────────────
function Gauge({ value = 0, max = 100, color = '#38bdf8', label, size = 90 }) {
  const r = (size - 12) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.min(Math.max(value / max, 0), 1)
  const dash = pct * circ
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ffffff10" strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circ}`} strokeDashoffset={circ / 4}
          strokeLinecap="round" style={{ transition: 'stroke-dasharray 0.5s' }} />
        <text x={size / 2} y={size / 2 + 1} textAnchor="middle" dominantBaseline="middle"
          fill={color} fontSize={size * 0.2} fontWeight="800" fontFamily="monospace">
          {Math.round(value)}%
        </text>
      </svg>
      <div style={{ fontSize: '0.6rem', color: 'var(--text3)', letterSpacing: 1 }}>{label}</div>
    </div>
  )
}

// ── Health Score ─────────────────────────────────────────────────────────────
function HealthBadge({ score, status, label }) {
  const color = status === 'green' ? '#4ade80' : status === 'orange' ? '#fbbf24' : '#ef4444'
  const glow  = status === 'green' ? '#4ade8040' : status === 'orange' ? '#fbbf2440' : '#ef444440'
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      background: glow, border: `2px solid ${color}`, borderRadius: 16,
      padding: '20px 32px', minWidth: 160,
    }}>
      <div style={{ fontSize: '3rem', fontWeight: 900, color, lineHeight: 1, fontFamily: 'monospace' }}>
        {score ?? '—'}
      </div>
      <div style={{ fontSize: '0.75rem', color, fontWeight: 700, marginTop: 4 }}>{label ?? '—'}</div>
      <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginTop: 2 }}>HEALTH SCORE</div>
    </div>
  )
}

// ── Spark line ───────────────────────────────────────────────────────────────
function Spark({ data, color = '#38bdf8', width = 120, height = 32 }) {
  const w = typeof width === 'number' ? width : 200
  if (!data || data.length < 2) return <div style={{ width: w, height, background: '#ffffff06', borderRadius: 4 }} />
  const min = Math.min(...data)
  const max = Math.max(...data) || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = height - ((v - min) / (max - min + 0.001)) * height
    return `${x},${y}`
  }).join(' ')
  const lastX = w
  const lastY = height - ((data[data.length - 1] - min) / (max - min + 0.001)) * height
  return (
    <svg width={w} height={height} style={{ display: 'block', width: '100%' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r={2.5} fill={color} />
    </svg>
  )
}

// ── Event Row ────────────────────────────────────────────────────────────────
function EventRow({ evt, onResolve }) {
  const color = SEV[evt.severity] || '#38bdf8'
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '8px 10px', background: '#ffffff05', borderRadius: 8,
      borderLeft: `3px solid ${color}`, marginBottom: 4,
      opacity: evt.resolved ? 0.4 : 1,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '0.72rem', color, fontWeight: 700 }}>
          [{evt.severity}] {evt.category}
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text)', marginTop: 1, wordBreak: 'break-word' }}>
          {evt.title}
        </div>
        {evt.description && (
          <div style={{ fontSize: '0.62rem', color: 'var(--text3)', marginTop: 2 }}>
            {evt.description?.slice(0, 120)}
          </div>
        )}
        <div style={{ fontSize: '0.58rem', color: 'var(--text3)', marginTop: 2 }}>
          {evt.timestamp?.slice(11, 19)}
        </div>
      </div>
      {!evt.resolved && onResolve && (
        <button onClick={() => onResolve(evt.id)} style={{
          padding: '3px 8px', fontSize: '0.6rem', background: '#ffffff08',
          border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer',
        }}>✓</button>
      )}
    </div>
  )
}

// ── Composant principal ──────────────────────────────────────────────────────
const TABS = ['TABLEAU DE BORD', 'ÉVÉNEMENTS', 'PROCESSUS', 'PORTS & INTÉGRITÉ', 'RÈGLES', 'RAPPORT']

export default function SystemMonitorView() {
  const [tab, setTab] = useState(0)
  const [health, setHealth] = useState(null)
  const [events, setEvents] = useState([])
  const [processes, setProcesses] = useState([])
  const [portsData, setPortsData] = useState(null)
  const [integrity, setIntegrity] = useState(null)
  const [rules, setRules] = useState([])
  const [report, setReport] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [wsEvents, setWsEvents] = useState([])
  const [newRule, setNewRule] = useState('')
  const [whitelistEntry, setWhitelistEntry] = useState('')
  const [ruleNatural, setRuleNatural] = useState('')
  const wsRef = useRef(null)
  const feedRef = useRef(null)

  // ── WebSocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const token = auth.getToken()
    if (!token) return
    const WS_BASE = window.location.hostname
    const ws = new WebSocket(`ws://${WS_BASE}:8001/api/sentinel/ws?token=${token}`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)
        if (evt.type === 'ping') return
        if (evt.type === 'metrics') {
          setHealth(prev => prev ? { ...prev, snapshot: evt } : { score: evt.health_score, status: evt.health_score >= 80 ? 'green' : evt.health_score >= 50 ? 'orange' : 'red', label: '', snapshot: evt })
        } else if (evt.type === 'security_event') {
          setWsEvents(prev => [evt, ...prev].slice(0, 100))
          setEvents(prev => [{ ...evt, id: Date.now() + Math.random() }, ...prev].slice(0, 200))
        }
      } catch {}
    }
    ws.onerror = () => {}
    ws.onclose = () => {}

    return () => { try { ws.close() } catch {} }
  }, [])

  // ── Auto-scroll feed ──────────────────────────────────────────────────────
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = 0
  }, [wsEvents])

  // ── Chargement des données ─────────────────────────────────────────────────
  const loadHealth = useCallback(() => {
    apiFetch('/sentinel/health').then(r => r.json()).then(setHealth).catch(() => {})
  }, [])

  const loadEvents = useCallback(() => {
    apiFetch('/sentinel/events?limit=100').then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {})
  }, [])

  const loadProcesses = useCallback(() => {
    apiFetch('/sentinel/processes').then(r => r.json()).then(d => setProcesses(d.processes || [])).catch(() => {})
  }, [])

  const loadPorts = useCallback(() => {
    apiFetch('/sentinel/ports').then(r => r.json()).then(setPortsData).catch(() => {})
  }, [])

  const loadIntegrity = useCallback(() => {
    apiFetch('/sentinel/integrity').then(r => r.json()).then(setIntegrity).catch(() => {})
  }, [])

  const loadRules = useCallback(() => {
    apiFetch('/sentinel/rules').then(r => r.json()).then(d => setRules(d.rules || [])).catch(() => {})
  }, [])

  useEffect(() => {
    loadHealth()
    loadEvents()
    const t = setInterval(() => { loadHealth(); loadEvents() }, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (tab === 2) loadProcesses()
    if (tab === 3) { loadPorts(); loadIntegrity() }
    if (tab === 4) loadRules()
  }, [tab])

  // ── Actions ───────────────────────────────────────────────────────────────
  const resolveEvent = async (id) => {
    try {
      await apiFetch(`/sentinel/events/${id}/resolve`, { method: 'POST' })
      setEvents(prev => prev.map(e => e.id === id ? { ...e, resolved: true } : e))
    } catch {}
  }

  const addWhitelist = async () => {
    if (!whitelistEntry.trim()) return
    try {
      await apiFetch('/sentinel/network/whitelist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry: whitelistEntry.trim() }),
      })
      setWhitelistEntry('')
      alert(`✓ ${whitelistEntry} ajouté à la whitelist`)
    } catch {}
  }

  const createRuleNatural = async () => {
    if (!ruleNatural.trim()) return
    try {
      await apiFetch('/sentinel/rules/natural', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ruleNatural }),
      })
      setRuleNatural('')
      loadRules()
    } catch {}
  }

  const toggleRule = async (id) => {
    try {
      await apiFetch(`/sentinel/rules/${id}/toggle`, { method: 'PATCH' })
      loadRules()
    } catch {}
  }

  const deleteRule = async (id) => {
    try {
      await apiFetch(`/sentinel/rules/${id}`, { method: 'DELETE' })
      loadRules()
    } catch {}
  }

  const rebuildBaseline = async () => {
    if (!confirm('Recalculer toutes les baselines ? (processus, ports, fichiers)')) return
    await apiFetch('/sentinel/baseline/rebuild', { method: 'POST' }).catch(() => {})
    alert('✓ Baselines recalculées')
  }

  const rebuildIntegrity = async () => {
    await apiFetch('/sentinel/integrity/rebuild', { method: 'POST' }).catch(() => {})
    loadIntegrity()
  }

  const generateReport = async () => {
    setReportLoading(true)
    try {
      const r = await apiFetch('/sentinel/report?hours=24')
      const d = await r.json()
      setReport(d)
    } catch {}
    setReportLoading(false)
  }

  // ── Données dérivées ──────────────────────────────────────────────────────
  const snap = health?.snapshot || {}
  const score = health?.score ?? snap.health_score ?? 100
  const status = health?.status ?? (score >= 80 ? 'green' : score >= 50 ? 'orange' : 'red')
  const label = health?.label ?? (score >= 80 ? 'Bon' : score >= 50 ? 'Dégradé' : 'Critique')
  const history = health?.history || []
  const cpuHistory = history.map(m => m.cpu_pct)
  const ramHistory = history.map(m => m.ram_pct)
  const scoreHistory = history.map(m => m.health_score)

  const critCount = events.filter(e => e.severity === 'CRITICAL').length
  const highCount = events.filter(e => e.severity === 'HIGH').length
  const unresolvedCount = events.filter(e => !e.resolved).length

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <span style={{ fontSize: 28 }}>🔬</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            SENTINEL
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Surveillance système · Temps réel · Proactif
          </div>
        </div>
        <button onClick={rebuildBaseline} style={{
          marginLeft: 'auto', padding: '7px 16px', background: '#ffffff08',
          border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text3)',
          cursor: 'pointer', fontSize: '0.72rem',
        }}>⟳ Recalibrer Baselines</button>
        {/* Indicateur live */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ade80', display: 'inline-block', animation: 'neon-pulse 2s infinite' }} />
          <span style={{ fontSize: '0.62rem', color: '#4ade80' }}>LIVE</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20, overflowX: 'auto' }}>
        {TABS.map((t, i) => (
          <button key={i} onClick={() => setTab(i)} style={{
            padding: '7px 14px', background: tab === i ? 'var(--glow2)' : 'var(--glass)',
            border: `1px solid ${tab === i ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 8, color: tab === i ? 'var(--accent)' : 'var(--text3)',
            cursor: 'pointer', fontSize: '0.68rem', fontWeight: tab === i ? 700 : 400,
            whiteSpace: 'nowrap',
          }}>
            {t}
            {i === 1 && unresolvedCount > 0 && (
              <span style={{ marginLeft: 6, padding: '1px 5px', background: '#ef4444', borderRadius: 8, color: '#fff', fontSize: '0.6rem' }}>
                {unresolvedCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── TAB 0 : Tableau de bord ─────────────────────────────────────── */}
      {tab === 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr 280px', gap: 16 }}>
          {/* Health score */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
            <HealthBadge score={score} status={status} label={label} />
            <div style={{ width: '100%' }}>
              <div style={{ fontSize: '0.6rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 6 }}>TENDANCE 20 MIN</div>
              <Spark data={scoreHistory} color={status === 'green' ? '#4ade80' : status === 'orange' ? '#fbbf24' : '#ef4444'} width={150} height={40} />
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
              {critCount > 0 && <div style={{ fontSize: '0.65rem', color: '#ef4444', fontWeight: 700 }}>🔴 {critCount} CRITIQUE{critCount > 1 ? 'S' : ''}</div>}
              {highCount > 0 && <div style={{ fontSize: '0.65rem', color: '#f97316', fontWeight: 700 }}>🟠 {highCount} HIGH</div>}
              {critCount === 0 && highCount === 0 && <div style={{ fontSize: '0.65rem', color: '#4ade80' }}>✓ Aucune alerte critique</div>}
            </div>
          </div>

          {/* Gauges métriques */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 16 }}>MÉTRIQUES SYSTÈME</div>
            <div style={{ display: 'flex', gap: 24, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
              <Gauge value={snap.cpu_pct ?? 0}  max={100} color={snap.cpu_pct > 90 ? '#ef4444' : snap.cpu_pct > 70 ? '#fbbf24' : '#38bdf8'}  label="CPU" />
              <Gauge value={snap.ram_pct ?? 0}  max={100} color={snap.ram_pct > 90 ? '#ef4444' : snap.ram_pct > 70 ? '#fbbf24' : '#a78bfa'}  label="RAM" />
              <Gauge value={snap.disk_pct ?? 0} max={100} color={snap.disk_pct > 90 ? '#ef4444' : snap.disk_pct > 70 ? '#fbbf24' : '#4ade80'} label="DISQUE" />
              <Gauge value={snap.swap_pct ?? 0} max={100} color={snap.swap_pct > 80 ? '#ef4444' : snap.swap_pct > 50 ? '#fbbf24' : '#f97316'}  label="SWAP" />
              {snap.cpu_temp && <Gauge value={snap.cpu_temp ?? 0} max={100} color={snap.cpu_temp > 85 ? '#ef4444' : '#fbbf24'} label="TEMP°C" />}
            </div>
            {/* Historique CPU + RAM */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginBottom: 4 }}>CPU (20 dernières mesures)</div>
                <Spark data={cpuHistory} color="#38bdf8" width="100%" height={40} />
              </div>
              <div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginBottom: 4 }}>RAM (20 dernières mesures)</div>
                <Spark data={ramHistory} color="#a78bfa" width="100%" height={40} />
              </div>
            </div>
            {/* Stats détaillées */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 16 }}>
              {[
                { label: 'RAM utilisée', value: snap.ram_used_gb ? `${snap.ram_used_gb} GB` : '—' },
                { label: 'Disque libre', value: snap.disk_free_gb ? `${snap.disk_free_gb} GB` : '—' },
                { label: 'Processus', value: snap.process_count ?? '—' },
                { label: 'Ports ouverts', value: snap.open_ports ?? '—' },
                { label: 'Net envoyé', value: snap.net_sent_mb ? `${snap.net_sent_mb} MB` : '—' },
                { label: 'Net reçu', value: snap.net_recv_mb ? `${snap.net_recv_mb} MB` : '—' },
              ].map((s, i) => (
                <div key={i} style={{ background: '#ffffff05', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>{s.label}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text)', fontWeight: 700, fontFamily: 'monospace' }}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Live events feed */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 10 }}>
              FLUX TEMPS RÉEL
              <span style={{ marginLeft: 8, fontSize: '0.6rem', color: '#4ade80' }}>● WS</span>
            </div>
            <div ref={feedRef} style={{ height: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {wsEvents.length === 0
                ? <div style={{ color: 'var(--text3)', fontSize: '0.72rem', textAlign: 'center', paddingTop: 40 }}>En attente d'événements…</div>
                : wsEvents.map((evt, i) => (
                    <div key={i} style={{
                      padding: '6px 8px', background: '#ffffff06', borderRadius: 6,
                      borderLeft: `3px solid ${SEV[evt.severity] || '#38bdf8'}`,
                    }}>
                      <div style={{ fontSize: '0.58rem', color: SEV[evt.severity] || 'var(--text3)' }}>
                        {evt.severity} · {evt.category}
                      </div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text)', lineHeight: 1.4 }}>
                        {evt.title?.slice(0, 70)}
                      </div>
                    </div>
                  ))
              }
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 1 : Événements ──────────────────────────────────────────── */}
      {tab === 1 && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>
              {unresolvedCount} événement{unresolvedCount > 1 ? 's' : ''} non résolu{unresolvedCount > 1 ? 's' : ''}
            </div>
            <button onClick={loadEvents} style={{ padding: '5px 12px', fontSize: '0.68rem', background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer' }}>
              ↻ Rafraîchir
            </button>
            {/* Whitelist */}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <input value={whitelistEntry} onChange={e => setWhitelistEntry(e.target.value)}
                placeholder="IP ou IP:port à whitelister"
                style={{ padding: '5px 10px', background: 'var(--input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: '0.72rem', width: 200 }} />
              <button onClick={addWhitelist} style={{ padding: '5px 12px', background: 'var(--glow2)', border: '1px solid var(--border2)', borderRadius: 6, color: 'var(--accent)', cursor: 'pointer', fontSize: '0.72rem' }}>
                + Whitelist
              </button>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: '70vh', overflowY: 'auto' }}>
            {events.length === 0
              ? <div style={{ textAlign: 'center', color: '#4ade80', padding: 40 }}>✓ Aucun événement de sécurité</div>
              : events.map((evt, i) => (
                  <EventRow key={evt.id || i} evt={evt} onResolve={resolveEvent} />
                ))
            }
          </div>
        </div>
      )}

      {/* ── TAB 2 : Processus ───────────────────────────────────────────── */}
      {tab === 2 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>{processes.length} processus (top CPU)</div>
            <button onClick={loadProcesses} style={{ padding: '5px 12px', fontSize: '0.68rem', background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer' }}>↻</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
              <thead>
                <tr style={{ color: 'var(--text3)', fontSize: '0.62rem', letterSpacing: 1 }}>
                  {['PID', 'NOM', 'CPU%', 'MEM%', 'USER', 'STATUS', 'EXE'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 10px', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {processes.map((p, i) => (
                  <tr key={i} style={{ background: p.suspicious ? '#ef444410' : i % 2 === 0 ? '#ffffff03' : 'transparent' }}>
                    <td style={{ padding: '5px 10px', fontFamily: 'monospace', color: 'var(--text3)' }}>{p.pid}</td>
                    <td style={{ padding: '5px 10px', color: p.suspicious ? '#ef4444' : 'var(--text)', fontWeight: p.suspicious ? 700 : 400 }}>
                      {p.suspicious && '⚠️ '}{p.name}
                    </td>
                    <td style={{ padding: '5px 10px', color: p.cpu_pct > 80 ? '#ef4444' : p.cpu_pct > 50 ? '#fbbf24' : 'var(--text)' }}>
                      {p.cpu_pct}%
                    </td>
                    <td style={{ padding: '5px 10px', color: 'var(--text)' }}>{p.mem_pct}%</td>
                    <td style={{ padding: '5px 10px', color: 'var(--text3)' }}>{p.user}</td>
                    <td style={{ padding: '5px 10px', color: p.status === 'running' ? '#4ade80' : 'var(--text3)' }}>{p.status}</td>
                    <td style={{ padding: '5px 10px', fontFamily: 'monospace', fontSize: '0.6rem', color: 'var(--text3)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.exe}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── TAB 3 : Ports & Intégrité ───────────────────────────────────── */}
      {tab === 3 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Ports */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>PORTS & SERVICES</div>
              <button onClick={loadPorts} style={{ padding: '3px 10px', fontSize: '0.62rem', background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer' }}>↻</button>
            </div>
            {portsData?.services?.map((svc, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 10px', background: '#ffffff05', borderRadius: 8, marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text)', fontWeight: 600 }}>{svc.name}</div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>:{svc.port}</div>
                </div>
                <div style={{ color: svc.running ? '#4ade80' : '#ef4444', fontWeight: 700, fontSize: '0.72rem' }}>
                  {svc.running ? '● ACTIF' : '○ ARRÊTÉ'}
                </div>
              </div>
            ))}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: '0.6rem', color: 'var(--text3)', marginBottom: 8 }}>PORTS EN ÉCOUTE ({portsData?.count ?? 0})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(portsData?.listening_ports || []).map(p => (
                  <span key={p} style={{ padding: '2px 8px', background: '#ffffff08', borderRadius: 4, fontSize: '0.65rem', fontFamily: 'monospace', color: 'var(--text)' }}>{p}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Intégrité */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>INTÉGRITÉ FICHIERS</div>
              <button onClick={rebuildIntegrity} style={{ padding: '3px 10px', fontSize: '0.62rem', background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', cursor: 'pointer' }}>
                ↻ Recalculer
              </button>
            </div>
            {integrity && (
              <>
                <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                  <div style={{ color: '#4ade80', fontSize: '0.72rem' }}>✓ {integrity.ok} OK</div>
                  {integrity.modified > 0 && <div style={{ color: '#ef4444', fontSize: '0.72rem' }}>⚠ {integrity.modified} MODIFIÉS</div>}
                  {integrity.missing > 0 && <div style={{ color: '#f97316', fontSize: '0.72rem' }}>✗ {integrity.missing} MANQUANTS</div>}
                </div>
                <div style={{ maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {integrity.files?.map((f, i) => (
                    <div key={i} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '5px 8px', background: '#ffffff04', borderRadius: 6,
                      borderLeft: `3px solid ${f.ok ? '#4ade80' : f.modified ? '#ef4444' : '#f97316'}`,
                    }}>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text3)', fontFamily: 'monospace' }}>{f.name}</div>
                      <div style={{ fontSize: '0.6rem', color: f.ok ? '#4ade80' : f.modified ? '#ef4444' : '#f97316', fontWeight: 700 }}>
                        {f.ok ? 'OK' : f.modified ? 'MODIFIÉ' : 'MANQUANT'}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 4 : Règles ──────────────────────────────────────────────── */}
      {tab === 4 && (
        <div>
          {/* Créer règle en langage naturel */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border2)', borderRadius: 12, padding: 16, marginBottom: 20 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--accent)', letterSpacing: 1, marginBottom: 10 }}>NOUVELLE RÈGLE — LANGAGE NATUREL</div>
            <div style={{ display: 'flex', gap: 10 }}>
              <input value={ruleNatural} onChange={e => setRuleNatural(e.target.value)}
                placeholder="Ex: surveille le dossier /home/kali/projects | alerte si cpu dépasse 85% | alerte si le processus nginx s'arrête"
                onKeyDown={e => e.key === 'Enter' && createRuleNatural()}
                style={{ flex: 1, padding: '8px 12px', background: 'var(--input)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: '0.75rem' }} />
              <button onClick={createRuleNatural} style={{ padding: '8px 18px', background: 'var(--glow2)', border: '1px solid var(--accent)', borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontWeight: 700 }}>
                + Créer
              </button>
            </div>
          </div>

          {/* Liste des règles */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rules.length === 0
              ? <div style={{ textAlign: 'center', color: 'var(--text3)', padding: 40 }}>Aucune règle personnalisée</div>
              : rules.map(rule => (
                  <div key={rule.id} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 14px', background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 10,
                    opacity: rule.enabled ? 1 : 0.4,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text)', fontWeight: 600 }}>{rule.name}</div>
                      <div style={{ fontSize: '0.62rem', color: 'var(--text3)', marginTop: 2 }}>
                        Type: {rule.rule_type} · Action: {rule.action}
                      </div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text3)', fontFamily: 'monospace', marginTop: 2 }}>
                        {JSON.stringify(rule.condition)}
                      </div>
                    </div>
                    <button onClick={() => toggleRule(rule.id)} style={{ padding: '4px 10px', fontSize: '0.65rem', background: rule.enabled ? '#4ade8020' : '#ffffff08', border: `1px solid ${rule.enabled ? '#4ade80' : 'var(--border)'}`, borderRadius: 6, color: rule.enabled ? '#4ade80' : 'var(--text3)', cursor: 'pointer' }}>
                      {rule.enabled ? 'ON' : 'OFF'}
                    </button>
                    <button onClick={() => deleteRule(rule.id)} style={{ padding: '4px 8px', fontSize: '0.65rem', background: '#ef444410', border: '1px solid #ef4444', borderRadius: 6, color: '#ef4444', cursor: 'pointer' }}>✕</button>
                  </div>
                ))
            }
          </div>
        </div>
      )}

      {/* ── TAB 5 : Rapport ─────────────────────────────────────────────── */}
      {tab === 5 && (
        <div>
          <button onClick={generateReport} disabled={reportLoading} style={{
            marginBottom: 20, padding: '10px 24px', background: 'var(--glow2)',
            border: '1px solid var(--accent)', borderRadius: 10, color: 'var(--accent)',
            cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem',
          }}>
            {reportLoading ? '⟳ Génération du rapport…' : '📊 Générer Rapport de Sécurité (24h)'}
          </button>

          {report && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {/* Stats */}
              <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>STATISTIQUES 24H</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {[
                    { label: 'Total événements', value: report.total_events },
                    { label: 'CPU moyen', value: `${report.avg_cpu_pct}%` },
                    { label: 'RAM moyenne', value: `${report.avg_ram_pct}%` },
                    { label: 'Score santé moy.', value: `${report.avg_health_score}/100` },
                  ].map((s, i) => (
                    <div key={i} style={{ background: '#ffffff06', borderRadius: 8, padding: '10px 12px' }}>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>{s.label}</div>
                      <div style={{ fontSize: '1rem', color: 'var(--accent)', fontWeight: 800, fontFamily: 'monospace' }}>{s.value}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 12 }}>
                  {Object.entries(report.stats || {}).map(([sev, count]) => (
                    <div key={sev} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ color: SEV[sev], fontSize: '0.7rem', fontWeight: 700 }}>{sev}</span>
                      <span style={{ color: SEV[sev], fontSize: '0.7rem' }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Analyse Claude */}
              <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--accent)', letterSpacing: 1, marginBottom: 12 }}>ANALYSE CLAUDE</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                  {report.analysis}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
