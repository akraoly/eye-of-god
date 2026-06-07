/**
 * AEGIS — Command Center + Intelligence
 * Onglets : Command Center · CVE Intel · Exploits · Cibles · Rapports
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

const SEV_COLOR = { INFO:'#38bdf8', LOW:'#4ade80', MEDIUM:'#fbbf24', HIGH:'#f97316', CRITICAL:'#ef4444' }
const SEV_BG    = { INFO:'#38bdf820', LOW:'#4ade8020', MEDIUM:'#fbbf2420', HIGH:'#f9731620', CRITICAL:'#ef444420' }

function SevBadge({ sev }) {
  return (
    <span style={{
      background: SEV_BG[sev] || '#ffffff10', color: SEV_COLOR[sev] || 'var(--text2)',
      border: `1px solid ${SEV_COLOR[sev] || '#ffffff30'}`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', fontWeight: 700,
    }}>
      {sev}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONGLET 1 — Command Center (panneaux existants)
// ═══════════════════════════════════════════════════════════════════════════════

function useNetworkWS() {
  const [events, setEvents] = useState([])
  const [stats,  setStats]  = useState(null)
  const [status, setStatus] = useState('disconnected')
  const wsRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const token = auth.getToken(); if (!token) return
    setStatus('connecting')
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/network/ws?token=${encodeURIComponent(token)}`)
    wsRef.current = ws
    ws.onopen    = () => setStatus('connected')
    ws.onclose   = () => { setStatus('disconnected'); setTimeout(connect, 3000) }
    ws.onerror   = () => setStatus('error')
    ws.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'ping') return
        if (data.type === 'stats') { setStats(data); return }
        if (data.type === 'network_event') setEvents(prev => [data, ...prev].slice(0, 80))
      } catch {}
    }
  }, [])

  useEffect(() => { connect(); return () => wsRef.current?.close() }, [connect])
  return { events, stats, status }
}

function NetworkPanel() {
  const { events, stats, status } = useNetworkWS()
  const [snapshot, setSnapshot] = useState(null)
  useEffect(() => {
    const load = () => apiFetch('/network/snapshot').then(r => r.json()).then(setSnapshot).catch(() => {})
    load(); const t = setInterval(load, 5000); return () => clearInterval(t)
  }, [])
  const dot = status === 'connected' ? '#4ade80' : status === 'connecting' ? '#fbbf24' : '#ef4444'
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🌐</span><span>Réseau Live</span>
        <span style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ width:8, height:8, borderRadius:'50%', background:dot, display:'inline-block' }} />
          <span style={{ fontSize:'0.65rem', color:'var(--text3)' }}>{status}</span>
        </span>
      </div>
      {snapshot && (
        <div className="aegis-stats-row">
          {[['Connexions', snapshot.conn_count,'var(--text1)'],['Établies',snapshot.established,'#a78bfa'],['Écoute',snapshot.listening,'#38bdf8']].map(([l,v,c]) => (
            <div className="aegis-stat-box" key={l}>
              <div className="aegis-stat-val" style={{ color:c }}>{v}</div>
              <div className="aegis-stat-label">{l}</div>
            </div>
          ))}
          {stats && <div className="aegis-stat-box">
            <div className="aegis-stat-val" style={{ color:'#4ade80' }}>{fmtBytes(stats.bytes_recv)}</div>
            <div className="aegis-stat-label">Reçus total</div>
          </div>}
        </div>
      )}
      <div className="aegis-feed">
        {events.length === 0 ? <div className="aegis-feed-empty">En attente d'événements…</div>
        : events.map((evt, i) => (
          <div key={i} className={`aegis-feed-row${evt.is_suspicious?' aegis-suspicious':''}`}>
            <SevBadge sev={evt.severity} />
            <span className="aegis-feed-time">{evt.timestamp?.slice(11,19)}</span>
            <span className="aegis-feed-title">{evt.title}</span>
            {evt.source_ip && <span className="aegis-feed-ip">{evt.source_ip}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function SystemPanel() {
  const [metrics, setMetrics] = useState(null)
  const [history, setHistory] = useState([])
  useEffect(() => {
    const fetch = () => apiFetch('/system/metrics').then(r => r.json()).then(m => {
      setMetrics(m)
      setHistory(prev => [...prev, { cpu: m.cpu?.percent ?? 0, ram: m.memory?.percent ?? 0 }].slice(-30))
    }).catch(() => {})
    fetch(); const t = setInterval(fetch, 2000); return () => clearInterval(t)
  }, [])
  const SparkBar = ({ values, color }) => (
    <div style={{ display:'flex', alignItems:'flex-end', gap:1, height:28, marginTop:4 }}>
      {values.map((v, i) => <div key={i} style={{ flex:1, background:color, opacity:0.5+0.5*(i/values.length), height:`${Math.max(2,v)}%`, borderRadius:1 }} />)}
    </div>
  )
  const Bar = ({ val, color }) => (
    <div style={{ position:'relative', height:6, background:'#ffffff10', borderRadius:3, overflow:'hidden', marginTop:4 }}>
      <div style={{ width:`${val}%`, height:'100%', background:color, borderRadius:3, transition:'width 0.5s' }} />
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">💻</span><span>Système</span>
        {metrics?.uptime && <span style={{ marginLeft:'auto', fontSize:'0.62rem', color:'var(--text3)' }}>uptime {metrics.uptime}</span>}
      </div>
      {metrics ? (
        <div className="aegis-sys-grid">
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">CPU</div>
            <div className="aegis-sys-val" style={{ color: metrics.cpu?.percent>80?'#ef4444':'#a78bfa' }}>{metrics.cpu?.percent?.toFixed(1)}%</div>
            <Bar val={metrics.cpu?.percent} color="#a78bfa" />
            <SparkBar values={history.map(h=>h.cpu)} color="#a78bfa" />
          </div>
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">RAM</div>
            <div className="aegis-sys-val" style={{ color: metrics.memory?.percent>85?'#ef4444':'#38bdf8' }}>{metrics.memory?.percent?.toFixed(1)}%</div>
            <Bar val={metrics.memory?.percent} color="#38bdf8" />
            <div style={{ fontSize:'0.6rem', color:'var(--text3)', marginTop:2 }}>{fmtBytes(metrics.memory?.used)} / {fmtBytes(metrics.memory?.total)}</div>
          </div>
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">Disque</div>
            <div className="aegis-sys-val" style={{ color: metrics.disk?.percent>90?'#ef4444':'#4ade80' }}>{metrics.disk?.percent?.toFixed(1)}%</div>
            <Bar val={metrics.disk?.percent} color="#4ade80" />
          </div>
          <div className="aegis-sys-block">
            <div className="aegis-sys-label">Processus</div>
            <div className="aegis-sys-val" style={{ color:'#fbbf24' }}>{metrics.process_count ?? '—'}</div>
          </div>
        </div>
      ) : <div className="aegis-feed-empty">Chargement métriques…</div>}
      {metrics?.top_processes?.length > 0 && (
        <div style={{ marginTop:8 }}>
          <div style={{ fontSize:'0.62rem', color:'var(--text3)', marginBottom:4 }}>Top CPU</div>
          {metrics.top_processes.slice(0,5).map((p,i) => (
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

function PentestPanel() {
  const [jobs, setJobs] = useState([])
  const [target, setTarget] = useState('')
  const [running, setRunning] = useState(null)
  const [steps, setSteps] = useState([])
  const [log, setLog] = useState([])
  const esRef = useRef(null)
  const logRef = useRef(null)

  const loadJobs = () => apiFetch('/pentest/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
  useEffect(() => { loadJobs(); const t = setInterval(loadJobs, 10000); return () => clearInterval(t) }, [])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])

  const launch = async () => {
    if (!target.trim()) return
    const res = await apiFetch('/pentest/run', { method:'POST', body: JSON.stringify({ target: target.trim() }) })
    const { job_id } = await res.json()
    setRunning(job_id); setSteps([]); setLog([`[${new Date().toLocaleTimeString()}] Opération lancée — ${target}`])
    esRef.current?.close()
    const es = new EventSource(`/api/pentest/stream/${job_id}?token=${auth.getToken()}`)
    esRef.current = es
    es.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] [${data.type}] ${data.data?.message||data.message||data.step?.name||''}`])
        if (data.type==='step_start') setSteps(prev => { const s={...data.step,status:'running'}; const idx=prev.findIndex(x=>x.name===s.name); return idx>=0?prev.map((x,i)=>i===idx?s:x):[...prev,s] })
        if (data.type==='step_done')  setSteps(prev => prev.map(s => s.name===data.step?.name?data.step:s))
        if (data.type==='complete') { setRunning(null); loadJobs(); es.close() }
        if (data.type==='error')    { setRunning(null); es.close() }
      } catch {}
    }
    es.onerror = () => { setRunning(null); es.close() }
  }

  const STEP_ICON = { pending:'○', running:'⟳', done:'✓', error:'✗', skipped:'—' }
  const STEP_COLOR = { pending:'var(--text3)', running:'#fbbf24', done:'#4ade80', error:'#ef4444', skipped:'var(--text3)' }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">⚔️</span><span>Opérations Offensives</span>
        {running && <span className="aegis-running-badge">EN COURS</span>}
      </div>
      <div className="aegis-launch-row">
        <input className="aegis-target-input" placeholder="Cible : IP ou domaine…" value={target}
          onChange={e=>setTarget(e.target.value)} onKeyDown={e=>e.key==='Enter'&&!running&&launch()} disabled={!!running} />
        {running
          ? <button className="aegis-stop-btn" onClick={() => { apiFetch(`/pentest/jobs/${running}/stop`,{method:'POST'}).catch(()=>{}); esRef.current?.close(); setRunning(null); setLog(p=>[...p,'⏹ Arrêté']) }}>⏹ Stop</button>
          : <button className="aegis-launch-btn" onClick={launch} disabled={!target.trim()}>▶ Lancer</button>
        }
      </div>
      {steps.length > 0 && <div className="aegis-pipeline">{steps.map((s,i) => (
        <div key={i} className="aegis-step-row">
          <span style={{ color:STEP_COLOR[s.status], fontSize:'0.75rem', fontWeight:700, minWidth:14 }}>{STEP_ICON[s.status]}</span>
          <span className="aegis-step-name">{s.name}</span>
          {s.duration && <span className="aegis-step-dur">{s.duration}s</span>}
        </div>
      ))}</div>}
      {log.length > 0 && <div className="aegis-log" ref={logRef}>{log.map((l,i) => <div key={i} className="aegis-log-line">{l}</div>)}</div>}
      {jobs.length > 0 && <div style={{ marginTop:8 }}>
        <div style={{ fontSize:'0.62rem', color:'var(--text3)', marginBottom:4 }}>Historique</div>
        {jobs.slice(0,5).map(j => (
          <div key={j.job_id} className="aegis-job-row">
            <span className={`aegis-job-status ${j.status}`}>{j.status}</span>
            <span className="aegis-job-target">{j.target}</span>
            <span className="aegis-job-ports">{j.summary?.open_ports?.length||0} ports</span>
            <span className="aegis-job-cves">{j.summary?.cves_count||0} CVEs</span>
          </div>
        ))}
      </div>}
    </div>
  )
}

function AlertsPanel() {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('ALL')
  useEffect(() => {
    const load = () => apiFetch('/soc/alerts?limit=50').then(r => r.json()).then(d => setAlerts(d.alerts||[])).catch(() => {})
    load(); const t = setInterval(load, 5000); return () => clearInterval(t)
  }, [])
  const filtered = filter==='ALL' ? alerts : alerts.filter(a=>a.severity===filter)
  const counts = alerts.reduce((acc,a) => { acc[a.severity]=(acc[a.severity]||0)+1; return acc }, {})
  const ack = async id => {
    await apiFetch(`/soc/alerts/${id}`,{method:'PATCH',body:JSON.stringify({status:'ACK'})}).catch(()=>{})
    setAlerts(prev => prev.map(a => a.id===id?{...a,status:'ACK'}:a))
  }
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🚨</span><span>Alertes & Détections</span>
        <span style={{ marginLeft:'auto', fontSize:'0.65rem', color:'var(--text3)' }}>{alerts.length} alertes</span>
      </div>
      <div className="aegis-stats-row" style={{ flexWrap:'wrap' }}>
        {['CRITICAL','HIGH','MEDIUM','LOW'].map(sev => (
          <button key={sev} className={`aegis-sev-filter ${filter===sev?'active':''}`}
            style={{ borderColor:SEV_COLOR[sev], color:filter===sev?SEV_COLOR[sev]:'var(--text3)' }}
            onClick={() => setFilter(filter===sev?'ALL':sev)}>
            <span style={{ color:SEV_COLOR[sev] }}>{counts[sev]||0}</span> {sev}
          </button>
        ))}
      </div>
      <div className="aegis-feed">
        {filtered.length===0 ? <div className="aegis-feed-empty">Aucune alerte {filter!=='ALL'?filter:''}</div>
        : filtered.slice(0,30).map((a,i) => (
          <div key={i} className={`aegis-feed-row ${a.status==='NEW'?'aegis-alert-new':''}`}>
            <SevBadge sev={a.severity} />
            <span className="aegis-feed-time">{a.timestamp?.slice(11,19)}</span>
            <span className="aegis-feed-title" style={{ flex:1 }}>{a.title}</span>
            {a.status==='NEW' && <button className="aegis-ack-btn" onClick={()=>ack(a.id)}>ACK</button>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONGLET 2 — CVE Intel
// ═══════════════════════════════════════════════════════════════════════════════

function CveIntelTab() {
  const [cves, setCves] = useState([])
  const [stats, setStats] = useState(null)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState({ severity:'', unread:false, exploit:false, project:false })
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams({ limit:100 })
    if (filter.severity) params.set('severity', filter.severity)
    if (filter.unread)   params.set('read', 'false')
    if (filter.exploit)  params.set('has_exploit', 'true')
    if (filter.project)  params.set('affects_project', 'true')
    apiFetch(`/aegis/cves?${params}`).then(r => r.json()).then(d => { setCves(d.cves||[]); setLoading(false) }).catch(() => setLoading(false))
    apiFetch('/aegis/cves/stats').then(r => r.json()).then(setStats).catch(() => {})
  }, [filter])

  useEffect(() => { load() }, [load])

  const markRead = id => {
    apiFetch(`/aegis/cves/${id}/read`, { method:'POST' }).catch(() => {})
    setCves(prev => prev.map(c => c.cve_id===id ? {...c, read:true} : c))
  }

  const refresh = async () => {
    setRefreshing(true)
    await apiFetch('/aegis/cves/refresh', { method:'POST' }).catch(() => {})
    setRefreshing(false)
    load()
  }

  const openDetail = cve => {
    setSelected(cve)
    if (!cve.read) markRead(cve.cve_id)
  }

  return (
    <div style={{ display:'flex', gap:12, height:'100%', minHeight:0 }}>
      {/* Colonne gauche */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', gap:8, minHeight:0 }}>
        {/* Stats bar */}
        {stats && (
          <div className="aegis-stats-row">
            {[['Total', stats.total,'var(--text1)'],['Non lus',stats.unread,'#fbbf24'],['Critiques',stats.critical,'#ef4444'],['Avec exploit',stats.with_exploit,'#f97316'],['Proj. affectés',stats.affects_project,'#a78bfa']].map(([l,v,c]) => (
              <div className="aegis-stat-box" key={l}>
                <div className="aegis-stat-val" style={{ color:c }}>{v}</div>
                <div className="aegis-stat-label">{l}</div>
              </div>
            ))}
          </div>
        )}

        {/* Filtres */}
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {['','CRITICAL','HIGH','MEDIUM','LOW'].map(s => (
            <button key={s||'ALL'}
              style={{ padding:'3px 8px', fontSize:'0.65rem', background: filter.severity===s?'var(--primary)':'var(--bg2)',
                color: filter.severity===s?'white':'var(--text2)', border:'1px solid var(--border)', borderRadius:4, cursor:'pointer' }}
              onClick={() => setFilter(f => ({...f, severity:s}))}>
              {s||'Tout'}
            </button>
          ))}
          <span style={{ flex:1 }} />
          {[['unread','Non lus'],['exploit','Avec exploit'],['project','Projet affecté']].map(([k,l]) => (
            <button key={k}
              style={{ padding:'3px 8px', fontSize:'0.65rem', background: filter[k]?'#a78bfa20':'var(--bg2)',
                color: filter[k]?'#a78bfa':'var(--text3)', border:`1px solid ${filter[k]?'#a78bfa':'var(--border)'}`, borderRadius:4, cursor:'pointer' }}
              onClick={() => setFilter(f => ({...f, [k]:!f[k]}))}>
              {l}
            </button>
          ))}
          <button onClick={refresh} disabled={refreshing}
            style={{ padding:'3px 8px', fontSize:'0.65rem', background:'var(--bg2)', color:'#38bdf8', border:'1px solid #38bdf840', borderRadius:4, cursor:'pointer' }}>
            {refreshing ? '⟳ …' : '⟳ MAJ NVD'}
          </button>
        </div>

        {/* Liste CVE */}
        <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:4 }}>
          {loading && <div className="aegis-feed-empty">Chargement…</div>}
          {!loading && cves.length===0 && <div className="aegis-feed-empty">Aucun CVE — lancez une collecte NVD</div>}
          {cves.map(cve => (
            <div key={cve.cve_id}
              onClick={() => openDetail(cve)}
              style={{
                padding:'8px 10px', background: selected?.cve_id===cve.cve_id?'var(--primary)20':'var(--bg2)',
                border:`1px solid ${selected?.cve_id===cve.cve_id?'var(--primary)':'var(--border)'}`,
                borderLeft:`3px solid ${SEV_COLOR[cve.severity]||'#ffffff20'}`,
                borderRadius:6, cursor:'pointer', opacity: cve.read?0.7:1,
              }}>
              <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                <span style={{ fontFamily:'monospace', fontSize:'0.72rem', color:'#a78bfa', fontWeight:700 }}>{cve.cve_id}</span>
                <SevBadge sev={cve.severity} />
                {cve.cvss_score >= 0 && <span style={{ fontSize:'0.62rem', color:'var(--text3)' }}>CVSS {cve.cvss_score?.toFixed(1)}</span>}
                {cve.has_exploit && <span style={{ fontSize:'0.58rem', background:'#f9731620', color:'#f97316', border:'1px solid #f9731640', borderRadius:3, padding:'0 4px' }}>EXPLOIT</span>}
                {cve.affects_project && <span style={{ fontSize:'0.58rem', background:'#ef444420', color:'#ef4444', border:'1px solid #ef444440', borderRadius:3, padding:'0 4px' }}>PROJET</span>}
                {!cve.read && <span style={{ marginLeft:'auto', width:6, height:6, borderRadius:'50%', background:'#fbbf24', display:'inline-block' }} />}
              </div>
              <div style={{ fontSize:'0.65rem', color:'var(--text2)', marginTop:3, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {cve.title || cve.description?.slice(0,100) || '—'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Colonne droite — détail */}
      {selected && (
        <div style={{ width:340, background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:14, overflowY:'auto', display:'flex', flexDirection:'column', gap:10 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontFamily:'monospace', fontWeight:700, color:'#a78bfa', fontSize:'0.85rem' }}>{selected.cve_id}</span>
            <button onClick={() => setSelected(null)} style={{ background:'none', border:'none', color:'var(--text3)', cursor:'pointer', fontSize:'1rem' }}>✕</button>
          </div>
          <SevBadge sev={selected.severity} />
          {selected.cvss_score != null && <div style={{ fontSize:'0.72rem', color:'var(--text2)' }}>CVSS {selected.cvss_score?.toFixed(1)} — {selected.cvss_vector || ''}</div>}
          {selected.published_at && <div style={{ fontSize:'0.65rem', color:'var(--text3)' }}>Publié le {selected.published_at?.slice(0,10)}</div>}
          <div style={{ fontSize:'0.7rem', color:'var(--text1)', lineHeight:1.5 }}>{selected.description}</div>
          {selected.affected_products?.length > 0 && (
            <div>
              <div style={{ fontSize:'0.62rem', color:'var(--text3)', marginBottom:4 }}>Produits affectés</div>
              {selected.affected_products.slice(0,8).map((p,i) => <div key={i} style={{ fontSize:'0.65rem', color:'var(--text2)' }}>• {p}</div>)}
            </div>
          )}
          {selected.ai_summary && (
            <div style={{ background:'#a78bfa10', border:'1px solid #a78bfa30', borderRadius:6, padding:8 }}>
              <div style={{ fontSize:'0.62rem', color:'#a78bfa', marginBottom:4 }}>IA Summary</div>
              <div style={{ fontSize:'0.65rem', color:'var(--text1)', lineHeight:1.5 }}>{selected.ai_summary}</div>
            </div>
          )}
          {selected.exploits?.length > 0 && (
            <div>
              <div style={{ fontSize:'0.62rem', color:'var(--text3)', marginBottom:4 }}>Exploits associés ({selected.exploits.length})</div>
              {selected.exploits.map((e,i) => (
                <div key={i} style={{ padding:'4px 8px', background:'#f9731610', border:'1px solid #f9731630', borderRadius:4, marginBottom:3, fontSize:'0.65rem' }}>
                  <div style={{ color:'#f97316', fontWeight:700 }}>{e.repo_name}</div>
                  <div style={{ color:'var(--text3)' }}>{e.reliability} — {e.language}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONGLET 3 — Exploits
// ═══════════════════════════════════════════════════════════════════════════════

function ExploitsTab() {
  const [exploits, setExploits] = useState([])
  const [analyzing, setAnalyzing] = useState(null)

  useEffect(() => {
    apiFetch('/aegis/exploits?limit=100').then(r => r.json()).then(d => setExploits(d.exploits||[])).catch(() => {})
  }, [])

  const analyze = async exploit_id => {
    setAnalyzing(exploit_id)
    const res = await apiFetch(`/aegis/exploits/${exploit_id}/analyze`, { method:'POST' }).catch(() => null)
    if (res?.ok) {
      const data = await res.json()
      setExploits(prev => prev.map(e => e.exploit_id===exploit_id ? {...e, ai_analysis:data.analysis, status:'analyzed'} : e))
    }
    setAnalyzing(null)
  }

  const REL_COLOR = { high:'#ef4444', medium:'#f97316', low:'#fbbf24', unknown:'var(--text3)' }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <span style={{ fontSize:'0.72rem', color:'var(--text2)' }}>{exploits.length} exploit(s) en surveillance</span>
        <span style={{ fontSize:'0.65rem', color:'var(--text3)' }}>Analyse statique uniquement — aucun code exécuté</span>
      </div>
      {exploits.length===0 && <div className="aegis-feed-empty">Aucun exploit — la veille GitHub est automatique (toutes les 2h)</div>}
      {exploits.map(e => (
        <div key={e.exploit_id} style={{ padding:12, background:'var(--bg2)', border:'1px solid var(--border)', borderLeft:`3px solid ${REL_COLOR[e.reliability||'unknown']}`, borderRadius:6 }}>
          <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:6 }}>
            <span style={{ fontWeight:700, color:'#f97316', fontSize:'0.75rem' }}>{e.repo_name}</span>
            {e.cve_id && <span style={{ fontFamily:'monospace', fontSize:'0.62rem', color:'#a78bfa' }}>{e.cve_id}</span>}
            {e.reliability && <span style={{ fontSize:'0.58rem', background:REL_COLOR[e.reliability]+'20', color:REL_COLOR[e.reliability], border:`1px solid ${REL_COLOR[e.reliability]}40`, borderRadius:3, padding:'0 4px' }}>{e.reliability}</span>}
            {e.language && <span style={{ fontSize:'0.58rem', color:'var(--text3)' }}>{e.language}</span>}
            <span style={{ marginLeft:'auto', fontSize:'0.6rem', color:'var(--text3)' }}>⭐ {e.stars}</span>
          </div>
          <div style={{ fontSize:'0.65rem', color:'var(--text2)', marginBottom:6 }}>{e.description?.slice(0,150) || '—'}</div>
          {e.ai_analysis ? (
            <div style={{ background:'#38bdf810', border:'1px solid #38bdf830', borderRadius:4, padding:6, fontSize:'0.62rem', color:'var(--text2)', marginBottom:6 }}>
              <div style={{ color:'#38bdf8', marginBottom:2, fontSize:'0.6rem' }}>Analyse IA</div>
              {e.ai_analysis?.slice(0,300)}
            </div>
          ) : null}
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <a href={e.repo_url} target="_blank" rel="noopener noreferrer" style={{ fontSize:'0.62rem', color:'#38bdf8', textDecoration:'none' }}>⎋ GitHub</a>
            <button onClick={() => analyze(e.exploit_id)} disabled={analyzing===e.exploit_id || e.status==='analyzed'}
              style={{ padding:'2px 8px', fontSize:'0.62rem', background:'var(--bg3)', color: e.status==='analyzed'?'var(--text3)':'#a78bfa', border:`1px solid ${e.status==='analyzed'?'var(--border)':'#a78bfa40'}`, borderRadius:4, cursor: e.status==='analyzed'?'default':'pointer' }}>
              {analyzing===e.exploit_id ? '⟳ Analyse…' : e.status==='analyzed' ? '✓ Analysé' : '⚡ Analyser'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONGLET 4 — Cibles (gate autorisation obligatoire)
// ═══════════════════════════════════════════════════════════════════════════════

function TargetsTab() {
  const [targets, setTargets] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [reconning, setReconning] = useState(null)
  const [reconResult, setReconResult] = useState(null)
  const [form, setForm] = useState({ name:'', target_type:'domain', target_value:'', authorization_confirmed:false, authorization_note:'', notes:'' })

  const load = () => apiFetch('/aegis/targets').then(r => r.json()).then(d => setTargets(d.targets||[])).catch(() => {})
  useEffect(() => { load() }, [])

  const submit = async () => {
    if (!form.authorization_confirmed) { alert('Vous devez confirmer l\'autorisation de pentest écrite avant d\'ajouter une cible.'); return }
    const res = await apiFetch('/aegis/targets', { method:'POST', body: JSON.stringify(form) }).catch(() => null)
    if (res?.ok) { setShowForm(false); setForm({ name:'', target_type:'domain', target_value:'', authorization_confirmed:false, authorization_note:'', notes:'' }); load() }
  }

  const recon = async target_id => {
    setReconning(target_id); setReconResult(null)
    const res = await apiFetch(`/aegis/targets/${target_id}/recon`, { method:'POST' }).catch(() => null)
    if (res?.ok) { const d = await res.json(); setReconResult(d) }
    else setReconResult({ error: 'Erreur reconnaissance — vérifiez l\'autorisation' })
    setReconning(null); load()
  }

  const remove = async target_id => {
    if (!confirm('Supprimer cette cible ?')) return
    await apiFetch(`/aegis/targets/${target_id}`, { method:'DELETE' }).catch(() => {})
    load()
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      {/* Avertissement sécurité */}
      <div style={{ background:'#ef444410', border:'1px solid #ef444440', borderRadius:8, padding:'10px 14px', fontSize:'0.68rem', color:'#ef4444', lineHeight:1.6 }}>
        <strong>⚠ AVERTISSEMENT LÉGAL</strong> — Toute reconnaissance sur une cible doit faire l'objet d'une autorisation écrite explicite de la part du propriétaire du système.
        La reconnaissance passive utilise exclusivement des sources publiques (DNS, crt.sh, WHOIS). Aucune connexion directe à la cible n'est effectuée.
      </div>

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <span style={{ fontSize:'0.72rem', color:'var(--text2)' }}>{targets.length} cible(s) autorisée(s)</span>
        <button onClick={() => setShowForm(!showForm)} style={{ padding:'4px 12px', fontSize:'0.68rem', background:'var(--primary)', color:'white', border:'none', borderRadius:6, cursor:'pointer' }}>
          {showForm ? '✕ Annuler' : '+ Ajouter une cible'}
        </button>
      </div>

      {/* Formulaire d'ajout */}
      {showForm && (
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:14, display:'flex', flexDirection:'column', gap:8 }}>
          <div style={{ display:'flex', gap:8 }}>
            <div style={{ flex:1 }}>
              <label style={{ fontSize:'0.62rem', color:'var(--text3)', display:'block', marginBottom:3 }}>Nom de la mission</label>
              <input value={form.name} onChange={e => setForm(f=>({...f,name:e.target.value}))} placeholder="Client XYZ — audit externe"
                style={{ width:'100%', padding:'5px 8px', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4, color:'var(--text1)', fontSize:'0.72rem', boxSizing:'border-box' }} />
            </div>
            <div>
              <label style={{ fontSize:'0.62rem', color:'var(--text3)', display:'block', marginBottom:3 }}>Type</label>
              <select value={form.target_type} onChange={e => setForm(f=>({...f,target_type:e.target.value}))}
                style={{ padding:'5px 8px', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4, color:'var(--text1)', fontSize:'0.72rem' }}>
                <option value="domain">Domaine</option>
                <option value="ip">IP</option>
                <option value="org">Organisation</option>
              </select>
            </div>
          </div>
          <div>
            <label style={{ fontSize:'0.62rem', color:'var(--text3)', display:'block', marginBottom:3 }}>Valeur cible</label>
            <input value={form.target_value} onChange={e => setForm(f=>({...f,target_value:e.target.value}))} placeholder="exemple.com ou 192.168.1.0/24"
              style={{ width:'100%', padding:'5px 8px', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4, color:'var(--text1)', fontSize:'0.72rem', boxSizing:'border-box' }} />
          </div>
          <div>
            <label style={{ fontSize:'0.62rem', color:'var(--text3)', display:'block', marginBottom:3 }}>Référence d'autorisation (contrat/bon de commande)</label>
            <input value={form.authorization_note} onChange={e => setForm(f=>({...f,authorization_note:e.target.value}))} placeholder="Contrat #2024-XXX, email du RSSI, etc."
              style={{ width:'100%', padding:'5px 8px', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4, color:'var(--text1)', fontSize:'0.72rem', boxSizing:'border-box' }} />
          </div>
          <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer', userSelect:'none' }}>
            <input type="checkbox" checked={form.authorization_confirmed} onChange={e => setForm(f=>({...f,authorization_confirmed:e.target.checked}))} />
            <span style={{ fontSize:'0.68rem', color: form.authorization_confirmed?'#4ade80':'#ef4444', fontWeight:600 }}>
              ✓ Je certifie disposer d'une autorisation écrite de pentest sur cette cible
            </span>
          </label>
          <button onClick={submit} disabled={!form.authorization_confirmed||!form.target_value||!form.name}
            style={{ padding:'6px 16px', background: form.authorization_confirmed?'var(--primary)':'#ffffff20', color:'white', border:'none', borderRadius:6, cursor: form.authorization_confirmed?'pointer':'not-allowed', fontSize:'0.72rem' }}>
            Ajouter la cible
          </button>
        </div>
      )}

      {/* Résultat de recon */}
      {reconResult && (
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:12, fontSize:'0.65rem' }}>
          {reconResult.error
            ? <div style={{ color:'#ef4444' }}>❌ {reconResult.error}</div>
            : <div>
                <div style={{ color:'#4ade80', marginBottom:4 }}>✓ Recon terminée — {reconResult.subdomains?.length||0} sous-domaines, {Object.keys(reconResult.dns_records||{}).length} enreg. DNS</div>
                {reconResult.changes?.length > 0 && <div style={{ color:'#fbbf24' }}>⚡ Changements : {reconResult.changes.join(' · ')}</div>}
                <button onClick={()=>setReconResult(null)} style={{ marginTop:4, background:'none', border:'none', color:'var(--text3)', cursor:'pointer', fontSize:'0.6rem' }}>✕ Fermer</button>
              </div>
          }
        </div>
      )}

      {/* Liste cibles */}
      {targets.map(t => (
        <div key={t.target_id} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderLeft:'3px solid #a78bfa', borderRadius:6, padding:12 }}>
          <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:6 }}>
            <span style={{ fontWeight:700, color:'#a78bfa' }}>{t.name}</span>
            <span style={{ fontSize:'0.62rem', background:'#a78bfa20', color:'#a78bfa', padding:'1px 6px', borderRadius:3 }}>{t.target_type}</span>
            <span style={{ fontFamily:'monospace', fontSize:'0.65rem', color:'var(--text2)' }}>{t.target_value}</span>
            <span style={{ marginLeft:'auto', fontSize:'0.6rem', color: t.authorization_confirmed?'#4ade80':'#ef4444' }}>
              {t.authorization_confirmed ? '✓ Autorisé' : '✗ Non autorisé'}
            </span>
          </div>
          {t.last_checked && <div style={{ fontSize:'0.6rem', color:'var(--text3)', marginBottom:4 }}>Dernière vérification : {t.last_checked.slice(0,16).replace('T',' ')}</div>}
          {t.subdomains?.length > 0 && <div style={{ fontSize:'0.62rem', color:'var(--text2)', marginBottom:4 }}>{t.subdomains.length} sous-domaine(s) détecté(s)</div>}
          {t.findings?.length > 0 && <div style={{ fontSize:'0.62rem', color:'#fbbf24', marginBottom:4 }}>⚡ {t.findings.length} changement(s)</div>}
          <div style={{ display:'flex', gap:8 }}>
            <button onClick={() => recon(t.target_id)} disabled={reconning===t.target_id}
              style={{ padding:'3px 10px', fontSize:'0.62rem', background:'var(--bg3)', color:'#38bdf8', border:'1px solid #38bdf840', borderRadius:4, cursor:'pointer' }}>
              {reconning===t.target_id ? '⟳ En cours…' : '🔍 Recon passive'}
            </button>
            <button onClick={() => remove(t.target_id)}
              style={{ padding:'3px 10px', fontSize:'0.62rem', background:'var(--bg3)', color:'#ef4444', border:'1px solid #ef444440', borderRadius:4, cursor:'pointer' }}>
              ✕ Supprimer
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ONGLET 5 — Rapports
// ═══════════════════════════════════════════════════════════════════════════════

function ReportsTab() {
  const [reports, setReports] = useState([])
  const [selected, setSelected] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [hours, setHours] = useState(24)

  const load = () => apiFetch('/aegis/reports?limit=20').then(r => r.json()).then(d => setReports(d.reports||[])).catch(() => {})
  useEffect(() => { load() }, [])

  const generate = async () => {
    setGenerating(true)
    const res = await apiFetch('/aegis/reports/generate', { method:'POST', body: JSON.stringify({ hours }) }).catch(() => null)
    if (res?.ok) { const d = await res.json(); setSelected(d); load() }
    setGenerating(false)
  }

  const TYPE_LABEL = { weekly:'Hebdomadaire', on_demand:'À la demande' }

  return (
    <div style={{ display:'flex', gap:12, height:'100%', minHeight:0 }}>
      {/* Liste rapports */}
      <div style={{ width:240, display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ display:'flex', gap:6, alignItems:'center' }}>
          <select value={hours} onChange={e=>setHours(Number(e.target.value))}
            style={{ flex:1, padding:'4px 6px', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:4, color:'var(--text1)', fontSize:'0.65rem' }}>
            <option value={6}>6 dernières heures</option>
            <option value={24}>24 heures</option>
            <option value={72}>72 heures</option>
            <option value={168}>7 jours</option>
          </select>
          <button onClick={generate} disabled={generating}
            style={{ padding:'4px 10px', fontSize:'0.62rem', background:'var(--primary)', color:'white', border:'none', borderRadius:4, cursor:'pointer', whiteSpace:'nowrap' }}>
            {generating ? '⟳ …' : '⚡ Générer'}
          </button>
        </div>
        <div style={{ fontSize:'0.6rem', color:'var(--text3)' }}>Rapport hebdomadaire : automatique dimanche 09:00</div>
        <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:4 }}>
          {reports.length===0 && <div className="aegis-feed-empty">Aucun rapport — générez votre premier rapport</div>}
          {reports.map(r => (
            <div key={r.report_id} onClick={() => setSelected(r)}
              style={{ padding:'8px 10px', background: selected?.report_id===r.report_id?'var(--primary)20':'var(--bg2)',
                border:`1px solid ${selected?.report_id===r.report_id?'var(--primary)':'var(--border)'}`, borderRadius:6, cursor:'pointer' }}>
              <div style={{ fontSize:'0.68rem', color:'var(--text1)', fontWeight:600 }}>{r.title}</div>
              <div style={{ display:'flex', gap:8, marginTop:3 }}>
                <span style={{ fontSize:'0.58rem', background:'var(--bg3)', color:'var(--text3)', padding:'1px 4px', borderRadius:3 }}>{TYPE_LABEL[r.report_type]||r.report_type}</span>
                <span style={{ fontSize:'0.58rem', color:'var(--text3)' }}>{r.created_at?.slice(0,10)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Contenu rapport */}
      <div style={{ flex:1, background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:14, overflowY:'auto' }}>
        {!selected ? (
          <div className="aegis-feed-empty">Sélectionnez un rapport</div>
        ) : (
          <>
            <div style={{ fontSize:'0.85rem', fontWeight:700, color:'var(--text1)', marginBottom:4 }}>{selected.title}</div>
            <div style={{ fontSize:'0.62rem', color:'var(--text3)', marginBottom:12 }}>{selected.created_at?.replace('T',' ').slice(0,16)}</div>
            <div style={{ fontSize:'0.72rem', color:'var(--text1)', lineHeight:1.7, whiteSpace:'pre-wrap' }}>{selected.content}</div>
          </>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Vue principale AEGIS
// ═══════════════════════════════════════════════════════════════════════════════

const TABS = [
  { id:'command',  label:'⚡ Command Center' },
  { id:'cve',      label:'🔴 CVE Intel' },
  { id:'exploits', label:'💣 Exploits' },
  { id:'targets',  label:'🎯 Cibles' },
  { id:'reports',  label:'📄 Rapports' },
]

export default function AegisView() {
  const [tab, setTab] = useState('command')

  return (
    <div className="aegis-view" style={{ display:'flex', flexDirection:'column', height:'100%' }}>
      {/* Header */}
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">⚡</span>
          <div>
            <div className="aegis-title">AEGIS COMMAND CENTER</div>
            <div className="aegis-subtitle">Surveillance · Renseignement · Cibles · Rapports</div>
          </div>
        </div>
        <div className="aegis-header-right">
          <span className="aegis-live-dot" />
          <span style={{ fontSize:'0.65rem', color:'var(--text3)' }}>LIVE</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:0, borderBottom:'1px solid var(--border)', marginBottom:12 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{
              padding:'8px 16px', fontSize:'0.7rem', background:'none', border:'none',
              borderBottom: tab===t.id?'2px solid var(--primary)':'2px solid transparent',
              color: tab===t.id?'var(--primary)':'var(--text3)',
              cursor:'pointer', fontWeight: tab===t.id?700:400, transition:'all 0.15s',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      <div style={{ flex:1, overflowY:'auto', minHeight:0 }}>
        {tab === 'command' && (
          <div className="aegis-grid">
            <NetworkPanel />
            <SystemPanel />
            <PentestPanel />
            <AlertsPanel />
          </div>
        )}
        {tab === 'cve'      && <CveIntelTab />}
        {tab === 'exploits' && <ExploitsTab />}
        {tab === 'targets'  && <TargetsTab />}
        {tab === 'reports'  && <ReportsTab />}
      </div>
    </div>
  )
}
