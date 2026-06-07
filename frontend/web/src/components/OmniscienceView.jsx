/**
 * OmniscienceView — Dashboard global : stats, carte réseau, alertes, feeds
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const SEV_COLOR = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24', LOW: '#4ade80', INFO: '#38bdf8' }

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ icon, label, value, color = 'var(--accent)' }) {
  return (
    <div style={{
      background: 'var(--glass)', border: `1px solid ${color}30`,
      borderRadius: 12, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: color + '18', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem' }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: '1.3rem', fontWeight: 800, color, lineHeight: 1 }}>{value ?? '—'}</div>
        <div style={{ fontSize: '0.62rem', color: 'var(--text3)', letterSpacing: 1, marginTop: 2 }}>{label}</div>
      </div>
    </div>
  )
}

// ── SVG Network Map ──────────────────────────────────────────────────────────
function NetworkMap({ nodes, edges }) {
  const W = 520, H = 320
  const nodeMap = {}
  nodes.forEach(n => { nodeMap[n.id] = n })

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%', background: '#000a18', borderRadius: 10 }}>
      {/* Background grid */}
      <defs>
        <pattern id="omni-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#ffffff06" strokeWidth="0.5" />
        </pattern>
        <radialGradient id="node-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#omni-grid)" />

      {/* Edges */}
      {edges.map((e, i) => {
        const src = nodeMap[e.source]
        const dst = nodeMap[e.target]
        if (!src || !dst) return null
        return (
          <line key={i} x1={src.x} y1={src.y} x2={dst.x} y2={dst.y}
            stroke="#00d4ff20" strokeWidth={1.5} strokeDasharray={e.active ? '0' : '4 4'} />
        )
      })}

      {/* Nodes */}
      {nodes.map((n, i) => {
        const color = n.type === 'camera' ? '#4ade80'
          : n.type === 'beacon' ? '#ef4444'
          : n.type === 'target' ? '#fbbf24'
          : '#38bdf8'
        return (
          <g key={i}>
            <circle cx={n.x} cy={n.y} r={20} fill={color + '15'} stroke={color} strokeWidth={1} />
            <circle cx={n.x} cy={n.y} r={8} fill={color} opacity={0.9} />
            {n.alert && <circle cx={n.x} cy={n.y} r={18} fill="none" stroke="#ef4444" strokeWidth={1.5}
              strokeDasharray="4 2" style={{ animation: 'ring-cw 3s linear infinite' }} />}
            <text x={n.x} y={n.y + 24} textAnchor="middle" fill={color} fontSize="9" fontFamily="monospace">
              {n.label?.slice(0, 14)}
            </text>
          </g>
        )
      })}

      {/* Legend */}
      {[
        { color: '#4ade80', label: 'Camera' },
        { color: '#ef4444', label: 'Beacon' },
        { color: '#fbbf24', label: 'Target' },
        { color: '#38bdf8', label: 'Device' },
      ].map((l, i) => (
        <g key={i}>
          <circle cx={10} cy={H - 60 + i * 14} r={4} fill={l.color} />
          <text x={18} y={H - 56 + i * 14} fill={l.color} fontSize="9">{l.label}</text>
        </g>
      ))}
    </svg>
  )
}

