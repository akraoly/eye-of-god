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
    <Widget title="JOURNAL TEMPS RÉEL" icon="📋" color="#38bdf8" style={{ gridColumn: 'span 2' }}>
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
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: 'var(--accent)', letterSpacing: 1 }}>
              {greeting}, Mr Vitch
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: 2 }}>
              {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              {' · '}L'Œil de Dieu v8.0 · Tous les systèmes opérationnels
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            {[
              { label: 'Chat', view: 'chat', icon: '💬' },
              { label: 'AEGIS', view: 'soc', icon: '🛡️' },
              { label: 'Sentinel', view: 'sentinel', icon: '🔬' },
            ].map(({ label, view, icon }) => (
              <button key={view} onClick={() => onNav(view)} style={{
                padding: '7px 14px', background: 'var(--glass)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontSize: '0.72rem',
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                {icon} {label}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Grid 3×2 de widgets */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 16,
      }}>
        <SystemWidget />
        <AegisWidget onNav={onNav} />
        <AgentsWidget onNav={onNav} />
        <MemoryWidget onNav={onNav} />
        <LifeWidget onNav={onNav} />
        <ActionLogWidget />
      </div>
    </div>
  )
}
