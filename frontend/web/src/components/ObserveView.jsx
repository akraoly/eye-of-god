import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

const TABS = [
  { id: 'health',  label: '🩺 Santé'   },
  { id: 'actions', label: '📋 Actions' },
  { id: 'report',  label: '📄 Rapport' },
]

const PERIODS = [
  { value: 7,  label: '7 j'  },
  { value: 14, label: '14 j' },
  { value: 30, label: '30 j' },
  { value: 90, label: '90 j' },
]

const STATUS_STYLE = {
  success: { color: '#6ee7b7', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)', label: '✓' },
  error:   { color: '#f87171', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',  label: '✕' },
  skipped: { color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.2)',label: '—' },
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'à l\'instant'
  if (m < 60) return `il y a ${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  return `il y a ${Math.floor(h / 24)}j`
}

/* ──────────────────────────── ONGLET SANTÉ ──────────────────────────────── */
function TabHealth({ period, onPeriodChange }) {
  const [data,    setData]    = useState(null)
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const [r1, r2] = await Promise.all([
      apiFetch(`/observe/report?days=${period}`),
      apiFetch('/observe/stats'),
    ])
    if (r1.ok) setData(await r1.json())
    if (r2.ok) setStats(await r2.json())
    setLoading(false)
  }, [period])

  useEffect(() => { load() }, [load])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Barre contrôles */}
      <div style={{ padding: '12px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text3)' }}>Période :</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {PERIODS.map(p => (
            <button key={p.value}
              className={period === p.value ? 'mem-filter-btn active' : 'mem-filter-btn'}
              onClick={() => onPeriodChange(p.value)}>
              {p.label}
            </button>
          ))}
        </div>
        <button className="mem-add-btn" onClick={load} disabled={loading} style={{ marginLeft: 'auto' }}>
          {loading ? '⏳' : '↺ Actualiser'}
        </button>
      </div>

      <div className="memory-scroll">
        {/* Cartes stats globales */}
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginBottom: 22 }}>
            {[
              { label: 'Actions totales', value: stats.actions,          icon: '⚡', color: '#a78bfa' },
              { label: 'Base de savoir',  value: stats.knowledge_entries, icon: '📚', color: '#38bdf8' },
              { label: 'Évènements appris', value: stats.learning_events, icon: '🧠', color: '#6ee7b7' },
              { label: 'Objectifs actifs', value: stats.goals_active,    icon: '🎯', color: '#f59e0b' },
              { label: 'Habitudes',        value: stats.habits_active,   icon: '🔄', color: '#fb7185' },
            ].map(s => (
              <div key={s.label} style={{
                background: 'var(--glass2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                padding: '14px', display: 'flex', flexDirection: 'column', gap: 5, backdropFilter: 'blur(12px)',
              }}>
                <span style={{ fontSize: '1.3rem' }}>{s.icon}</span>
                <span style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color }}>{s.value ?? '…'}</span>
                <span style={{ fontSize: '0.68rem', color: 'var(--text3)', lineHeight: 1.3 }}>{s.label}</span>
              </div>
            ))}
          </div>
        )}

        {data && (
          <>
            {/* Healthy */}
            {data.healthy?.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <div className="obs-section-title" style={{ color: '#6ee7b7' }}>✅ Points positifs</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.healthy.map((item, i) => (
                    <div key={i} className="obs-item obs-healthy">{item}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Issues */}
            {data.issues?.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <div className="obs-section-title" style={{ color: '#f87171' }}>⚠️ Problèmes détectés</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.issues.map((item, i) => (
                    <div key={i} className="obs-item obs-issue">{item}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Suggestions */}
            {data.suggestions?.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <div className="obs-section-title" style={{ color: '#f59e0b' }}>💡 Suggestions</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.suggestions.map((item, i) => (
                    <div key={i} className="obs-item obs-suggestion">{item}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Stats période */}
            {data.stats && (
              <div style={{ background: 'var(--glass2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16, backdropFilter: 'blur(12px)' }}>
                <div className="obs-section-title" style={{ marginBottom: 10 }}>📊 Stats sur {period} jours</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {[
                    ['Actions totales', data.stats.total_actions],
                    ['Erreurs',         data.stats.total_errors],
                    ['Taux d\'erreur',  data.stats.error_rate !== undefined ? (data.stats.error_rate * 100).toFixed(1) + '%' : '—'],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text3)' }}>{k}</span>
                      <span style={{ color: 'var(--text2)', fontWeight: 600 }}>{v}</span>
                    </div>
                  ))}
                </div>
                {/* Activité par agent */}
                {data.stats.agents && Object.keys(data.stats.agents).length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Activité par agent</div>
                    {Object.entries(data.stats.agents)
                      .sort((a, b) => b[1].total - a[1].total)
                      .map(([agent, d]) => {
                        const errRate = d.total > 0 ? d.error / d.total : 0
                        const color = errRate > 0.3 ? '#f87171' : errRate > 0.1 ? '#f59e0b' : '#6ee7b7'
                        return (
                          <div key={agent} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                            <span style={{ width: 80, fontSize: '0.72rem', color: 'var(--text2)', fontWeight: 600 }}>{agent}</span>
                            <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'rgba(255,255,255,0.07)' }}>
                              <div style={{ width: `${Math.min((d.total / (data.stats.total_actions || 1)) * 100, 100)}%`, height: '100%', borderRadius: 3, background: color, opacity: 0.75 }} />
                            </div>
                            <span style={{ fontSize: '0.68rem', color: 'var(--text3)', width: 60, textAlign: 'right' }}>
                              {d.total} | {d.error ?? 0} err
                            </span>
                          </div>
                        )
                      })}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {!data && !loading && (
          <div className="mem-empty">
            <div className="mem-empty-icon">🔭</div>
            <div>Aucune donnée d'observation disponible.</div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── ONGLET ACTIONS ────────────────────────────── */
function TabActions() {
  const [actions,    setActions]    = useState([])
  const [total,      setTotal]      = useState(0)
  const [filterStat, setFilterStat] = useState('all')
  const [filterAgt,  setFilterAgt]  = useState('all')
  const [limit,      setLimit]      = useState(50)
  const [loading,    setLoading]    = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const r = await apiFetch(`/observe/actions?limit=${limit}`)
    if (r.ok) {
      const d = await r.json()
      setActions(d.actions)
      setTotal(d.count)
    }
    setLoading(false)
  }, [limit])

  useEffect(() => { load() }, [load])

  const agents = ['all', ...new Set(actions.map(a => a.agent))]
  const visible = actions.filter(a =>
    (filterStat === 'all' || a.status === filterStat) &&
    (filterAgt  === 'all' || a.agent  === filterAgt)
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Contrôles */}
      <div style={{ padding: '10px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {['all','success','error','skipped'].map(s => (
            <button key={s}
              className={filterStat === s ? 'mem-filter-btn active' : 'mem-filter-btn'}
              style={filterStat !== s && s !== 'all' ? { color: STATUS_STYLE[s]?.color } : {}}
              onClick={() => setFilterStat(s)}>
              {s === 'all' ? 'Tout' : s}
            </button>
          ))}
        </div>
        <select className="mem-input" value={filterAgt} onChange={e => setFilterAgt(e.target.value)} style={{ width: 110, padding: '4px 8px', fontSize: '0.75rem' }}>
          {agents.map(a => <option key={a} value={a}>{a === 'all' ? 'Tous agents' : a}</option>)}
        </select>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="mem-badge">{visible.length}</span>
          <select className="mem-input" value={limit} onChange={e => setLimit(+e.target.value)} style={{ width: 70, padding: '4px 8px', fontSize: '0.75rem' }}>
            {[20,50,100,200,500].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
          <button className="mem-add-btn" onClick={load} disabled={loading}>{loading ? '⏳' : '↺'}</button>
        </div>
      </div>

      {/* Timeline */}
      <div className="memory-scroll">
        {visible.length === 0 ? (
          <div className="mem-empty">
            <div className="mem-empty-icon">📋</div>
            <div>Aucune action{filterStat !== 'all' ? ` avec statut "${filterStat}"` : ''}.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {visible.map((a, i) => {
              const st = STATUS_STYLE[a.status] || STATUS_STYLE.skipped
              return (
                <div key={a.id} className="obs-action-row" style={{ '--obs-border': st.border }}>
                  {/* Indicateur statut */}
                  <div style={{
                    flexShrink: 0, width: 22, height: 22, borderRadius: 6,
                    background: st.bg, border: `1px solid ${st.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.72rem', fontWeight: 700, color: st.color,
                  }}>{st.label}</div>

                  {/* Contenu */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#a78bfa', flexShrink: 0 }}>{a.agent}</span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>·</span>
                      <span style={{ fontSize: '0.72rem', color: '#38bdf8' }}>{a.action_type}</span>
                    </div>
                    {a.description && (
                      <div style={{
                        fontSize: '0.78rem', color: 'var(--text2)', lineHeight: 1.35,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        maxWidth: '100%',
                      }} title={a.description}>{a.description}</div>
                    )}
                  </div>

                  {/* Date */}
                  <div style={{ flexShrink: 0, fontSize: '0.67rem', color: 'var(--text3)', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {timeAgo(a.executed_at)}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── ONGLET RAPPORT ────────────────────────────── */
function TabReport({ period }) {
  const [report,  setReport]  = useState('')
  const [loading, setLoading] = useState(false)
  const [copied,  setCopied]  = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const r = await apiFetch(`/observe/report?days=${period}`)
    if (r.ok) {
      const d = await r.json()
      setReport(d.report || '')
    }
    setLoading(false)
  }, [period])

  useEffect(() => { load() }, [load])

  const copy = () => {
    navigator.clipboard.writeText(report).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '10px 24px', borderBottom: '1px solid var(--border)', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text3)' }}>Rapport sur {period} jours</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button className="mem-add-btn" onClick={copy} disabled={!report}>{copied ? '✅ Copié' : '📋 Copier'}</button>
          <button className="mem-add-btn" onClick={load} disabled={loading}>{loading ? '⏳' : '↺ Regénérer'}</button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '18px 24px' }}>
        {loading ? (
          <div className="mem-empty"><div className="mem-empty-icon">⏳</div><div>Génération du rapport…</div></div>
        ) : report ? (
          <pre className="obs-report-pre">{report}</pre>
        ) : (
          <div className="mem-empty"><div className="mem-empty-icon">📄</div><div>Aucun rapport disponible.</div></div>
        )}
      </div>
    </div>
  )
}

/* ──────────────────────────── COMPOSANT PRINCIPAL ───────────────────────── */
export default function ObserveView() {
  const [tab,    setTab]    = useState('health')
  const [period, setPeriod] = useState(7)

  return (
    <div className="memory-view">
      <div className="memory-header">
        <div className="memory-title">🔭 Observe</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {TABS.map(t => (
            <button key={t.id}
              className={tab === t.id ? 'mem-tab-btn active' : 'mem-tab-btn'}
              onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'health'  && <TabHealth period={period} onPeriodChange={setPeriod} />}
        {tab === 'actions' && <TabActions />}
        {tab === 'report'  && <TabReport period={period} />}
      </div>
    </div>
  )
}
