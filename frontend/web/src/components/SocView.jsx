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
// ── ML Anomaly ───────────────────────────────────────────────────────────────
function MlAnomaly() {
  const [stats, setStats] = useState(null)
  const [anomalies, setAnomalies] = useState(null)
  const [training, setTraining] = useState(false)

  useEffect(() => {
    f(`${BASE}/ml/stats`).then(setStats)
    f(`${BASE}/ml/anomalies?hours=168`).then(setAnomalies)
  }, [])

  const train = async () => {
    setTraining(true)
    const r = await fetch(`${BASE}/ml/train`, { method: 'POST' }).then(r => r.json()).catch(() => ({}))
    setTraining(false)
    f(`${BASE}/ml/stats`).then(setStats)
    f(`${BASE}/ml/anomalies?hours=168`).then(setAnomalies)
  }

  return (
    <div className="soc-section">
      <div className="soc-row">
        <div className="soc-panel">
          <div className="soc-panel-title">Statut ML</div>
          {stats && <>
            <div className="soc-bar-row">
              <span className="soc-bar-label">Entraîné</span>
              <span className="soc-bar-count">{stats.trained ? '✅ Oui' : '❌ Non'}</span>
            </div>
            <div className="soc-bar-row">
              <span className="soc-bar-label">Total anomalies</span>
              <span className="soc-bar-count">{stats.total_anomalies}</span>
            </div>
            <div className="soc-bar-row">
              <span className="soc-bar-label">CRITICAL</span>
              <span className="soc-bar-count" style={{ color: '#ef4444' }}>{stats.critical}</span>
            </div>
          </>}
          <button className="soc-link-btn" onClick={train} disabled={training} style={{ marginTop: 10 }}>
            {training ? '⏳ Entraînement…' : '🧠 Entraîner le modèle'}
          </button>
        </div>
        <div className="soc-panel">
          <div className="soc-panel-title">Algorithmes</div>
          <div className="soc-sub">K-Means (k=5) — clustering comportemental</div>
          <div className="soc-sub">Isolation Forest — détection anomalies</div>
          <div className="soc-sub">Score 0–100 · Seuil anomalie : 70</div>
        </div>
      </div>
      {anomalies && anomalies.anomalies?.length > 0 && (
        <div className="soc-rule-list">
          <div className="soc-panel-title" style={{ marginBottom: 8 }}>Anomalies détectées ({anomalies.total})</div>
          {anomalies.anomalies.slice(0, 10).map(a => (
            <div key={a.id} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-rule-name">{a.cluster}</span>
                <Badge text={a.severity} color={SEV_COLOR[a.severity] || '#7c3aed'} />
                <span style={{ fontSize: '0.75rem', color: 'var(--elec)', fontWeight: 700 }}>{a.score.toFixed(0)}/100</span>
              </div>
              <div className="soc-rule-meta"><span>{a.explanation}</span></div>
            </div>
          ))}
        </div>
      )}
      {(!anomalies || anomalies.anomalies?.length === 0) && (
        <div className="soc-empty">Aucune anomalie détectée — Lance l'entraînement avec des alertes en base.</div>
      )}
    </div>
  )
}

