import { useState, useEffect } from 'react'

const BASE = '/api/soc'
const f = url => fetch(url).then(r => r.json()).catch(() => ({}))

// ── Badges sévérité ─────────────────────────────────────────────────────────
const SEV_ICON  = { CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🟢' }
const SEV_COLOR = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#34d399' }
const STAT_ICONS= { NEW: '🔵', ACKNOWLEDGED: '🟣', IN_PROGRESS: '🔄', RESOLVED: '✅', FALSE_POSITIVE: '⚪', OPEN: '🔴', INVESTIGATING: '🟠', CONTAINED: '🟡', CLOSED: '⚫' }

function Badge({ text, color }) {
  return (
    <span style={{
      fontSize: '0.65rem', fontWeight: 700, padding: '2px 7px',
      borderRadius: 5, background: `${color}22`,
      border: `1px solid ${color}55`, color, letterSpacing: '0.04em',
    }}>{text}</span>
  )
}

// ── Dashboard ────────────────────────────────────────────────────────────────
function Dashboard({ onTab }) {
  const [data, setData] = useState(null)
  useEffect(() => { f(`${BASE}/dashboard`).then(setData) }, [])
  if (!data) return <div className="soc-loading">Chargement…</div>

  const a = data.alerts || {}
  const i = data.incidents || {}
  const m = data.mitre || {}

  return (
    <div className="soc-dashboard">
      <div className="soc-cards">
        <button className="soc-stat-card critical" onClick={() => onTab('alerts')}>
          <div className="soc-stat-val">{a.critical_open || 0}</div>
          <div className="soc-stat-label">Alertes CRITICAL</div>
        </button>
        <button className="soc-stat-card high" onClick={() => onTab('alerts')}>
          <div className="soc-stat-val">{(a.by_severity?.HIGH || 0) + (a.by_severity?.CRITICAL || 0)}</div>
          <div className="soc-stat-label">Alertes HIGH+ (24h)</div>
        </button>
        <button className="soc-stat-card incident" onClick={() => onTab('incidents')}>
          <div className="soc-stat-val">{i.open || 0}</div>
          <div className="soc-stat-label">Incidents ouverts</div>
        </button>
        <button className="soc-stat-card mitre" onClick={() => onTab('mitre')}>
          <div className="soc-stat-val">{m.coverage_pct || 0}%</div>
          <div className="soc-stat-label">Couverture MITRE</div>
        </button>
      </div>

      <div className="soc-row">
        <div className="soc-panel">
          <div className="soc-panel-title">Alertes par sévérité (24h)</div>
          {Object.entries(a.by_severity || {}).map(([sev, count]) => (
            <div key={sev} className="soc-bar-row">
              <span className="soc-bar-label">{SEV_ICON[sev]} {sev}</span>
              <div className="soc-bar-track">
                <div className="soc-bar-fill"
                  style={{ width: `${Math.min(100, (count / (a.total || 1)) * 100)}%`,
                           background: SEV_COLOR[sev] || '#7c3aed' }} />
              </div>
              <span className="soc-bar-count">{count}</span>
            </div>
          ))}
        </div>
        <div className="soc-panel">
          <div className="soc-panel-title">Statuts incidents</div>
          {Object.entries(i.by_status || {}).map(([st, count]) => count > 0 && (
            <div key={st} className="soc-bar-row">
              <span className="soc-bar-label">{STAT_ICONS[st] || '○'} {st}</span>
              <span className="soc-bar-count">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="soc-row">
        <div className="soc-panel">
          <div className="soc-panel-title">SIEM — {data.siem?.rules || 0} règles actives</div>
          <div className="soc-sub">Corrélation en temps réel · Sigma-like rules</div>
          <button className="soc-link-btn" onClick={() => onTab('siem')}>Voir les événements →</button>
        </div>
        <div className="soc-panel">
          <div className="soc-panel-title">SOAR — {data.soar?.playbooks || 0} playbooks</div>
          <div className="soc-sub">Réponse automatisée · Brute Force · Intrusion · Ransomware</div>
          <button className="soc-link-btn" onClick={() => onTab('soar')}>Voir les playbooks →</button>
        </div>
      </div>
    </div>
  )
}

// ── Alertes ──────────────────────────────────────────────────────────────────
function Alerts() {
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState({ severity: '', status: 'NEW' })

  const load = () => {
    const params = new URLSearchParams()
    if (filter.severity) params.set('severity', filter.severity)
    if (filter.status)   params.set('status', filter.status)
    f(`${BASE}/alerts?${params}&per_page=30`).then(setData)
  }
  useEffect(load, [filter])

  return (
    <div className="soc-section">
      <div className="soc-filters">
        <select className="soc-select" value={filter.severity} onChange={e => setFilter(p => ({...p, severity: e.target.value}))}>
          <option value="">Toutes sévérités</option>
          {['CRITICAL','HIGH','MEDIUM','LOW'].map(s => <option key={s} value={s}>{SEV_ICON[s]} {s}</option>)}
        </select>
        <select className="soc-select" value={filter.status} onChange={e => setFilter(p => ({...p, status: e.target.value}))}>
          <option value="">Tous statuts</option>
          {['NEW','ACKNOWLEDGED','IN_PROGRESS','RESOLVED','FALSE_POSITIVE'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {!data ? <div className="soc-loading">Chargement…</div> : (
        <div className="soc-table">
          <div className="soc-table-header">
            <span>Sévérité</span><span>Catégorie</span><span>Titre</span>
            <span>Source IP</span><span>Statut</span><span>Date</span>
          </div>
          {(data.alerts || []).map(a => (
            <div key={a.id} className="soc-table-row">
              <span><Badge text={a.severity} color={SEV_COLOR[a.severity] || '#7c3aed'} /></span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text2)' }}>{a.category}</span>
              <span style={{ fontSize: '0.8rem' }}>{a.title}</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'monospace', color: 'var(--elec)' }}>{a.source_ip || '—'}</span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{a.status}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                {a.timestamp ? new Date(a.timestamp).toLocaleString('fr-FR') : '—'}
              </span>
            </div>
          ))}
          {(!data.alerts?.length) && <div className="soc-empty">Aucune alerte</div>}
        </div>
      )}
    </div>
  )
}

// ── Incidents ─────────────────────────────────────────────────────────────────
function Incidents() {
  const [data, setData] = useState(null)
  useEffect(() => { f(`${BASE}/incidents?per_page=20`).then(setData) }, [])

  return (
    <div className="soc-section">
      {!data ? <div className="soc-loading">Chargement…</div> : (
        <div className="soc-table">
          <div className="soc-table-header">
            <span>Sévérité</span><span>Titre</span><span>Statut</span><span>Priorité</span><span>Ouvert le</span>
          </div>
          {(data.incidents || []).map(i => (
            <div key={i.id} className="soc-table-row">
              <span><Badge text={i.severity} color={SEV_COLOR[i.severity] || '#7c3aed'} /></span>
              <span style={{ fontSize: '0.8rem' }}>{i.title}</span>
              <span style={{ fontSize: '0.68rem' }}>{STAT_ICONS[i.status]} {i.status}</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text2)' }}>P{i.priority}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                {i.opened_at ? new Date(i.opened_at).toLocaleDateString('fr-FR') : '—'}
              </span>
            </div>
          ))}
          {(!data.incidents?.length) && <div className="soc-empty">Aucun incident</div>}
        </div>
      )}
    </div>
  )
}

// ── SIEM ─────────────────────────────────────────────────────────────────────
function Siem() {
  const [rules, setRules] = useState(null)
  useEffect(() => { f(`${BASE}/siem/rules`).then(d => setRules(d.rules)) }, [])

  return (
    <div className="soc-section">
      <div className="soc-panel-title" style={{ marginBottom: 12 }}>Règles de corrélation SIEM</div>
      {!rules ? <div className="soc-loading">Chargement…</div> : (
        <div className="soc-rule-list">
          {rules.map(r => (
            <div key={r.id} className={`soc-rule-card ${r.enabled ? '' : 'disabled'}`}>
              <div className="soc-rule-header">
                <span className="soc-rule-name">{r.name}</span>
                <Badge text={r.severity} color={SEV_COLOR[r.severity] || '#7c3aed'} />
              </div>
              <div className="soc-rule-meta">
                <span>{r.rule_type}</span>
                {r.mitre_tactic && <span className="soc-mitre-tag">{r.mitre_tactic} / {r.mitre_technique}</span>}
                <span>hits: {r.hit_count || 0}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── SOAR Playbooks ────────────────────────────────────────────────────────────
function Soar() {
  const [pbs, setPbs] = useState(null)
  useEffect(() => { f(`${BASE}/soar/playbooks`).then(d => setPbs(d.playbooks)) }, [])

  return (
    <div className="soc-section">
      {!pbs ? <div className="soc-loading">Chargement…</div> : (
        <div className="soc-pb-list">
          {pbs.map(pb => (
            <div key={pb.id} className="soc-pb-card">
              <div className="soc-pb-header">
                <span className="soc-pb-name">{pb.name}</span>
                <span className="soc-pb-duration">{pb.estimated_duration}</span>
              </div>
              <div className="soc-pb-cats">
                {pb.attack_categories.map(c => <span key={c} className="soc-cat-tag">{c}</span>)}
              </div>
              <div className="soc-pb-impact">
                Impact évité : <strong>${pb.financial_impact_usd.toLocaleString()}</strong>
                <span className="soc-pb-src"> — {pb.financial_source?.split('—')[0]}</span>
              </div>
              <div className="soc-pb-steps">
                {pb.steps.map(s => (
                  <div key={s.order} className="soc-step">
                    <span className="soc-step-n">{s.order}</span>
                    <span className="soc-step-action">{s.action}</span>
                    <span className="soc-step-desc">{s.description}</span>
                    {s.auto_execute && <span className="soc-auto-badge">auto</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── MITRE ATT&CK ─────────────────────────────────────────────────────────────
function Mitre() {
  const [coverage, setCoverage] = useState(null)
  const [stats, setStats]       = useState(null)
  const [search, setSearch]     = useState('')
  const [results, setResults]   = useState(null)

  useEffect(() => {
    f(`${BASE}/mitre/coverage`).then(setCoverage)
    f(`${BASE}/mitre/stats`).then(setStats)
  }, [])

  const doSearch = async () => {
    const data = await fetch(`${BASE}/mitre/search`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: search }),
    }).then(r => r.json())
    setResults(data.results || [])
  }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-mitre-stats">
          <strong>ATT&CK Enterprise v14</strong> — {stats.total_techniques} techniques,{' '}
          {stats.techniques_covered} couvertes ({stats.coverage_pct}%)
        </div>
      )}

      <div className="soc-search-bar">
        <input className="soc-input" placeholder="Rechercher technique… (ex: brute force, T1110, pivot)"
          value={search} onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()} />
        <button className="soc-search-btn" onClick={doSearch}>Rechercher</button>
      </div>

      {results && (
        <div className="soc-rule-list">
          {results.map(t => (
            <div key={t.id} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-mitre-id">{t.id}</span>
                <span className="soc-rule-name">{t.name}</span>
                <Badge text={t.severity} color={SEV_COLOR[t.severity?.toUpperCase()] || '#7c3aed'} />
              </div>
              <div className="soc-rule-meta">
                <span>{t.tactic_name}</span>
                {t.tools?.length > 0 && <span>Outils : {t.tools.join(', ')}</span>}
              </div>
            </div>
          ))}
          {results.length === 0 && <div className="soc-empty">Aucun résultat</div>}
        </div>
      )}

      {!results && coverage && (
        <div className="soc-cov-grid">
          {Object.values(coverage).map(d => (
            <div key={d.tactic} className="soc-cov-row">
              <span className="soc-cov-name">{d.tactic}</span>
              <div className="soc-bar-track" style={{ flex: 1 }}>
                <div className="soc-bar-fill"
                  style={{ width: `${d.pct}%`,
                           background: d.pct > 70 ? '#34d399' : d.pct > 30 ? '#eab308' : '#ef4444' }} />
              </div>
              <span className="soc-cov-pct">{d.covered}/{d.total}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Vue principale SOC ────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'alerts',    label: '🔴 Alertes'   },
  { id: 'incidents', label: '🚨 Incidents'  },
  { id: 'siem',      label: '⚙️ SIEM'      },
  { id: 'soar',      label: '🤖 SOAR'      },
  { id: 'mitre',     label: '🗺️ MITRE'     },
]

export default function SocView() {
  const [tab, setTab] = useState('dashboard')

  return (
    <div className="soc-view">
      <div className="soc-header">
        <div className="soc-title">🔴 SOC — Centre Opérationnel de Sécurité</div>
        <div className="soc-tabs">
          {TABS.map(t => (
            <button key={t.id}
              className={`soc-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="soc-content">
        {tab === 'dashboard' && <Dashboard onTab={setTab} />}
        {tab === 'alerts'    && <Alerts />}
        {tab === 'incidents' && <Incidents />}
        {tab === 'siem'      && <Siem />}
        {tab === 'soar'      && <Soar />}
        {tab === 'mitre'     && <Mitre />}
      </div>
    </div>
  )
}
