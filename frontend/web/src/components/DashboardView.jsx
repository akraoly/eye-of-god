/**
 * DashboardView — Cockpit principal de L'Œil de Dieu
 * 6 widgets temps réel : Système · AEGIS · Agents · Mémoire · Vie · Journal
 */
import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { apiFetch } from '../utils/auth'
import { notify } from '../stores/notificationStore'

const api = (path) => apiFetch(path).then(r => r.json()).catch(() => null)

// ── Widget shell ──────────────────────────────────────────────────────────────
function Widget({ title, icon, color = 'var(--accent)', children, accent, style }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{
        background: 'var(--glass)', border: `1px solid ${accent || 'var(--border)'}`,
        borderRadius: 14, padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: 10,
        ...style,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: '1rem' }}>{icon}</span>
        <span style={{ fontSize: '0.65rem', fontWeight: 800, color, letterSpacing: 2 }}>{title}</span>
        <div style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: color, opacity: 0.7, animation: 'neon-pulse 2s infinite' }} />
      </div>
      {children}
    </motion.div>
  )
}

// ── Mini barre de progression ──────────────────────────────────────────────────
function Bar({ value, max = 100, color = '#38bdf8', label }) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100)
  const c = pct > 85 ? '#ef4444' : pct > 65 ? '#fbbf24' : color
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>{label}</span>
        <span style={{ fontSize: '0.62rem', color: c, fontWeight: 700, fontFamily: 'monospace' }}>{Math.round(value)}%</span>
      </div>
      <div style={{ height: 4, background: '#ffffff10', borderRadius: 99 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: c, borderRadius: 99, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  )
}

// ── Widget Système ─────────────────────────────────────────────────────────────
function SystemWidget() {
  const [data, setData] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    const load = async () => {
      const d = await api('/sentinel/health')
      if (!d) return
      setData(d)
      setHistory(prev => [...prev, {
        t: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
        cpu: d.snapshot?.cpu_pct ?? 0,
        ram: d.snapshot?.ram_pct ?? 0,
      }].slice(-20))

      if (d.score < 50) notify('critical', 'Santé système critique', `Score: ${d.score}/100`, { source: 'Sentinel', dedupeKey: 'sentinel-health-critical' })
      else if (d.score < 80) notify('warning', 'Santé système dégradée', `Score: ${d.score}/100`, { source: 'Sentinel', dedupeKey: 'sentinel-health-warning' })
    }
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  const snap = data?.snapshot || {}
  const score = data?.score ?? 100
  const status = data?.status ?? 'green'
  const scoreColor = status === 'green' ? '#4ade80' : status === 'orange' ? '#fbbf24' : '#ef4444'

  return (
    <Widget title="SYSTÈME" icon="💻" color={scoreColor} accent={`${scoreColor}50`}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '2.2rem', fontWeight: 900, color: scoreColor, lineHeight: 1, fontFamily: 'monospace' }}>{score}</div>
          <div style={{ fontSize: '0.55rem', color: scoreColor }}>HEALTH</div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Bar value={snap.cpu_pct ?? 0} label="CPU" color="#38bdf8" />
          <Bar value={snap.ram_pct ?? 0} label="RAM" color="#a78bfa" />
          <Bar value={snap.disk_pct ?? 0} label="Disque" color="#4ade80" />
        </div>
      </div>
      {history.length > 2 && (
        <div style={{ height: 40 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <Area type="monotone" dataKey="cpu" stroke="#38bdf8" fill="#38bdf810" strokeWidth={1.5} dot={false} />
              <Area type="monotone" dataKey="ram" stroke="#a78bfa" fill="#a78bfa10" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      {snap.ram_used_gb && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            { l: 'RAM', v: `${snap.ram_used_gb} GB` },
            { l: 'Libre', v: `${snap.disk_free_gb ?? '?'} GB` },
            { l: 'Procs', v: snap.process_count ?? '?' },
          ].map((s, i) => (
            <div key={i} style={{ background: '#ffffff06', borderRadius: 6, padding: '4px 8px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.55rem', color: 'var(--text3)' }}>{s.l}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text)', fontWeight: 700, fontFamily: 'monospace' }}>{s.v}</div>
            </div>
          ))}
        </div>
      )}
    </Widget>
  )
}