// ── EDR ───────────────────────────────────────────────────────────────────────
function Edr() {
  const [agents, setAgents] = useState(null)
  const [events, setEvents] = useState(null)
  const [stats, setStats]   = useState(null)

  useEffect(() => {
    f(`${BASE}/edr/agents`).then(setAgents)
    f(`${BASE}/edr/events?hours=24`).then(setEvents)
    f(`${BASE}/edr/stats`).then(setStats)
  }, [])

  const STATUS_COLOR = { online: '#34d399', compromised: '#ef4444', isolated: '#f97316', offline: '#64748b' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <div className="soc-stat-card high">
            <div className="soc-stat-val">{stats.total_agents}</div>
            <div className="soc-stat-label">Agents EDR</div>
          </div>
          <div className="soc-stat-card critical">
            <div className="soc-stat-val">{stats.compromised}</div>
            <div className="soc-stat-label">Compromis</div>
          </div>
          <div className="soc-stat-card incident">
            <div className="soc-stat-val">{stats.events_24h}</div>
            <div className="soc-stat-label">Événements 24h</div>
          </div>
        </div>
      )}

      {agents && agents.agents?.length > 0 && (
        <div>
          <div className="soc-panel-title" style={{ margin: '12px 0 8px' }}>Endpoints ({agents.total})</div>
          <div className="soc-table">
            <div className="soc-table-header" style={{ gridTemplateColumns: '1fr 100px 80px 60px' }}>
              <span>Hostname</span><span>IP</span><span>OS</span><span>Risk</span>
            </div>
            {agents.agents.slice(0, 10).map(a => (
              <div key={a.id} className="soc-table-row" style={{ gridTemplateColumns: '1fr 100px 80px 60px' }}>
                <span style={{ fontWeight: 600 }}>
                  <span style={{ color: STATUS_COLOR[a.status] || '#64748b', marginRight: 6 }}>●</span>
                  {a.hostname}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: 'var(--elec)' }}>{a.ip || '—'}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text2)' }}>{a.os?.split(' ')[0] || '—'}</span>
                <span style={{ color: a.risk_score >= 70 ? '#ef4444' : a.risk_score >= 40 ? '#f97316' : '#34d399', fontWeight: 700 }}>
                  {a.risk_score?.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── NTA ───────────────────────────────────────────────────────────────────────
function Nta() {
  const [stats, setStats]   = useState(null)
  const [flows, setFlows]   = useState(null)
  const [beaconing, setBeac]= useState(null)

  useEffect(() => {
    f(`${BASE}/nta/stats`).then(setStats)
    f(`${BASE}/nta/flows?threat_only=true`).then(setFlows)
    f(`${BASE}/nta/beaconing`).then(d => setBeac(d.beaconing || []))
  }, [])

  const THREAT_COLOR = { C2: '#ef4444', EXFILTRATION: '#f97316', BEACONING: '#eab308',
                         DNS_TUNNEL: '#8b5cf6', IRC_C2: '#ef4444', FTP_EXFIL: '#f97316' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-row">
          <div className="soc-panel">
            <div className="soc-panel-title">Trafic réseau (24h)</div>
            {[['Total flux', stats.total_flows, 'var(--text)'],
              ['Flux suspects', stats.threat_flows, '#f97316'],
              ['C2 détectés', stats.c2_flows, '#ef4444'],
              ['Exfiltrations', stats.exfil_flows, '#f97316'],
              ['Haut risque', stats.high_risk, '#ef4444']
            ].map(([label, val, color]) => (
              <div key={label} className="soc-bar-row">
                <span className="soc-bar-label">{label}</span>
                <span className="soc-bar-count" style={{ color }}>{val}</span>
              </div>
            ))}
          </div>
          <div className="soc-panel">
            <div className="soc-panel-title">Top IPs menaçantes</div>
            {stats.top_threat_ips?.length > 0 ? stats.top_threat_ips.map(t => (
              <div key={t.ip} className="soc-bar-row">
                <span className="soc-bar-label" style={{ fontFamily: 'monospace', color: 'var(--elec)' }}>{t.ip}</span>
                <span className="soc-bar-count">{t.count} flux</span>
              </div>
            )) : <div className="soc-empty" style={{ padding: '8px 0' }}>Aucune IP suspecte</div>}
          </div>
        </div>
      )}

      {beaconing?.length > 0 && (
        <div>
          <div className="soc-panel-title" style={{ margin: '12px 0 8px' }}>🔔 Beaconing détecté</div>
          <div className="soc-rule-list">
            {beaconing.map((b, i) => (
              <div key={i} className="soc-rule-card">
                <div className="soc-rule-meta">
                  <span style={{ fontFamily: 'monospace', color: 'var(--elec)' }}>{b.src_ip}</span>
                  <span>→</span>
                  <span style={{ fontFamily: 'monospace' }}>{b.dst_ip}</span>
                  <span>{b.flow_count} connexions</span>
                  <Badge text="BEACONING" color="#eab308" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Threat Intel ──────────────────────────────────────────────────────────────
function ThreatIntel() {
  const [stats, setStats] = useState(null)
  const [iocs, setIocs]   = useState(null)
  const [check, setCheck] = useState('')
  const [checkResult, setCheckResult] = useState(null)

  useEffect(() => {
    f(`${BASE}/threat-intel/stats`).then(setStats)
    f(`${BASE}/threat-intel/iocs?per_page=20`).then(setIocs)
  }, [])

  const doCheck = () => {
    const isIp = /^\d+\.\d+\.\d+\.\d+$/.test(check)
    const url  = isIp ? `${BASE}/threat-intel/check/ip/${check}` : `${BASE}/threat-intel/check/domain/${check}`
    f(url).then(setCheckResult)
  }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <div className="soc-stat-card high">
            <div className="soc-stat-val">{stats.total_iocs}</div>
            <div className="soc-stat-label">IOCs actifs</div>
          </div>
          <div className="soc-stat-card critical">
            <div className="soc-stat-val">{stats.critical_iocs}</div>
            <div className="soc-stat-label">IOCs CRITICAL</div>
          </div>
          <div className="soc-stat-card incident">
            <div className="soc-stat-val">{stats.total_hits}</div>
            <div className="soc-stat-label">Hits totaux</div>
          </div>
        </div>
      )}

      <div className="soc-search-bar">
        <input className="soc-input" placeholder="Vérifier une IP ou domaine (ex: 45.33.32.156)"
          value={check} onChange={e => setCheck(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doCheck()} />
        <button className="soc-search-btn" onClick={doCheck}>Vérifier</button>
      </div>

      {checkResult && (
        <div className="soc-rule-card" style={{ marginBottom: 12 }}>
          {checkResult.status === 'clean' ? (
            <div style={{ color: '#34d399' }}>✅ Propre — non présent dans la base IOC</div>
          ) : (
            <>
              <div className="soc-rule-header">
                <span className="soc-rule-name">{checkResult.value}</span>
                <Badge text={checkResult.severity} color={SEV_COLOR[checkResult.severity] || '#7c3aed'} />
                <span style={{ color: '#f97316', fontSize: '0.75rem' }}>{checkResult.threat_type}</span>
              </div>
              <div className="soc-rule-meta">
                <span>Confiance: {checkResult.confidence}%</span>
                <span>Source: {checkResult.source}</span>
                <span>{checkResult.description}</span>
              </div>
            </>
          )}
        </div>
      )}

      {iocs && (
        <div className="soc-rule-list">
          {iocs.iocs?.slice(0, 12).map(i => (
            <div key={i.id} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-mitre-id">{i.type}</span>
                <span className="soc-rule-name" style={{ fontFamily: i.type?.includes('HASH') ? 'monospace' : 'inherit', fontSize: i.type?.includes('HASH') ? '0.7rem' : '0.82rem' }}>{i.value}</span>
                <Badge text={i.severity} color={SEV_COLOR[i.severity] || '#7c3aed'} />
              </div>
              <div className="soc-rule-meta">
                <span>{i.threat_type}</span>
                <span>Conf: {i.confidence}%</span>
                <span>{i.source}</span>
                <span>{i.description}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── IDS ───────────────────────────────────────────────────────────────────────
function Ids() {
  const [sigs, setSigs] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    f(`${BASE}/ids/signatures`).then(d => setSigs(d.signatures))
    f(`${BASE}/ids/stats`).then(setStats)
  }, [])

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-panel" style={{ marginBottom: 12 }}>
          <div className="soc-bar-row">
            <span className="soc-bar-label">Signatures actives</span>
            <span className="soc-bar-count">{stats.total_signatures}</span>
          </div>
          <div className="soc-bar-row">
            <span className="soc-bar-label">Alertes IDS (24h)</span>
            <span className="soc-bar-count">{stats.ids_alerts_24h}</span>
          </div>
        </div>
      )}
      {sigs && (
        <div className="soc-rule-list">
          {sigs.map(s => (
            <div key={s.sid} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-mitre-id">SID:{s.sid}</span>
                <span className="soc-rule-name">{s.name}</span>
                <Badge text={s.severity} color={SEV_COLOR[s.severity] || '#7c3aed'} />
              </div>
              <div className="soc-rule-meta">
                <span>{s.description}</span>
                <span>{s.mitre_tactic}/{s.mitre_tech}</span>
                <span>seuil: {s.threshold}×/{s.window_s}s</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── DLP ───────────────────────────────────────────────────────────────────────
function Dlp() {
  const [stats, setStats]   = useState(null)
  const [policies, setPolicies] = useState(null)
  const [scan, setScan]     = useState('')
  const [result, setResult] = useState(null)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    f(`${BASE}/dlp/stats`).then(setStats)
    f(`${BASE}/dlp/policies`).then(d => setPolicies(d.policies))
  }, [])

  const doScan = async () => {
    if (!scan.trim()) return
    setScanning(true)
    const r = await fetch(`${BASE}/dlp/scan`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: scan, source: 'ui-manual', channel: 'MANUAL' }),
    }).then(r => r.json()).catch(() => ({}))
    setResult(r)
    setScanning(false)
    f(`${BASE}/dlp/stats`).then(setStats)
  }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.critical}</div><div className="soc-stat-label">Incidents CRITICAL</div></div>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.open}</div><div className="soc-stat-label">Ouverts</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.total}</div><div className="soc-stat-label">Total incidents</div></div>
        </div>
      )}

      <div className="soc-panel" style={{ marginBottom: 12 }}>
        <div className="soc-panel-title">Scanner un texte pour données sensibles</div>
        <textarea className="soc-input" rows={4} style={{ width: '100%', resize: 'vertical', marginBottom: 8 }}
          placeholder="Colle un texte, log ou code à analyser (API keys, IBAN, SSN, emails, mots de passe…)"
          value={scan} onChange={e => setScan(e.target.value)} />
        <button className="soc-search-btn" onClick={doScan} disabled={scanning}>
          {scanning ? '⏳ Scan…' : '🔍 Scanner'}
        </button>
      </div>

      {result && (
        <div className="soc-rule-list" style={{ marginBottom: 12 }}>
          <div className="soc-panel-title">
            {result.total > 0 ? `⚠️ ${result.total} violation(s) détectée(s)` : '✅ Aucune donnée sensible détectée'}
          </div>
          {result.findings?.map((f, i) => (
            <div key={i} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-rule-name">{f.label}</span>
                <Badge text={f.severity} color={SEV_COLOR[f.severity] || '#7c3aed'} />
                <span className="soc-mitre-tag">{f.mitre}</span>
              </div>
              <div className="soc-rule-meta">
                <span>{f.count} occurrence(s)</span>
                <span style={{ fontFamily: 'monospace', color: '#f87171' }}>{f.snippet}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {policies && (
        <div className="soc-rule-list">
          <div className="soc-panel-title" style={{ marginBottom: 8 }}>{policies.length} politiques DLP</div>
          {policies.map(p => (
            <div key={p.name} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-rule-name">{p.label}</span>
                <Badge text={p.severity} color={SEV_COLOR[p.severity] || '#7c3aed'} />
                <span className="soc-mitre-tag">{p.mitre}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── RANSOMWARE ────────────────────────────────────────────────────────────────
function Ransomware() {
  const [families, setFamilies] = useState(null)
  const [stats, setStats]       = useState(null)
  const [indicators, setInds]   = useState(null)

  useEffect(() => {
    f(`${BASE}/ransomware/families`).then(d => setFamilies(d.families))
    f(`${BASE}/ransomware/stats`).then(setStats)
    f(`${BASE}/ransomware/indicators`).then(d => setInds(d.indicators))
  }, [])

  const THREAT_COLOR = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.active}</div><div className="soc-stat-label">Détections actives</div></div>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.known_families}</div><div className="soc-stat-label">Familles connues</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.behavioral_indicators}</div><div className="soc-stat-label">Indicateurs comportementaux</div></div>
        </div>
      )}

      {families && (
        <div className="soc-rule-list" style={{ marginBottom: 16 }}>
          <div className="soc-panel-title" style={{ marginBottom: 8 }}>Familles de ransomwares connus</div>
          {families.map(fam => (
            <div key={fam.name} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-rule-name">{fam.name}</span>
                {fam.aka && <span style={{ fontSize: '0.72rem', color: 'var(--text2)' }}>alias: {fam.aka}</span>}
                <Badge text={fam.threat_level} color={THREAT_COLOR[fam.threat_level] || '#7c3aed'} />
                <span style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{fam.known_victims}+ victimes</span>
              </div>
              <div className="soc-rule-meta">
                <span>{fam.encryption}</span>
                <span style={{ fontFamily: 'monospace', color: 'var(--elec)' }}>{fam.extension}</span>
                <span>Dwell: {fam.avg_dwell_days}j</span>
                <span style={{ color: '#34d399' }}>depuis {fam.first_seen}</span>
              </div>
              <div style={{ fontSize: '0.73rem', color: 'var(--text2)', marginTop: 4, paddingLeft: 4 }}>
                {fam.description}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── PHISHING ──────────────────────────────────────────────────────────────────
function Phishing() {
  const [stats, setStats]     = useState(null)
  const [indicators, setInds] = useState(null)
  const [form, setForm]       = useState({ sender: '', subject: '', body: '' })
  const [result, setResult]   = useState(null)
  const [analyzing, setAn]    = useState(false)

  useEffect(() => {
    f(`${BASE}/phishing/stats`).then(setStats)
    f(`${BASE}/phishing/indicators`).then(d => setInds(d.indicators))
  }, [])

  const analyze = async () => {
    if (!form.sender) return
    setAn(true)
    const r = await fetch(`${BASE}/phishing/analyze`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    }).then(r => r.json()).catch(() => ({}))
    setResult(r)
    setAn(false)
  }

  const VERDICT_COLOR = { PHISHING: '#ef4444', BEC: '#f97316', SUSPICIOUS: '#eab308', CLEAN: '#34d399' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.phishing}</div><div className="soc-stat-label">Emails phishing</div></div>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.bec}</div><div className="soc-stat-label">BEC détectés</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.total}</div><div className="soc-stat-label">Emails analysés</div></div>
        </div>
      )}

      <div className="soc-panel" style={{ marginBottom: 12 }}>
        <div className="soc-panel-title">Analyser un email</div>
        {['sender', 'subject', 'body'].map(field => (
          <div key={field} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 3 }}>
              {field === 'sender' ? 'Expéditeur' : field === 'subject' ? 'Objet' : 'Corps (optionnel)'}
            </div>
            {field === 'body' ? (
              <textarea className="soc-input" rows={3} style={{ width: '100%', resize: 'vertical' }}
                value={form[field]} onChange={e => setForm(p => ({...p, [field]: e.target.value}))} />
            ) : (
              <input className="soc-input" style={{ width: '100%' }}
                value={form[field]} onChange={e => setForm(p => ({...p, [field]: e.target.value}))}
                placeholder={field === 'sender' ? 'ex: ceo@company-secure.xyz' : 'ex: Urgent - Virement requis'} />
            )}
          </div>
        ))}
        <button className="soc-search-btn" onClick={analyze} disabled={analyzing || !form.sender}>
          {analyzing ? '⏳ Analyse…' : '🔍 Analyser'}
        </button>
      </div>

      {result && (
        <div className="soc-rule-card" style={{ marginBottom: 12, borderLeft: `3px solid ${VERDICT_COLOR[result.verdict] || '#7c3aed'}` }}>
          <div className="soc-rule-header">
            <span className="soc-rule-name">Score : {result.score}/100</span>
            <Badge text={result.verdict || 'CLEAN'} color={VERDICT_COLOR[result.verdict] || '#34d399'} />
            <span style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
              SPF:{result.spf} DKIM:{result.dkim} DMARC:{result.dmarc}
            </span>
          </div>
          {result.indicators_detail?.map(ind => (
            <div key={ind.code} className="soc-rule-meta" style={{ marginTop: 4 }}>
              <span>⚠️ {ind.label}</span>
              <span style={{ color: '#f97316' }}>+{ind.score}pts</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── OSINT APT ─────────────────────────────────────────────────────────────────
function Osint() {
  const [actors, setActors]   = useState(null)
  const [stats, setStats]     = useState(null)
  const [search, setSearch]   = useState('')
  const [results, setResults] = useState(null)

  useEffect(() => {
    f(`${BASE}/osint/stats`).then(setStats)
    f(`${BASE}/osint/actors`).then(setActors)
  }, [])

  const doSearch = async () => {
    const r = await fetch(`${BASE}/osint/search`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: search }),
    }).then(r => r.json()).catch(() => ({}))
    setResults(r.results || [])
  }

  const SPONSOR_COLOR = { STATE: '#ef4444', CRIMINAL: '#f97316', HACKTIVISM: '#eab308', UNKNOWN: '#64748b' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.active_actors}</div><div className="soc-stat-label">Groupes APT actifs</div></div>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.total_actors}</div><div className="soc-stat-label">Acteurs total</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.investigations}</div><div className="soc-stat-label">Investigations</div></div>
        </div>
      )}

      <div className="soc-search-bar">
        <input className="soc-input"
          placeholder="Rechercher un groupe (ex: APT28, Fancy Bear, Russie, ransomware…)"
          value={search} onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()} />
        <button className="soc-search-btn" onClick={doSearch}>Rechercher</button>
      </div>

      <div className="soc-rule-list">
        {(results || actors?.actors || []).map(a => (
          <div key={a.id || a.name} className="soc-rule-card">
            <div className="soc-rule-header">
              <span className="soc-rule-name">{a.name}</span>
              <Badge text={a.threat_level} color={SEV_COLOR[a.threat_level] || '#7c3aed'} />
              {a.sponsor && <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: 4,
                background: `${SPONSOR_COLOR[a.sponsor] || '#64748b'}22`,
                color: SPONSOR_COLOR[a.sponsor] || '#64748b', border: `1px solid ${SPONSOR_COLOR[a.sponsor] || '#64748b'}44` }}>
                {a.sponsor}
              </span>}
              <span style={{ fontSize: '0.68rem', color: a.is_active ? '#34d399' : '#64748b' }}>
                {a.is_active ? '● actif' : '● inactif'}
              </span>
            </div>
            <div className="soc-rule-meta">
              <span>{a.country}</span>
              {a.aliases?.slice(0,2).map(al => <span key={al} style={{ color: 'var(--text3)' }}>{al}</span>)}
              <span>{a.target_sectors?.slice(0,3).join(', ')}</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text2)', marginTop: 4, paddingLeft: 4, lineHeight: 1.4 }}>
              {a.description?.slice(0, 120)}{a.description?.length > 120 ? '…' : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── IAM ───────────────────────────────────────────────────────────────────────
function Iam() {
  const [stats, setStats] = useState(null)
  const [accounts, setAccounts] = useState(null)
  const [mfa, setMfa] = useState(null)

  useEffect(() => {
    f(`${BASE}/iam/stats`).then(setStats)
    f(`${BASE}/iam/accounts?risk_min=50`).then(setAccounts)
    f(`${BASE}/iam/mfa-audit`).then(setMfa)
  }, [])

  const RISK_COLOR = s => s >= 80 ? '#ef4444' : s >= 60 ? '#f97316' : s >= 40 ? '#eab308' : '#34d399'
  const TYPE_ICON  = { ADMIN: '👑', SERVICE: '⚙️', SHARED: '👥', USER: '👤' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.high_risk}</div><div className="soc-stat-label">Comptes à risque</div></div>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.no_mfa}</div><div className="soc-stat-label">Sans MFA</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.dormant}</div><div className="soc-stat-label">Dormants</div></div>
          <div className="soc-stat-card mitre"><div className="soc-stat-val">{stats.mfa_coverage_pct}%</div><div className="soc-stat-label">Couverture MFA</div></div>
        </div>
      )}

      {mfa && mfa.privileged_without_mfa?.length > 0 && (
        <div className="soc-panel" style={{ marginBottom: 12, borderLeft: '3px solid #ef4444' }}>
          <div className="soc-panel-title">⚠️ Comptes privilégiés sans MFA ({mfa.privileged_without_mfa.length})</div>
          {mfa.privileged_without_mfa.map(a => (
            <div key={a.username} className="soc-bar-row">
              <span className="soc-bar-label" style={{ color: '#ef4444' }}>{a.username}</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text2)' }}>{a.privilege_level}</span>
            </div>
          ))}
        </div>
      )}

      {accounts && accounts.accounts?.length > 0 && (
        <div>
          <div className="soc-panel-title" style={{ margin: '8px 0' }}>Comptes à risque élevé</div>
          <div className="soc-table">
            <div className="soc-table-header" style={{ gridTemplateColumns: '28px 1fr 70px 80px 60px 80px' }}>
              <span></span><span>Compte</span><span>Type</span><span>MFA</span><span>Risk</span><span>Statut</span>
            </div>
            {accounts.accounts.slice(0, 10).map(a => (
              <div key={a.id} className="soc-table-row" style={{ gridTemplateColumns: '28px 1fr 70px 80px 60px 80px' }}>
                <span>{TYPE_ICON[a.account_type] || '👤'}</span>
                <span>
                  <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>{a.username}</div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text2)' }}>{a.department}</div>
                </span>
                <span style={{ fontSize: '0.7rem' }}>{a.account_type}</span>
                <span style={{ fontSize: '0.72rem', color: a.mfa_enabled ? '#34d399' : '#ef4444' }}>
                  {a.mfa_enabled ? `✅ ${a.mfa_type || 'activé'}` : '❌ aucun'}
                </span>
                <span style={{ fontWeight: 700, color: RISK_COLOR(a.risk_score) }}>{a.risk_score?.toFixed(0)}</span>
                <span style={{ fontSize: '0.68rem', color: a.is_dormant ? '#f97316' : 'var(--text3)' }}>
                  {a.is_dormant ? '💤 dormant' : a.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── COMPLIANCE ────────────────────────────────────────────────────────────────
function Compliance() {
  const [stats, setStats]     = useState(null)
  const [controls, setControls] = useState(null)
  const [assessing, setAssessing] = useState(false)

  const load = () => {
    f(`${BASE}/compliance/stats`).then(setStats)
    f(`${BASE}/compliance/controls`).then(setControls)
  }
  useEffect(() => { load() }, [])

  const assess = async () => {
    setAssessing(true)
    await fetch(`${BASE}/compliance/assess`, { method: 'POST' })
    load()
    setAssessing(false)
  }

  const STATUS_COLOR = { PASS: '#34d399', FAIL: '#ef4444', PARTIAL: '#eab308', NOT_ASSESSED: '#64748b' }
  const STATUS_ICON  = { PASS: '✅', FAIL: '❌', PARTIAL: '⚠️', NOT_ASSESSED: '○' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-row" style={{ marginBottom: 12 }}>
          <div className="soc-panel">
            <div className="soc-panel-title">Score de conformité</div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: stats.score_pct >= 70 ? '#34d399' : stats.score_pct >= 50 ? '#eab308' : '#ef4444' }}>
              {stats.score_pct}%
            </div>
            <div className="soc-sub">{stats.framework}</div>
            {[['Passés', stats.passed, '#34d399'], ['Échoués', stats.failed, '#ef4444'],
              ['Partiels', stats.partial, '#eab308'], ['Non évalués', stats.not_assessed, '#64748b']
            ].map(([label, val, color]) => (
              <div key={label} className="soc-bar-row">
                <span className="soc-bar-label">{label}</span>
                <span className="soc-bar-count" style={{ color }}>{val}</span>
              </div>
            ))}
            <button className="soc-link-btn" onClick={assess} disabled={assessing} style={{ marginTop: 10 }}>
              {assessing ? '⏳ Évaluation…' : '▶ Lancer l\'évaluation'}
            </button>
          </div>
          <div className="soc-panel">
            <div className="soc-panel-title">Par catégorie</div>
            {Object.entries(stats.by_category || {}).map(([cat, data]) => (
              <div key={cat} className="soc-bar-row">
                <span className="soc-bar-label" style={{ fontSize: '0.68rem' }}>{cat}</span>
                <div className="soc-bar-track">
                  <div className="soc-bar-fill" style={{
                    width: `${(data.passed / (data.total || 1)) * 100}%`,
                    background: data.passed / data.total >= 0.7 ? '#34d399' : '#eab308',
                  }} />
                </div>
                <span className="soc-bar-count">{data.passed}/{data.total}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {controls && (
        <div className="soc-rule-list">
          {controls.controls?.filter(c => c.status === 'FAIL' || c.status === 'NOT_ASSESSED').slice(0, 15).map(c => (
            <div key={c.id} className="soc-rule-card">
              <div className="soc-rule-header">
                <span className="soc-mitre-id">{c.id}</span>
                <span className="soc-rule-name">{c.title}</span>
                <Badge text={c.severity} color={SEV_COLOR[c.severity] || '#7c3aed'} />
                <span style={{ fontSize: '0.7rem', color: STATUS_COLOR[c.status] }}>
                  {STATUS_ICON[c.status]} {c.status}
                </span>
              </div>
              <div className="soc-rule-meta"><span>{c.category}</span><span style={{ color: 'var(--text2)' }}>{c.requirement?.slice(0,80)}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── ZERO TRUST ────────────────────────────────────────────────────────────────
function ZeroTrust() {
  const [policies, setPolicies] = useState(null)
  const [stats, setStats]       = useState(null)
  const [form, setForm]         = useState({ user: '', source_ip: '', resource: '/' })
  const [evalResult, setEval]   = useState(null)

  useEffect(() => {
    f(`${BASE}/zero-trust/policies`).then(d => setPolicies(d.policies))
    f(`${BASE}/zero-trust/stats`).then(setStats)
  }, [])

  const evaluate = async () => {
    const r = await fetch(`${BASE}/zero-trust/evaluate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    }).then(r => r.json()).catch(() => ({}))
    setEval(r)
    f(`${BASE}/zero-trust/stats`).then(setStats)
  }

  const DECISION_COLOR = { ALLOW: '#34d399', DENY: '#ef4444', MFA_REQUIRED: '#eab308', AUDIT: '#818cf8' }
  const ACTION_COLOR   = { ALLOW: '#34d399', DENY: '#ef4444', MFA_REQUIRED: '#eab308', AUDIT: '#818cf8' }

  return (
    <div className="soc-section">
      {stats && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 12 }}>
          <div className="soc-stat-card high"><div className="soc-stat-val">{stats.active_sessions}</div><div className="soc-stat-label">Sessions actives</div></div>
          <div className="soc-stat-card critical"><div className="soc-stat-val">{stats.denied_sessions}</div><div className="soc-stat-label">Accès refusés</div></div>
          <div className="soc-stat-card incident"><div className="soc-stat-val">{stats.active_policies}</div><div className="soc-stat-label">Politiques actives</div></div>
        </div>
      )}

      <div className="soc-panel" style={{ marginBottom: 12 }}>
        <div className="soc-panel-title">Évaluer un accès</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 8 }}>
          {[['user','Utilisateur','alice@company.local'],['source_ip','IP source','192.168.1.50'],['resource','Ressource','/admin/dashboard']].map(([key,label,ph]) => (
            <div key={key}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text3)', marginBottom: 3 }}>{label}</div>
              <input className="soc-input" style={{ width: '100%' }} placeholder={ph}
                value={form[key]} onChange={e => setForm(p => ({...p, [key]: e.target.value}))} />
            </div>
          ))}
        </div>
        <button className="soc-search-btn" onClick={evaluate} disabled={!form.user}>Évaluer</button>
        {evalResult && (
          <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8,
            background: `${DECISION_COLOR[evalResult.decision] || '#7c3aed'}18`,
            border: `1px solid ${DECISION_COLOR[evalResult.decision] || '#7c3aed'}44` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: DECISION_COLOR[evalResult.decision] }}>
                {evalResult.decision}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text2)' }}>Score de confiance: {evalResult.trust_score}/100</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text2)' }}>
              Facteurs: {evalResult.risk_factors?.join(', ') || 'aucun'}
            </div>
          </div>
        )}
      </div>

      {policies && (
        <div className="soc-rule-list">
          <div className="soc-panel-title" style={{ marginBottom: 8 }}>Politiques Zero Trust ({policies.length})</div>
          {policies.map(p => (
            <div key={p.id} className="soc-rule-card">
              <div className="soc-rule-header">
                <span style={{ fontSize: '0.68rem', color: 'var(--text3)', width: 30 }}>P{p.priority}</span>
                <span className="soc-rule-name">{p.name}</span>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 5,
                  background: `${ACTION_COLOR[p.action] || '#7c3aed'}22`,
                  color: ACTION_COLOR[p.action] || '#7c3aed' }}>{p.action}</span>
                <span style={{ fontSize: '0.65rem', color: p.enabled ? '#34d399' : '#64748b' }}>
                  {p.enabled ? '● actif' : '● inactif'}
                </span>
              </div>
              <div className="soc-rule-meta"><span>{p.description}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── REPORTS ───────────────────────────────────────────────────────────────────
function Reports() {
  const [types, setTypes]   = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(null)

  useEffect(() => { f(`${BASE}/reports/types`).then(d => setTypes(d.types)) }, [])

  const generate = async (type) => {
    setLoading(type)
    const r = await fetch(`${BASE}/reports/generate/${type}`, { method: 'POST' })
      .then(r => r.json()).catch(() => ({}))
    setResult(r)
    setLoading(null)
  }

  return (
    <div className="soc-section">
      {types && (
        <div className="soc-cards" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          {types.map(t => (
            <button key={t.type} className="soc-stat-card high"
              style={{ cursor: 'pointer', textAlign: 'left' }}
              onClick={() => generate(t.type)} disabled={loading === t.type}>
              <div className="soc-stat-val" style={{ fontSize: '1.8rem' }}>{t.icon}</div>
              <div className="soc-stat-label" style={{ fontSize: '0.75rem', fontWeight: 600, marginTop: 4 }}>
                {loading === t.type ? '⏳ Génération…' : t.label}
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginTop: 2 }}>{t.desc}</div>
            </button>
          ))}
        </div>
      )}

      {result && !result.error && (
        <div className="soc-panel" style={{ marginTop: 12 }}>
          <div className="soc-panel-title">📄 {result.label}</div>
          <div className="soc-sub">Généré le {new Date(result.generated_at).toLocaleString('fr-FR')} · Période: {result.period_hours}h</div>
          <pre style={{ marginTop: 12, fontSize: '0.75rem', color: 'var(--text2)', lineHeight: 1.5,
            background: 'var(--bg)', padding: '12px 14px', borderRadius: 8,
            border: '1px solid var(--border)', overflow: 'auto', maxHeight: 300 }}>
            {JSON.stringify(result.summary || result, null, 2)}
          </pre>
          {result.recommendations?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Recommandations</div>
              {result.recommendations.map((r, i) => (
                <div key={i} style={{ fontSize: '0.75rem', color: 'var(--text2)', marginBottom: 3 }}>{r}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Onglets ───────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'alerts',    label: '🔴 Alertes'   },
  { id: 'incidents', label: '🚨 Incidents'  },
  // Phase 2
  { id: 'ml',        label: '🧠 ML'         },
  { id: 'edr',       label: '🖥️ EDR'        },
  { id: 'nta',       label: '🌐 NTA'        },
  { id: 'ti',        label: '🔎 Threat Intel'},
  { id: 'ids',       label: '🛡️ IDS'        },
  // Phase 3
  { id: 'dlp',       label: '📋 DLP'        },
  { id: 'ransom',    label: '💀 Ransomware'  },
  { id: 'phish',     label: '🎣 Phishing'   },
  { id: 'osint',     label: '🕵️ APT/OSINT'  },
  // Phase 4
  { id: 'iam',       label: '👤 IAM'        },
  { id: 'compliance',label: '✅ Compliance'  },
  { id: 'zt',        label: '🔒 Zero Trust'  },
  { id: 'reports',   label: '📄 Rapports'   },
  // Fondation
  { id: 'siem',      label: '⚙️ SIEM'       },
  { id: 'soar',      label: '🤖 SOAR'       },
  { id: 'mitre',     label: '🗺️ MITRE'      },
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
        {tab === 'dashboard'  && <Dashboard onTab={setTab} />}
        {tab === 'alerts'     && <Alerts />}
        {tab === 'incidents'  && <Incidents />}
        {tab === 'ml'         && <MlAnomaly />}
        {tab === 'edr'        && <Edr />}
        {tab === 'nta'        && <Nta />}
        {tab === 'ti'         && <ThreatIntel />}
        {tab === 'ids'        && <Ids />}
        {tab === 'dlp'        && <Dlp />}
        {tab === 'ransom'     && <Ransomware />}
        {tab === 'phish'      && <Phishing />}
        {tab === 'osint'      && <Osint />}
        {tab === 'iam'        && <Iam />}
        {tab === 'compliance' && <Compliance />}
        {tab === 'zt'         && <ZeroTrust />}
        {tab === 'reports'    && <Reports />}
        {tab === 'siem'       && <Siem />}
        {tab === 'soar'       && <Soar />}
        {tab === 'mitre'      && <Mitre />}
      </div>
    </div>
  )
}
