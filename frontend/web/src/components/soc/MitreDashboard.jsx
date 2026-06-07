import { useState, useEffect, useCallback } from 'react'

const BASE = '/api/mitre'
const getAuthHeaders = () => {
  const t = localStorage.getItem('eye_token')
  return t
    ? { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}
const api = (url) =>
  fetch(url, { headers: getAuthHeaders() }).then((r) => r.json()).catch(() => ({}))

// ── Palette score ─────────────────────────────────────────────────────────────
function scoreColor(score) {
  if (!score || score === 0) return '#0a0a0a'
  if (score <= 2) return '#166534'
  if (score <= 4) return '#9a3412'
  return '#7f1d1d'
}
function scoreBorder(score) {
  if (!score || score === 0) return '#1a1a1a'
  if (score <= 2) return '#16a34a'
  if (score <= 4) return '#ea580c'
  return '#ef4444'
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
const TABS = ['Heatmap', 'Attack Graph', 'Kill Chain', 'Stats', 'Recommandations', 'Timeline']

// ── Tactic order ─────────────────────────────────────────────────────────────
const TACTIC_ORDER = [
  'TA0043','TA0042','TA0001','TA0002','TA0003',
  'TA0004','TA0005','TA0006','TA0009','TA0010','TA0011',
]

// ── Phase colors ─────────────────────────────────────────────────────────────
const PHASE_COLORS = {
  Recon: '#6366f1', 'Resource Dev': '#8b5cf6',
  'Initial Access': '#ec4899', Execution: '#f43f5e',
  Persistence: '#f97316', 'Priv Esc': '#eab308',
  'Defense Evasion': '#84cc16', 'Cred Access': '#22c55e',
  Collection: '#14b8a6', Exfil: '#06b6d4', C2: '#3b82f6',
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
function Tooltip({ children, tip }) {
  const [show, setShow] = useState(false)
  return (
    <div
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && tip && (
        <div style={{
          position: 'absolute', bottom: '110%', left: '50%', transform: 'translateX(-50%)',
          background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
          padding: '6px 10px', fontSize: '0.7rem', color: '#e2e8f0',
          whiteSpace: 'nowrap', zIndex: 100, pointerEvents: 'none',
          boxShadow: '0 4px 12px rgba(0,0,0,.5)',
        }}>
          {tip}
        </div>
      )}
    </div>
  )
}

// ── Tab: Heatmap ─────────────────────────────────────────────────────────────
function HeatmapTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/heatmap`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  if (!campaignId)
    return <div style={s.empty}>Entrez un Campaign ID pour afficher la heatmap.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>
  if (!data?.heatmap?.length)
    return <div style={s.empty}>Aucune donnée pour cette campagne.</div>

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.72rem' }}>
        <tbody>
          {data.heatmap.map((row) => {
            const techniques = Object.entries(row.techniques || {})
            return (
              <tr key={row.tactic_id}>
                <td style={{
                  padding: '4px 10px', color: '#94a3b8', fontWeight: 600,
                  whiteSpace: 'nowrap', minWidth: 130, borderBottom: '1px solid #1e293b',
                }}>
                  <span style={{
                    display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                    background: PHASE_COLORS[row.phase] || '#64748b', marginRight: 6,
                  }} />
                  {row.phase}
                </td>
                <td style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    {techniques.length === 0 ? (
                      <span style={{ color: '#334155', fontSize: '0.65rem' }}>—</span>
                    ) : (
                      techniques.map(([tid, count]) => (
                        <Tooltip key={tid} tip={`${tid} — ${count} hit(s)`}>
                          <div style={{
                            width: 32, height: 24, borderRadius: 3,
                            background: scoreColor(Math.min(count * 2, 5)),
                            border: `1px solid ${scoreBorder(Math.min(count * 2, 5))}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'default', fontSize: '0.6rem', color: '#e2e8f0',
                            fontFamily: 'monospace',
                          }}>
                            {count}
                          </div>
                        </Tooltip>
                      ))
                    )}
                  </div>
                </td>
                <td style={{
                  padding: '4px 8px', color: '#475569', fontSize: '0.65rem',
                  borderBottom: '1px solid #1e293b', whiteSpace: 'nowrap',
                }}>
                  {row.total_hits > 0 ? `${row.total_hits} hits` : '0'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: '0.65rem', color: '#64748b' }}>
        {[
          { label: '0 hits', color: '#0a0a0a', border: '#1a1a1a' },
          { label: '1–2', color: '#166534', border: '#16a34a' },
          { label: '3–4', color: '#9a3412', border: '#ea580c' },
          { label: '5+', color: '#7f1d1d', border: '#ef4444' },
        ].map((l) => (
          <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              display: 'inline-block', width: 14, height: 14, borderRadius: 2,
              background: l.color, border: `1px solid ${l.border}`,
            }} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Tab: Attack Graph ─────────────────────────────────────────────────────────
function AttackGraphTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/graph`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  if (!campaignId)
    return <div style={s.empty}>Entrez un Campaign ID.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>
  if (!data?.nodes?.length)
    return <div style={s.empty}>Aucun noeud graphe.</div>

  const nodes = data.nodes || []
  const edges = data.edges || []

  // Group nodes by phase_order for column layout
  const byPhase = {}
  for (const n of nodes) {
    const key = n.tactic || 'unknown'
    if (!byPhase[key]) byPhase[key] = []
    byPhase[key].push(n)
  }

  const colW = 160
  const nodeH = 56
  const colGap = 40
  const rowGap = 12
  const padX = 20
  const padY = 20

  const phases = Object.keys(byPhase)
  const totalW = phases.length * (colW + colGap) + padX * 2
  const maxRows = Math.max(...phases.map((p) => byPhase[p].length))
  const totalH = maxRows * (nodeH + rowGap) + padY * 2 + 30

  // Map technique_id → center coords
  const coords = {}
  phases.forEach((phase, ci) => {
    byPhase[phase].forEach((node, ri) => {
      const cx = padX + ci * (colW + colGap) + colW / 2
      const cy = padY + 30 + ri * (nodeH + rowGap) + nodeH / 2
      coords[node.technique_id] = { cx, cy }
    })
  })

  return (
    <div>
      <div style={{
        marginBottom: 8, fontSize: '0.72rem', color: '#64748b',
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <span>Kill Chain Progress:</span>
        <div style={{ flex: 1, background: '#1e293b', borderRadius: 4, height: 8, maxWidth: 200 }}>
          <div style={{
            width: `${data.kill_chain_progress || 0}%`,
            height: '100%', borderRadius: 4,
            background: 'linear-gradient(90deg, #3b82f6, #6366f1)',
          }} />
        </div>
        <span style={{ color: '#e2e8f0', fontWeight: 700 }}>{data.kill_chain_progress}%</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <svg width={totalW} height={totalH} style={{ background: '#030712', borderRadius: 8 }}>
          {/* Phase labels */}
          {phases.map((phase, ci) => {
            const x = padX + ci * (colW + colGap)
            const color = PHASE_COLORS[byPhase[phase][0]?.phase] || '#64748b'
            return (
              <text key={phase} x={x + colW / 2} y={padY + 16}
                fill={color} fontSize="10" textAnchor="middle" fontWeight="600">
                {byPhase[phase][0]?.phase || phase}
              </text>
            )
          })}

          {/* Edges */}
          {edges.map((e, i) => {
            const src = coords[e.source]
            const tgt = coords[e.target]
            if (!src || !tgt) return null
            return (
              <line key={i} x1={src.cx} y1={src.cy} x2={tgt.cx} y2={tgt.cy}
                stroke="#1e3a5f" strokeWidth="1.5" strokeDasharray="4 3" />
            )
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const c = coords[node.technique_id]
            if (!c) return null
            const color = PHASE_COLORS[node.phase] || '#64748b'
            return (
              <g key={node.technique_id}>
                <rect x={c.cx - colW / 2} y={c.cy - nodeH / 2}
                  width={colW} height={nodeH} rx="6"
                  fill="#0f172a" stroke={color} strokeWidth="1.5" />
                <text x={c.cx} y={c.cy - 8} fill={color} fontSize="10"
                  textAnchor="middle" fontWeight="700" fontFamily="monospace">
                  {node.technique_id}
                </text>
                <text x={c.cx} y={c.cy + 6} fill="#94a3b8" fontSize="9"
                  textAnchor="middle">
                  {node.name?.length > 20 ? node.name.slice(0, 20) + '…' : node.name}
                </text>
                <text x={c.cx} y={c.cy + 18} fill="#475569" fontSize="8"
                  textAnchor="middle">
                  score {node.score} · {node.count}×
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Légende */}
      <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {Object.entries(PHASE_COLORS).map(([phase, color]) => (
          <span key={phase} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.65rem', color: '#94a3b8' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: color }} />
            {phase}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Tab: Kill Chain ───────────────────────────────────────────────────────────
function KillChainTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/stats`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  const SEGMENTS = [
    { id: 'TA0043', label: 'Recon' },
    { id: 'TA0042', label: 'Res Dev' },
    { id: 'TA0001', label: 'Init Acc' },
    { id: 'TA0002', label: 'Exec' },
    { id: 'TA0003', label: 'Persist' },
    { id: 'TA0004', label: 'PrivEsc' },
    { id: 'TA0005', label: 'Def Ev' },
    { id: 'TA0006', label: 'Cred' },
    { id: 'TA0009', label: 'Collect' },
    { id: 'TA0010', label: 'Exfil' },
    { id: 'TA0011', label: 'C2' },
  ]

  if (!campaignId) return <div style={s.empty}>Entrez un Campaign ID.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>

  const completed = new Set(data?.completed_phases || [])

  return (
    <div>
      <div style={{ display: 'flex', gap: 2, marginBottom: 16, flexWrap: 'wrap' }}>
        {SEGMENTS.map((seg, i) => {
          const color = PHASE_COLORS[seg.label] || '#64748b'
          const active = completed.has(seg.label)
          return (
            <div key={seg.id} style={{ flex: 1, minWidth: 60, textAlign: 'center' }}>
              <div style={{
                background: active ? color : '#0f172a',
                border: `2px solid ${active ? color : '#1e293b'}`,
                borderRadius: 6, padding: '10px 4px',
                boxShadow: active ? `0 0 12px ${color}55` : 'none',
                transition: 'all 0.3s',
              }}>
                <div style={{
                  fontSize: '0.6rem', fontWeight: 700,
                  color: active ? '#fff' : '#475569', letterSpacing: '0.04em',
                }}>
                  {i + 1}
                </div>
                <div style={{
                  fontSize: '0.65rem', fontWeight: 600,
                  color: active ? '#fff' : '#64748b', marginTop: 2,
                }}>
                  {seg.label}
                </div>
              </div>
              <div style={{
                marginTop: 4, fontSize: '0.6rem', fontWeight: 700,
                color: active ? '#22c55e' : '#374151',
              }}>
                {active ? 'DONE' : '—'}
              </div>
            </div>
          )
        })}
      </div>

      <div style={{
        background: '#0f172a', borderRadius: 8, padding: '12px 16px',
        border: '1px solid #1e293b', fontSize: '0.8rem',
      }}>
        <div style={{ display: 'flex', gap: 24, color: '#94a3b8' }}>
          <span>Phases complétées:
            <strong style={{ color: '#22c55e', marginLeft: 8 }}>
              {completed.size} / {SEGMENTS.length}
            </strong>
          </span>
          <span>Progression:
            <strong style={{ color: '#3b82f6', marginLeft: 8 }}>
              {Math.round(completed.size / SEGMENTS.length * 100)}%
            </strong>
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Tab: Stats ────────────────────────────────────────────────────────────────
function StatsTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/stats`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  if (!campaignId) return <div style={s.empty}>Entrez un Campaign ID.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>
  if (!data) return <div style={s.empty}>Aucune stat.</div>

  const kpis = [
    { label: 'Techniques', value: data.total_techniques ?? 0, color: '#6366f1' },
    { label: 'Tactiques', value: data.total_tactics ?? 0, color: '#8b5cf6' },
    { label: 'Score Total', value: data.total_score ?? 0, color: '#f43f5e' },
    { label: 'Coverage %', value: `${data.coverage ?? 0}%`, color: '#22c55e' },
  ]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {kpis.map((k) => (
          <div key={k.label} style={{
            background: '#0f172a', border: `1px solid ${k.color}44`,
            borderRadius: 10, padding: '16px 12px', textAlign: 'center',
            boxShadow: `0 0 20px ${k.color}22`,
          }}>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: k.color }}>{k.value}</div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {data.top_techniques?.length > 0 && (
        <div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: 8, fontWeight: 600 }}>
            TOP 5 TECHNIQUES
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr>
                {['Technique', 'Tactique', 'Hits', 'Score'].map((h) => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '6px 10px',
                    color: '#475569', borderBottom: '1px solid #1e293b',
                    fontWeight: 600,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.top_techniques.map((t, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #0f172a' }}>
                  <td style={{ padding: '6px 10px', color: '#6366f1', fontFamily: 'monospace', fontWeight: 700 }}>
                    {t.technique_id}
                  </td>
                  <td style={{ padding: '6px 10px', color: '#94a3b8' }}>{t.tactic_name}</td>
                  <td style={{ padding: '6px 10px', color: '#e2e8f0' }}>{t.count}</td>
                  <td style={{ padding: '6px 10px', color: '#f43f5e' }}>{t.total_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab: Recommandations ──────────────────────────────────────────────────────
function RecommandationsTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/recommendations`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  const copy = (action) => {
    navigator.clipboard?.writeText(`# MITRE ${action}`)
    setCopied(action)
    setTimeout(() => setCopied(null), 2000)
  }

  const PRIORITY_COLOR = { haute: '#ef4444', moyenne: '#f97316', faible: '#22c55e' }

  if (!campaignId) return <div style={s.empty}>Entrez un Campaign ID.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>
  if (!data?.recommendations?.length)
    return <div style={s.empty}>Toutes les techniques sont couvertes !</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {data.recommendations.slice(0, 30).map((r, i) => (
        <div key={i} style={{
          background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8,
          padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{
            fontSize: '0.6rem', fontWeight: 700, padding: '2px 6px', borderRadius: 4,
            background: `${PRIORITY_COLOR[r.priority]}22`,
            border: `1px solid ${PRIORITY_COLOR[r.priority]}55`,
            color: PRIORITY_COLOR[r.priority], minWidth: 50, textAlign: 'center',
          }}>
            {r.priority?.toUpperCase()}
          </span>
          <span style={{ fontFamily: 'monospace', color: '#6366f1', fontWeight: 700, fontSize: '0.8rem', minWidth: 90 }}>
            {r.technique_id}
          </span>
          <span style={{ fontSize: '0.72rem', color: '#94a3b8', flex: 1 }}>
            {r.action_type} · <span style={{ color: '#475569' }}>{r.phase}</span>
          </span>
          <span style={{ fontSize: '0.65rem', color: '#374151' }}>{r.reason}</span>
          <button
            onClick={() => copy(r.action_type)}
            style={{
              background: copied === r.action_type ? '#166534' : '#1e293b',
              border: '1px solid #334155', borderRadius: 4,
              padding: '3px 8px', color: '#94a3b8', cursor: 'pointer',
              fontSize: '0.65rem', whiteSpace: 'nowrap',
            }}
          >
            {copied === r.action_type ? 'Copié !' : 'Copier cmd'}
          </button>
        </div>
      ))}
    </div>
  )
}

// ── Tab: Timeline ─────────────────────────────────────────────────────────────
function TimelineTab({ campaignId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!campaignId) return
    setLoading(true)
    api(`${BASE}/campaign/${campaignId}/events?limit=100`)
      .then(setData)
      .finally(() => setLoading(false))
  }, [campaignId])

  if (!campaignId) return <div style={s.empty}>Entrez un Campaign ID.</div>
  if (loading) return <div style={s.loading}>Chargement…</div>
  if (!data?.events?.length) return <div style={s.empty}>Aucun événement.</div>

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.73rem' }}>
        <thead>
          <tr>
            {['Timestamp', 'Technique', 'Tactique', 'Action', 'Score', 'Statut'].map((h) => (
              <th key={h} style={{
                textAlign: 'left', padding: '6px 10px',
                color: '#475569', borderBottom: '1px solid #1e293b', fontWeight: 600,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.events.map((e) => (
            <tr key={e.event_id} style={{ borderBottom: '1px solid #0f172a' }}>
              <td style={{ padding: '5px 10px', color: '#475569', fontFamily: 'monospace', fontSize: '0.65rem' }}>
                {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
              </td>
              <td style={{ padding: '5px 10px', color: '#6366f1', fontFamily: 'monospace', fontWeight: 700 }}>
                {e.technique_id}
              </td>
              <td style={{ padding: '5px 10px', color: '#94a3b8' }}>{e.tactic_id}</td>
              <td style={{ padding: '5px 10px', color: '#e2e8f0' }}>{e.action_type}</td>
              <td style={{ padding: '5px 10px' }}>
                <span style={{
                  color: e.score >= 5 ? '#ef4444' : e.score >= 3 ? '#f97316' : '#22c55e',
                  fontWeight: 700,
                }}>
                  {e.score}
                </span>
              </td>
              <td style={{ padding: '5px 10px' }}>
                <span style={{ color: e.success ? '#22c55e' : '#ef4444', fontSize: '0.65rem' }}>
                  {e.success ? 'OK' : 'FAIL'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function MitreDashboard() {
  const [campaignId, setCampaignId] = useState('')
  const [activeTab, setActiveTab] = useState('Heatmap')
  const [inputVal, setInputVal] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    setCampaignId(inputVal.trim())
  }

  return (
    <div style={{
      background: '#030712', minHeight: '100vh', color: '#e2e8f0',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 20,
    }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{
          margin: '0 0 4px', fontSize: '1.3rem', fontWeight: 800,
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          letterSpacing: '0.06em',
        }}>
          MITRE ATT&CK
        </h2>
        <div style={{ color: '#64748b', fontSize: '0.72rem' }}>
          Cartographie automatique des techniques d'attaque
        </div>
      </div>

      {/* Campaign ID Input */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <input
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Campaign ID (ex: camp-2024-001)"
          style={{
            flex: 1, background: '#0f172a', border: '1px solid #1e293b',
            borderRadius: 8, padding: '8px 14px', color: '#e2e8f0',
            fontSize: '0.82rem', outline: 'none',
          }}
        />
        <button type="submit" style={{
          background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
          border: 'none', borderRadius: 8, padding: '8px 18px',
          color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '0.82rem',
        }}>
          Analyser
        </button>
      </form>

      {campaignId && (
        <div style={{
          display: 'inline-block', background: '#0f172a',
          border: '1px solid #1e293b', borderRadius: 6,
          padding: '3px 10px', fontSize: '0.7rem', color: '#6366f1',
          marginBottom: 16, fontFamily: 'monospace',
        }}>
          Campagne: {campaignId}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 20, borderBottom: '1px solid #1e293b' }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              background: 'none', border: 'none',
              borderBottom: activeTab === tab ? '2px solid #6366f1' : '2px solid transparent',
              padding: '8px 14px', cursor: 'pointer',
              color: activeTab === tab ? '#6366f1' : '#64748b',
              fontSize: '0.78rem', fontWeight: activeTab === tab ? 700 : 400,
              transition: 'all 0.2s',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'Heatmap'         && <HeatmapTab campaignId={campaignId} />}
        {activeTab === 'Attack Graph'    && <AttackGraphTab campaignId={campaignId} />}
        {activeTab === 'Kill Chain'      && <KillChainTab campaignId={campaignId} />}
        {activeTab === 'Stats'           && <StatsTab campaignId={campaignId} />}
        {activeTab === 'Recommandations' && <RecommandationsTab campaignId={campaignId} />}
        {activeTab === 'Timeline'        && <TimelineTab campaignId={campaignId} />}
      </div>
    </div>
  )
}

// ── Styles communs ────────────────────────────────────────────────────────────
const s = {
  empty: {
    color: '#334155', fontSize: '0.8rem', padding: '40px 0', textAlign: 'center',
  },
  loading: {
    color: '#6366f1', fontSize: '0.8rem', padding: '40px 0', textAlign: 'center',
    animation: 'pulse 1.5s infinite',
  },
}