// ── Composant principal ──────────────────────────────────────────────────────
export default function OmniscienceView() {
  const [stats,      setStats]      = useState(null)
  const [activities, setActivities] = useState([])
  const [alerts,     setAlerts]     = useState([])
  const [snapshots,  setSnapshots]  = useState([])
  const [networkData,setNetworkData]= useState({ nodes: [], edges: [] })
  const [report,     setReport]     = useState(null)
  const [reportLoading,setReportLoading] = useState(false)
  const actFeedRef = useRef(null)

  const loadAll = () => {
    // Stats
    apiFetch('/omniscience/stats').then(r => r.json()).then(setStats).catch(() => {})
    // Activity
    apiFetch('/omniscience/activity?limit=50').then(r => r.json()).then(d => setActivities(d.events || [])).catch(() => {})
    // Alerts
    apiFetch('/soc/alerts?limit=30').then(r => r.json()).then(d => setAlerts(d.alerts || [])).catch(() => {})
    // Camera snapshots
    apiFetch('/cameras/recent-snapshots?limit=4').then(r => r.json()).then(d => setSnapshots(d.snapshots || [])).catch(() => {})
    // Network map
    apiFetch('/omniscience/network-map').then(r => r.json()).then(d => {
      const nodes = (d.nodes || []).map((n, i) => ({
        ...n,
        x: 60 + (i % 7) * 60 + Math.sin(i) * 20,
        y: 50 + Math.floor(i / 7) * 80 + Math.cos(i) * 20,
      }))
      setNetworkData({ nodes, edges: d.edges || [] })
    }).catch(() => {
      // Fallback placeholder nodes
      setNetworkData({
        nodes: [
          { id: '1', label: 'AEGIS', type: 'device', x: 260, y: 160 },
          { id: '2', label: '192.168.1.10', type: 'camera', x: 120, y: 80 },
          { id: '3', label: '192.168.1.20', type: 'camera', x: 400, y: 80 },
          { id: '4', label: '10.0.0.5', type: 'beacon', x: 120, y: 240 },
          { id: '5', label: 'target.local', type: 'target', x: 400, y: 240 },
        ],
        edges: [
          { source: '1', target: '2' }, { source: '1', target: '3' },
          { source: '1', target: '4' }, { source: '1', target: '5' },
        ],
      })
    })
  }

  useEffect(() => {
    loadAll()
    const t = setInterval(loadAll, 8000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (actFeedRef.current) actFeedRef.current.scrollTop = actFeedRef.current.scrollHeight
  }, [activities])

  const generateReport = async () => {
    setReportLoading(true)
    try {
      const r = await apiFetch('/omniscience/report')
      const d = await r.json()
      setReport(d)
    } catch {}
    setReportLoading(false)
  }

  // Grouped alerts by severity
  const alertsBySev = Object.entries(
    alerts.reduce((acc, a) => { acc[a.severity] = (acc[a.severity] || 0) + 1; return acc }, {})
  ).sort(([a], [b]) => {
    const order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
    return order.indexOf(a) - order.indexOf(b)
  })

  const STAT_CARDS = [
    { icon: '📡', label: 'BEACONS',       key: 'beacons',    color: '#ef4444' },
    { icon: '📷', label: 'CAMERAS',       key: 'cameras',    color: '#4ade80' },
    { icon: '🚨', label: 'ALERTES',       key: 'alerts',     color: '#fbbf24' },
    { icon: '🔍', label: 'CVEs',          key: 'cves',       color: '#f97316' },
    { icon: '🎤', label: 'ENREGISTREMENTS',key: 'recordings', color: '#a78bfa' },
    { icon: '🔭', label: 'SCANS',         key: 'scans',      color: '#38bdf8' },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>🌍</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            OMNISCIENCE
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Vue globale · Temps réel · Intelligence unifiée
          </div>
        </div>
        <button onClick={generateReport} disabled={reportLoading} style={{
          marginLeft: 'auto', padding: '8px 20px', background: 'var(--glow2)',
          border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--accent)',
          cursor: 'pointer', fontWeight: 700, fontSize: '0.8rem',
        }}>
          {reportLoading ? '⟳ Génération…' : '📊 Générer Rapport'}
        </button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
        {STAT_CARDS.map(s => (
          <StatCard key={s.key} icon={s.icon} label={s.label} value={stats?.[s.key]} color={s.color} />
        ))}
      </div>

      {/* Main: Network Map + Side panels */}
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr 240px', gap: 16, marginBottom: 20 }}>

        {/* Activity feed */}
        <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 14 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 10 }}>ACTIVITÉ RÉCENTE</div>
          <div ref={actFeedRef} style={{ height: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 5 }}>
            {activities.length === 0 ? (
              <div style={{ color: 'var(--text3)', fontSize: '0.72rem', textAlign: 'center', paddingTop: 40 }}>Aucune activité</div>
            ) : activities.map((evt, i) => (
              <div key={i} style={{
                padding: '6px 8px', background: '#ffffff06', borderRadius: 6,
                borderLeft: `3px solid ${SEV_COLOR[evt.severity] || '#38bdf8'}`,
              }}>
                <div style={{ fontSize: '0.6rem', color: 'var(--text3)' }}>{evt.timestamp?.slice(11, 19)}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text)', marginTop: 2, lineHeight: 1.4 }}>
                  {evt.title || evt.message || evt.type}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Network Map */}
        <div className="omni-map" style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>CARTE RÉSEAU</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80', display: 'inline-block', animation: 'neon-pulse 2s infinite' }} />
              <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>LIVE</span>
            </div>
          </div>
          <div style={{ height: 300 }}>
            <NetworkMap nodes={networkData.nodes} edges={networkData.edges} />
          </div>
        </div>

        {/* Alerts by severity */}
        <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 14 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 10 }}>ALERTES PAR SÉVÉRITÉ</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {alertsBySev.map(([sev, count]) => (
              <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: '0.65rem', fontWeight: 700, color: SEV_COLOR[sev], minWidth: 60 }}>{sev}</span>
                <div style={{ flex: 1, height: 6, background: '#ffffff10', borderRadius: 3 }}>
                  <div style={{
                    height: '100%', width: `${Math.min((count / (alerts.length || 1)) * 100, 100)}%`,
                    background: SEV_COLOR[sev], borderRadius: 3, transition: 'width 0.5s',
                  }} />
                </div>
                <span style={{ fontSize: '0.72rem', color: SEV_COLOR[sev], fontWeight: 700, minWidth: 20, textAlign: 'right' }}>{count}</span>
              </div>
            ))}
            {alertsBySev.length === 0 && <div style={{ color: '#4ade80', fontSize: '0.75rem', textAlign: 'center', paddingTop: 20 }}>✓ Aucune alerte</div>}
          </div>
          {/* Recent alerts */}
          <div style={{ maxHeight: 160, overflowY: 'auto' }}>
            {alerts.slice(0, 6).map((a, i) => (
              <div key={i} style={{ fontSize: '0.68rem', color: 'var(--text2)', marginBottom: 5, paddingBottom: 5, borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: SEV_COLOR[a.severity] }}>●</span>{' '}
                <span style={{ color: 'var(--text)' }}>{a.title?.slice(0, 32)}</span>
                <div style={{ color: 'var(--text3)', fontSize: '0.6rem' }}>{a.timestamp?.slice(11, 19)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom: Camera feed mosaic */}
      <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>FLUX CAMERAS EN DIRECT</div>
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>4 dernières captures</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {[0, 1, 2, 3].map(i => {
            const snap = snapshots[i]
            return (
              <div key={i} style={{
                background: '#000820', borderRadius: 8, border: '1px solid var(--border)',
                aspectRatio: '16/10', overflow: 'hidden', position: 'relative',
              }}>
                {snap?.url || snap?.data ? (
                  <img
                    src={snap.url || `data:image/jpeg;base64,${snap.data}`}
                    alt={snap.ip}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: '0.72rem' }}>
                    📷 Pas de flux
                  </div>
                )}
                {snap && (
                  <div style={{
                    position: 'absolute', bottom: 0, left: 0, right: 0,
                    background: '#000c', padding: '4px 8px',
                    fontSize: '0.6rem', color: 'var(--text)',
                  }}>
                    {snap.ip} · {snap.timestamp?.slice(11, 19)}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Report modal */}
      {report && (
        <div onClick={() => setReport(null)} style={{
          position: 'fixed', inset: 0, background: '#000c', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'var(--glass)', border: '1px solid var(--border2)',
            borderRadius: 16, padding: 24, maxWidth: '80vw', maxHeight: '80vh', overflow: 'auto',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ color: 'var(--accent)', fontWeight: 800, fontSize: '1rem' }}>📊 Rapport d'Omniscience</span>
              <button onClick={() => setReport(null)} style={{ background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
            </div>
            <pre style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(report, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
