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

// ── Onglets ───────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'alerts',    label: '🔴 Alertes'   },
  { id: 'incidents', label: '🚨 Incidents'  },
  { id: 'ml',        label: '🧠 ML Anomaly' },
  { id: 'edr',       label: '🖥️ EDR'        },
  { id: 'nta',       label: '🌐 NTA'        },
  { id: 'ti',        label: '🔎 Threat Intel'},
  { id: 'ids',       label: '🛡️ IDS'        },
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
        {tab === 'dashboard' && <Dashboard onTab={setTab} />}
        {tab === 'alerts'    && <Alerts />}
        {tab === 'incidents' && <Incidents />}
        {tab === 'ml'        && <MlAnomaly />}
        {tab === 'edr'       && <Edr />}
        {tab === 'nta'       && <Nta />}
        {tab === 'ti'        && <ThreatIntel />}
        {tab === 'ids'       && <Ids />}
        {tab === 'siem'      && <Siem />}
        {tab === 'soar'      && <Soar />}
        {tab === 'mitre'     && <Mitre />}
      </div>
    </div>
  )
}