// ── Widget AEGIS ──────────────────────────────────────────────────────────────
function AegisWidget({ onNav }) {
  const [stats, setStats] = useState(null)
  const [alerts, setAlerts] = useState([])

  useEffect(() => {
    const load = async () => {
      const [s, a] = await Promise.all([
        api('/soc/alerts/stats'),
        api('/soc/alerts?limit=3&unread_only=true'),
      ])
      if (s) setStats(s)
      if (a) {
        setAlerts(a.alerts || a || [])
        const crits = (a.alerts || a || []).filter(al => al.severity === 'critical' || al.severity === 'CRITICAL')
        if (crits.length > 0) notify('critical', `${crits.length} alerte(s) AEGIS critique(s)`, crits[0]?.title || '', { source: 'AEGIS', persistent: true, dedupeKey: 'aegis-crits-widget' })
      }
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  const SEV_COLOR = { critical: '#ef4444', high: '#f97316', medium: '#fbbf24', low: '#4ade80', CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24', LOW: '#4ade80' }

  return (
    <Widget title="AEGIS — VEILLE" icon="🔴" color="#ef4444" accent="#ef444430">
      <div style={{ display: 'flex', gap: 10 }}>
        {[
          { l: 'Critiques', v: stats?.by_severity?.critical ?? stats?.critical ?? '—', c: '#ef4444' },
          { l: 'Non lus', v: stats?.unread ?? '—', c: '#fbbf24' },
          { l: 'Total 24h', v: stats?.total_24h ?? stats?.total ?? '—', c: '#38bdf8' },
        ].map((s, i) => (
          <div key={i} style={{ flex: 1, background: `${s.c}10`, border: `1px solid ${s.c}40`, borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
            <div style={{ fontSize: '1.3rem', fontWeight: 900, color: s.c, fontFamily: 'monospace' }}>{s.v}</div>
            <div style={{ fontSize: '0.55rem', color: s.c, opacity: 0.7 }}>{s.l}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {alerts.length === 0
          ? <div style={{ fontSize: '0.7rem', color: '#4ade80', textAlign: 'center', padding: 8 }}>✓ Aucune alerte non lue</div>
          : alerts.slice(0, 3).map((a, i) => (
              <div key={i} style={{
                display: 'flex', gap: 8, padding: '5px 8px', background: '#ffffff05',
                borderRadius: 6, borderLeft: `3px solid ${SEV_COLOR[a.severity] || '#38bdf8'}`,
                cursor: 'pointer',
              }} onClick={() => onNav('soc')}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.65rem', color: SEV_COLOR[a.severity] || 'var(--text)', fontWeight: 600 }}>{a.severity?.toUpperCase()}</div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</div>
                </div>
              </div>
            ))
        }
      </div>
      <button onClick={() => onNav('soc')} style={{ width: '100%', padding: '6px', background: '#ef444415', border: '1px solid #ef444440', borderRadius: 7, color: '#ef4444', cursor: 'pointer', fontSize: '0.68rem' }}>
        Ouvrir AEGIS →
      </button>
    </Widget>
  )
}

// ── Widget Agents ─────────────────────────────────────────────────────────────
function AgentsWidget({ onNav }) {
  const [agents, setAgents] = useState([])
  const [alerts, setAlerts] = useState([])

  useEffect(() => {
    const load = async () => {
      const [ag, al] = await Promise.all([
        api('/system/agents'),
        api('/autonomy/alerts?limit=5'),
      ])
      if (ag) setAgents(ag.agents || ag || [])
      if (al) setAlerts(al.alerts || al || [])
    }
    load()
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [])

  const AGENT_ICONS = { CyberAgent: '🔴', CodeAgent: '🛠️', SystemAgent: '💻', LifeAgent: '🎯', MemoryAgent: '🧠', ResearchAgent: '🔍' }

  return (
    <Widget title="AGENTS" icon="🤖" color="#a78bfa" accent="#a78bfa30">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {agents.length === 0 ? (
          ['CyberAgent','CodeAgent','SystemAgent','MemoryAgent'].map(n => (
            <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 8px', background: '#ffffff06', borderRadius: 6 }}>
              <span style={{ fontSize: '0.7rem' }}>{AGENT_ICONS[n] || '🤖'}</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>{n}</span>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#4ade80', display: 'inline-block' }} />
            </div>
          ))
        ) : agents.map((a, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 8px', background: '#ffffff06', borderRadius: 6 }}>
            <span style={{ fontSize: '0.7rem' }}>{AGENT_ICONS[a.name] || '🤖'}</span>
            <span style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>{a.name}</span>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: a.active ? '#4ade80' : '#ef4444', display: 'inline-block' }} />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ fontSize: '0.6rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 2 }}>DERNIÈRES ACTIONS</div>
        {alerts.slice(0, 3).map((al, i) => (
          <div key={i} style={{ fontSize: '0.65rem', color: 'var(--text)', display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ color: 'var(--text3)', fontFamily: 'monospace', fontSize: '0.58rem' }}>{al.timestamp?.slice(11, 16) || '—'}</span>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{al.message || al.title || al.body || '—'}</span>
          </div>
        ))}
        {alerts.length === 0 && <div style={{ fontSize: '0.68rem', color: 'var(--text3)', textAlign: 'center' }}>En attente d'actions…</div>}
      </div>
      <button onClick={() => onNav('autonomy')} style={{ width: '100%', padding: '6px', background: '#a78bfa15', border: '1px solid #a78bfa40', borderRadius: 7, color: '#a78bfa', cursor: 'pointer', fontSize: '0.68rem' }}>
        Gérer les agents →
      </button>
    </Widget>
  )
}

// ── Widget Mémoire ────────────────────────────────────────────────────────────
function MemoryWidget({ onNav }) {
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])

  useEffect(() => {
    const load = async () => {
      const [s, r] = await Promise.all([
        api('/memory/vector/stats'),
        api('/memory/search?q=recent&limit=3'),
      ])
      if (s) setStats(s)
      if (r) setRecent(r.results || r.memories || r || [])
    }
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  return (
    <Widget title="MÉMOIRE" icon="🧠" color="#4ade80" accent="#4ade8030">
      <div style={{ display: 'flex', gap: 10 }}>
        {[
          { l: 'Vecteurs', v: stats?.total_vectors ?? stats?.count ?? '—', c: '#4ade80' },
          { l: 'Taille DB', v: stats?.db_size_mb ? `${stats.db_size_mb} MB` : '—', c: '#38bdf8' },
          { l: 'Catégories', v: stats?.categories ?? '—', c: '#fbbf24' },
        ].map((s, i) => (
          <div key={i} style={{ flex: 1, background: `${s.c}10`, border: `1px solid ${s.c}40`, borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: s.c, fontFamily: 'monospace' }}>{s.v}</div>
            <div style={{ fontSize: '0.55rem', color: s.c, opacity: 0.7 }}>{s.l}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontSize: '0.6rem', color: 'var(--text3)', letterSpacing: 1 }}>DERNIERS SOUVENIRS</div>
        {recent.slice(0, 3).map((m, i) => (
          <div key={i} style={{ padding: '5px 8px', background: '#ffffff05', borderRadius: 6, borderLeft: '2px solid #4ade8050' }}>
            <div style={{ fontSize: '0.62rem', color: '#4ade80', fontWeight: 600 }}>{m.category || m.type || 'général'}</div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.content || m.value || m.text || '—'}</div>
          </div>
        ))}
        {recent.length === 0 && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', textAlign: 'center' }}>Aucun souvenir récent</div>}
      </div>
      <button onClick={() => onNav('memory')} style={{ width: '100%', padding: '6px', background: '#4ade8015', border: '1px solid #4ade8040', borderRadius: 7, color: '#4ade80', cursor: 'pointer', fontSize: '0.68rem' }}>
        Explorer la mémoire →
      </button>
    </Widget>
  )
}

// ── Widget Vie ────────────────────────────────────────────────────────────────
function LifeWidget({ onNav }) {
  const [dash, setDash] = useState(null)

  useEffect(() => {
    const load = async () => { const d = await api('/life/dashboard'); if (d) setDash(d) }
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  const goals  = dash?.goals?.active?.slice(0, 3) || []
  const habits = dash?.habits?.active?.slice(0, 3) || []
  const done   = dash?.goals?.done || 0
  const total  = dash?.goals?.total || 0

  return (
    <Widget title="VIE PERSONNELLE" icon="🎯" color="#fbbf24" accent="#fbbf2430">
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ flex: 1, background: '#fbbf2410', border: '1px solid #fbbf2440', borderRadius: 8, padding: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#fbbf24', fontFamily: 'monospace' }}>{done}/{total}</div>
          <div style={{ fontSize: '0.55rem', color: '#fbbf24', opacity: 0.7 }}>OBJECTIFS</div>
        </div>
        <div style={{ flex: 1, background: '#f9731610', border: '1px solid #f9731640', borderRadius: 8, padding: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#f97316', fontFamily: 'monospace' }}>{habits.length}</div>
          <div style={{ fontSize: '0.55rem', color: '#f97316', opacity: 0.7 }}>HABITUDES</div>
        </div>
        <div style={{ flex: 1, background: '#4ade8010', border: '1px solid #4ade8040', borderRadius: 8, padding: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#4ade80', fontFamily: 'monospace' }}>
            {dash?.habits?.top_streak?.streak ?? '—'}
          </div>
          <div style={{ fontSize: '0.55rem', color: '#4ade80', opacity: 0.7 }}>STREAK 🔥</div>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {goals.map((g, i) => {
          const PCOL = { 1: '#ef4444', 2: '#f97316', 3: '#fbbf24', 4: '#4ade80' }
          const c = PCOL[g.priority] || '#38bdf8'
          const pct = g.progress ?? 0
          return (
            <div key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ fontSize: '0.65rem', color: c }}>{g.title?.slice(0, 30)}</span>
                <span style={{ fontSize: '0.62rem', color: c, fontFamily: 'monospace' }}>{pct}%</span>
              </div>
              <div style={{ height: 3, background: '#ffffff10', borderRadius: 99 }}>
                <div style={{ height: '100%', width: `${pct}%`, background: c, borderRadius: 99, transition: 'width 0.5s' }} />
              </div>
            </div>
          )
        })}
        {goals.length === 0 && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', textAlign: 'center' }}>Aucun objectif actif</div>}
      </div>
      <button onClick={() => onNav('life')} style={{ width: '100%', padding: '6px', background: '#fbbf2415', border: '1px solid #fbbf2440', borderRadius: 7, color: '#fbbf24', cursor: 'pointer', fontSize: '0.68rem' }}>
        Ouvrir Vie Personnelle →
      </button>
    </Widget>
  )
}

// ── Widget Journal d'actions ──────────────────────────────────────────────────
function ActionLogWidget() {
  const [events, setEvents] = useState([])

  useEffect(() => {
    const load = async () => {
      const [se, au] = await Promise.all([
        api('/sentinel/events?limit=6&hours=24'),
        api('/autonomy/alerts?limit=4'),
      ])
      const sentinelEvts = (se?.events || []).map(e => ({ ...e, _source: 'sentinel' }))
      const autoEvts = (au?.alerts || au || []).slice(0, 4).map(e => ({ ...e, _source: 'auto', title: e.message || e.title || '—' }))
      const merged = [...sentinelEvts, ...autoEvts]
        .sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
        .slice(0, 10)
      setEvents(merged)
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const SEV_COL = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24', LOW: '#4ade80', INFO: '#38bdf8' }

  return (
    <Widget title="JOURNAL TEMPS RÉEL" icon="📋" color="#38bdf8" style={{ gridColumn: 'span 3' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 220, overflowY: 'auto' }}>
        {events.length === 0
          ? <div style={{ textAlign: 'center', color: 'var(--text3)', fontSize: '0.72rem', padding: 20 }}>Aucune action récente…</div>
          : events.map((e, i) => {
              const c = SEV_COL[e.severity] || '#38bdf8'
              const agent = e._source === 'auto' ? (e.agent || 'AutoAgent') : (e.category || 'Sentinel')
              return (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '50px 80px 1fr auto',
                  gap: 8, padding: '5px 8px', background: '#ffffff04', borderRadius: 6,
                  borderLeft: `2px solid ${c}`,
                }}>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text3)', fontFamily: 'monospace', alignSelf: 'center' }}>
                    {e.timestamp?.slice(11, 16) || e.ts?.slice(11, 16) || '—'}
                  </span>
                  <span style={{ fontSize: '0.6rem', color: c, fontWeight: 600, alignSelf: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {agent}
                  </span>
                  <span style={{ fontSize: '0.67rem', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', alignSelf: 'center' }}>
                    {e.title}
                  </span>
                  <span style={{ fontSize: '0.58rem', color: c, fontWeight: 700, alignSelf: 'center' }}>
                    {e.severity || '—'}
                  </span>
                </div>
              )
            })
        }
      </div>
    </Widget>
  )
}

// ── Widget Réseau WiFi / Bluetooth ────────────────────────────────────────────
function SignalDots({ pct }) {
  const bars = pct >= 75 ? 4 : pct >= 50 ? 3 : pct >= 25 ? 2 : 1
  const col  = pct >= 75 ? '#4ade80' : pct >= 50 ? '#44aaff' : pct >= 25 ? '#fbbf24' : '#f97316'
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'flex-end' }}>
      {[1,2,3,4].map(i => (
        <span key={i} style={{ width: 3, height: 3 + i * 2, borderRadius: 1, display: 'inline-block',
          background: i <= bars ? col : '#333' }} />
      ))}
    </span>
  )
}

function NetworkWidget({ onNav }) {
  const [tab,        setTab]        = useState('wifi')
  const [status,     setStatus]     = useState(null)
  const [networks,   setNetworks]   = useState([])
  const [btDevices,  setBtDevices]  = useState([])
  const [hasBt,      setHasBt]      = useState(null)
  const [hasWifi,    setHasWifi]    = useState(null)
  const [demoWifi,   setDemoWifi]   = useState(false)
  const [demoBt,     setDemoBt]     = useState(false)
  const [scanning,   setScanning]   = useState(false)
  const [btScanning, setBtScanning] = useState(false)
  const [modal,      setModal]      = useState(null)
  const [pwd,        setPwd]        = useState('')
  const [showPwd,    setShowPwd]    = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [toast,      setToast]      = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 4000)
  }

  const loadStatus = useCallback(async () => {
    const d = await api('/wifi/system-status')
    if (!d) return
    setStatus(d)
    if (d.has_wifi_hw !== undefined) setHasWifi(d.has_wifi_hw)
  }, [])

  const scanWifi = useCallback(async () => {
    setScanning(true)
    const d = await api('/wifi/available')
    if (d) {
      setNetworks(d.networks || [])
      if (d.has_wifi_hw !== undefined) setHasWifi(d.has_wifi_hw)
      setDemoWifi(!!d.demo)
    }
    setScanning(false)
  }, [])

  const scanBt = useCallback(async () => {
    setBtScanning(true)
    setBtDevices([])
    const d = await apiFetch('/wifi/bluetooth/scan', { method: 'POST' }).then(r => r.json()).catch(() => null)
    if (d) {
      setHasBt(d.has_bluetooth_hw)
      setDemoBt(!!d.demo)
      setBtDevices(d.devices || [])
      if (d.devices?.length) showToast(`${d.devices.length} appareil(s) BT trouvé(s)`)
    }
    setBtScanning(false)
  }, [])

  useEffect(() => {
    loadStatus()
    scanWifi()
    apiFetch('/wifi/bluetooth/status').then(r => r.json()).then(d => { setHasBt(d.has_bluetooth_hw); if (!d.has_bluetooth_hw) setDemoBt(true) }).catch(() => {})
    const t = setInterval(loadStatus, 30000)
    return () => clearInterval(t)
  }, [])

  async function connect() {
    if (!modal) return
    setConnecting(true)
    const d = await apiFetch('/wifi/system-connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid: modal.ssid, password: pwd }),
    }).then(r => r.json()).catch(() => null)
    setConnecting(false)
    if (d?.status === 'connected') {
      showToast(`✅ Connecté à ${modal.ssid}${d.local_ip ? ' — ' + d.local_ip : ''}`)
      setModal(null)
      await loadStatus()
      await scanWifi()
    } else {
      showToast(d?.error || 'Connexion échouée', false)
    }
  }

  async function disconnect() {
    const d = await apiFetch('/wifi/system-disconnect', { method: 'POST' }).then(r => r.json()).catch(() => null)
    if (d?.status === 'disconnected') { showToast('Déconnecté'); loadStatus(); scanWifi() }
    else showToast(d?.error || 'Erreur déconnexion', false)
  }

  const ip = status?.local_ip || (status?.server_ips?.[0]?.ip)
  const connected = status?.connected
  const SEC = { WPA3: '#4ade80', WPA2: '#44aaff', WEP: '#f97316', OPEN: '#fbbf24' }

  return (
    <Widget title="RÉSEAU" icon="📶" color="#38bdf8" accent="#38bdf830">
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 16, right: 72, zIndex: 9999,
          padding: '8px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
          background: toast.ok ? '#001800' : '#1a0000',
          border: `1px solid ${toast.ok ? '#4ade8077' : '#ef444477'}`,
          color: toast.ok ? '#4ade80' : '#ef4444',
          boxShadow: '0 4px 20px #0008',
        }}>{toast.msg}</div>
      )}

      {/* Statut actuel */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: '#ffffff06', borderRadius: 8 }}>
        <span style={{ fontSize: 16 }}>{connected ? '🟢' : hasWifi === false ? '⚠️' : '⭕'}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          {connected
            ? <><span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4ade80' }}>{status.ssid}</span>
                <span style={{ fontSize: '0.6rem', color: '#44aaff', marginLeft: 8, fontFamily: 'monospace' }}>{status.local_ip}</span></>
            : <span style={{ fontSize: '0.72rem', color: hasWifi === false ? '#f97316' : 'var(--text3)' }}>
                {hasWifi === false ? 'Pas d\'adaptateur WiFi' : 'Non connecté'}
              </span>
          }
          {ip && !connected && <div style={{ fontSize: '0.58rem', color: '#44aaff', fontFamily: 'monospace' }}>Serveur : {ip}:8001</div>}
        </div>
        {connected && (
          <button onClick={disconnect} style={{ padding: '3px 8px', background: 'transparent', border: '1px solid #ef444433', color: '#ef4444', borderRadius: 5, cursor: 'pointer', fontSize: '0.6rem' }}>
            Déco
          </button>
        )}
      </div>

      {/* Onglets */}
      <div style={{ display: 'flex', gap: 4 }}>
        {[['wifi','📶 WiFi'], ['bt','🔵 BT']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            flex: 1, padding: '5px 0', borderRadius: 6, cursor: 'pointer', fontSize: '0.65rem', fontWeight: tab === id ? 700 : 400,
            background: tab === id ? '#38bdf820' : 'transparent',
            border: `1px solid ${tab === id ? '#38bdf840' : '#ffffff10'}`,
            color: tab === id ? '#38bdf8' : 'var(--text3)',
          }}>{label}</button>
        ))}
      </div>

      {/* Panel WiFi */}
      {tab === 'wifi' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: '0.6rem', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1 }}>
              {networks.length > 0 ? `${networks.length} réseau(x)` : 'Réseaux à proximité'}
            </span>
            <button onClick={scanWifi} disabled={scanning} style={{ padding: '2px 8px', background: '#38bdf815', border: '1px solid #38bdf830', color: '#38bdf8', borderRadius: 5, cursor: 'pointer', fontSize: '0.6rem' }}>
              {scanning ? '⏳' : '🔄 Scan'}
            </button>
          </div>
          {demoWifi && <div style={{ fontSize: '0.55rem', color: '#f59e0b', background: '#1a1000', borderRadius: 5, padding: '3px 8px', marginBottom: 5 }}>🔮 MODE DÉMO — réseaux simulés</div>}
          {hasWifi === false && !demoWifi
            ? <div style={{ fontSize: '0.65rem', color: '#f97316', padding: '8px 10px', background: '#1a0f00', borderRadius: 6, lineHeight: 1.6 }}>
                Pas d'adaptateur WiFi physique<br />
                <span style={{ color: '#664422', fontSize: '0.58rem' }}>→ Branchez un dongle USB WiFi</span>
              </div>
            : networks.length === 0
              ? <div style={{ textAlign: 'center', color: 'var(--text3)', fontSize: '0.68rem', padding: '10px 0' }}>
                  {scanning ? 'Scan…' : 'Aucun réseau — clique Scan'}
                </div>
              : <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 140, overflowY: 'auto' }}>
                  {networks.slice(0, 6).map((n, i) => (
                    <div key={n.bssid || i}
                      onClick={() => !n.active && setModal({ ssid: n.ssid, secured: n.secured })}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6,
                        background: n.active ? '#4ade8010' : '#ffffff04',
                        border: `1px solid ${n.active ? '#4ade8030' : '#ffffff08'}`,
                        cursor: n.active ? 'default' : 'pointer',
                      }}>
                      <SignalDots pct={n.signal} />
                      <span style={{ flex: 1, fontSize: '0.68rem', color: n.active ? '#4ade80' : 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: n.active ? 700 : 400 }}>
                        {n.ssid || <em style={{ color: '#444' }}>Caché</em>}
                      </span>
                      {n.active && <span style={{ fontSize: '0.55rem', color: '#4ade80', background: '#4ade8020', borderRadius: 4, padding: '1px 5px' }}>✓</span>}
                      <span style={{ fontSize: '0.58rem', color: SEC[n.security] || '#888' }}>{n.secured ? '🔒' : '🔓'}</span>
                    </div>
                  ))}
                </div>
          }
        </div>
      )}

      {/* Panel Bluetooth */}
      {tab === 'bt' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: '0.6rem', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1 }}>
              {btDevices.length > 0 ? `${btDevices.length} appareil(s)` : 'Appareils BT'}
            </span>
            <button onClick={scanBt} disabled={btScanning} style={{ padding: '2px 8px', background: '#a78bfa15', border: '1px solid #a78bfa30', color: '#a78bfa', borderRadius: 5, cursor: 'pointer', fontSize: '0.6rem' }}>
              {btScanning ? '⏳ ~8s' : '🔄 Scan'}
            </button>
          </div>
          {demoBt && <div style={{ fontSize: '0.55rem', color: '#f59e0b', background: '#1a1000', borderRadius: 5, padding: '3px 8px', marginBottom: 5 }}>🔮 MODE DÉMO — appareils simulés</div>}
          {hasBt === false && !demoBt
            ? <div style={{ fontSize: '0.65rem', color: '#f97316', padding: '8px 10px', background: '#1a0f00', borderRadius: 6, lineHeight: 1.6 }}>
                Pas d'adaptateur Bluetooth<br />
                <span style={{ color: '#664422', fontSize: '0.58rem' }}>→ Branchez un dongle USB BT</span>
              </div>
            : btDevices.length === 0
              ? <div style={{ textAlign: 'center', color: 'var(--text3)', fontSize: '0.68rem', padding: '10px 0' }}>
                  {btScanning ? 'Scan Bluetooth (~8s)…' : 'Aucun appareil — clique Scan'}
                </div>
              : <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 140, overflowY: 'auto' }}>
                  {btDevices.map((d, i) => (
                    <div key={d.address || i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, background: '#a78bfa08', border: '1px solid #a78bfa20' }}>
                      <span style={{ fontSize: 14 }}>🔵</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name || 'Appareil inconnu'}</div>
                        <div style={{ fontSize: '0.55rem', color: 'var(--text3)', fontFamily: 'monospace' }}>{d.address}</div>
                      </div>
                      <span style={{ fontSize: '0.55rem', padding: '1px 5px', background: '#a78bfa20', color: '#a78bfa', borderRadius: 4 }}>{d.type || 'BT'}</span>
                    </div>
                  ))}
                </div>
          }
        </div>
      )}

      <button onClick={() => onNav('wifi-selector')} style={{ width: '100%', padding: '6px', background: '#38bdf815', border: '1px solid #38bdf840', borderRadius: 7, color: '#38bdf8', cursor: 'pointer', fontSize: '0.68rem' }}>
        Gérer les réseaux →
      </button>

      {/* Modal connexion */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: '#000c', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => !connecting && setModal(null)}>
          <div style={{ background: '#141414', border: '1px solid #2a2a2a', borderRadius: 14, padding: 24, width: 320, boxShadow: '0 24px 60px #000d' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: '0.6rem', color: '#555', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Se connecter à</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#44aaff', marginBottom: 16 }}>📶 {modal.ssid}</div>
            {modal.secured
              ? <div style={{ position: 'relative', marginBottom: 16 }}>
                  <input autoFocus type={showPwd ? 'text' : 'password'} value={pwd} onChange={e => setPwd(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && !connecting && connect()}
                    placeholder="Mot de passe WiFi"
                    style={{ width: '100%', boxSizing: 'border-box', background: '#0d0d0d', border: '1px solid #2a2a2a', color: '#fff', padding: '10px 40px 10px 12px', borderRadius: 8, fontSize: 14, outline: 'none' }} />
                  <button onClick={() => setShowPwd(p => !p)} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>{showPwd ? '🙈' : '👁️'}</button>
                </div>
              : <div style={{ color: '#fbbf24', fontSize: 12, marginBottom: 16, padding: '6px 10px', background: '#1a1200', borderRadius: 6 }}>🔓 Réseau ouvert</div>
            }
            {connecting && <div style={{ color: '#44aaff', fontSize: 12, marginBottom: 10, textAlign: 'center' }}>⏳ Connexion…</div>}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setModal(null)} disabled={connecting} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid #2a2a2a', color: '#666', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>Annuler</button>
              <button onClick={connect} disabled={connecting} style={{ padding: '8px 18px', background: '#44aaff', border: 'none', color: '#000', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 700, opacity: connecting ? 0.6 : 1 }}>
                {connecting ? '…' : '🔗 Connecter'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Widget>
  )
}

// ── Dashboard principal ───────────────────────────────────────────────────────
export default function DashboardView({ onNav }) {
  const [greeting, setGreeting] = useState('')
  useEffect(() => {
    const h = new Date().getHours()
    if (h < 6) setGreeting('Bonne nuit')
    else if (h < 12) setGreeting('Bonjour')
    else if (h < 18) setGreeting('Bon après-midi')
    else setGreeting('Bonsoir')
  }, [])

  return (
    <div style={{ padding: '16px 20px', maxWidth: 1400, margin: '0 auto', boxSizing: 'border-box', width: '100%' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', rowGap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '1.3rem', fontWeight: 900, color: 'var(--accent)', letterSpacing: 1 }}>
              {greeting}, Mr Vitch
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginTop: 2 }}>
              {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              {' · '}L'Œil de Dieu v8.0
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[
              { label: 'Chat', view: 'chat', icon: '💬' },
              { label: 'AEGIS', view: 'soc', icon: '🛡️' },
              { label: 'Sentinel', view: 'sentinel', icon: '🔬' },
            ].map(({ label, view, icon }) => (
              <button key={view} onClick={() => onNav(view)} style={{
                padding: '6px 12px', background: 'var(--glass)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontSize: '0.7rem',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                {icon} {label}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Grid responsive : 3 colonnes sur grand écran, 2 sur moyen, 1 sur petit */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: 14,
      }}>
        <SystemWidget />
        <AegisWidget onNav={onNav} />
        <AgentsWidget onNav={onNav} />
        <MemoryWidget onNav={onNav} />
        <LifeWidget onNav={onNav} />
        <NetworkWidget onNav={onNav} />
        <div style={{ gridColumn: '1 / -1' }}>
          <ActionLogWidget />
        </div>
      </div>
    </div>
  )
}
