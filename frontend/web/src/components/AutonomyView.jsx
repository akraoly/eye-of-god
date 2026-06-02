import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

const api = (path, opts) => apiFetch(path, opts).then(r => r.json())

const LEVEL_COLOR = { info: '#34d399', warning: '#fbbf24', error: '#f87171', critical: '#c026d3' }
const LEVEL_ICON  = { info: 'ℹ️', warning: '⚠️', error: '🔴', critical: '🚨' }

export default function AutonomyView({ onUnreadChange }) {
  const [tab, setTab] = useState('tasks')
  const [unread, setUnread] = useState(0)

  const refreshUnread = useCallback(async () => {
    const d = await api('/autonomy/alerts/count')
    const n = d.unread || 0
    setUnread(n)
    onUnreadChange?.(n)
  }, [onUnreadChange])

  useEffect(() => {
    refreshUnread()
    const t = setInterval(refreshUnread, 15000)
    return () => clearInterval(t)
  }, [refreshUnread])

  return (
    <div className="panel-view">
      <div className="panel-tabs">
        <button className={`panel-tab ${tab==='tasks'?'active':''}`}    onClick={() => setTab('tasks')}>⏰ Tâches</button>
        <button className={`panel-tab ${tab==='alerts'?'active':''}`}   onClick={() => { setTab('alerts'); }}>
          🔔 Alertes {unread > 0 && <span className="aut-badge">{unread}</span>}
        </button>
        <button className={`panel-tab ${tab==='monitors'?'active':''}`} onClick={() => setTab('monitors')}>🖥️ Moniteurs</button>
      </div>
      <div className="panel-body">
        {tab === 'tasks'    && <TasksTab />}
        {tab === 'alerts'   && <AlertsTab onRead={refreshUnread} />}
        {tab === 'monitors' && <MonitorsTab />}
      </div>
    </div>
  )
}

// ── Tâches planifiées ─────────────────────────────────────────────────────────
function TasksTab() {
  const [tasks,   setTasks]   = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try { const d = await api('/autonomy/tasks'); setTasks(d.tasks || []) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const toggle = async (id) => { await api(`/autonomy/tasks/${id}/toggle`, { method:'PATCH' }); load() }
  const del    = async (id) => { await api(`/autonomy/tasks/${id}`,         { method:'DELETE' }); load() }
  const runNow = async (id) => { await api(`/autonomy/tasks/${id}/run`,     { method:'POST' });  load() }

  const fmtInterval = (t) => {
    if (t.schedule_type === 'cron')     return `⏱ ${t.cron}`
    if (t.schedule_type === 'once')     return `🗓 ${t.run_at ? new Date(t.run_at).toLocaleString('fr-FR') : '?'}`
    const s = t.interval_seconds
    if (s < 60)   return `toutes les ${s}s`
    if (s < 3600) return `toutes les ${Math.round(s/60)}min`
    return `toutes les ${Math.round(s/3600)}h`
  }

  return (
    <div className="lv-section">
      <button className="cv-btn lv-add-btn" onClick={() => setShowAdd(v => !v)}>
        {showAdd ? '✕ Annuler' : '+ Nouvelle tâche'}
      </button>
      {showAdd && <TaskForm onSaved={() => { setShowAdd(false); load() }} />}

      {loading && <div className="cv-hint">Chargement…</div>}
      {!loading && tasks.length === 0 && <div className="cv-hint">Aucune tâche planifiée. Crée-en une !</div>}

      {tasks.map(t => (
        <div key={t.id} className={`aut-task-card ${!t.enabled ? 'disabled' : ''}`}>
          <div className="aut-task-header">
            <div className="aut-task-info">
              <span className="aut-task-name">{t.name}</span>
              <span className="aut-kind-badge">{t.kind}</span>
            </div>
            <div className="aut-task-actions">
              <button className="cv-btn-icon aut-run-btn" onClick={() => runNow(t.id)} title="Exécuter maintenant">▶</button>
              <button className="cv-btn-icon" onClick={() => toggle(t.id)} title={t.enabled ? 'Désactiver' : 'Activer'}>
                {t.enabled ? '⏸' : '▶️'}
              </button>
              <button className="kv-del-btn" onClick={() => del(t.id)}>✕</button>
            </div>
          </div>
          <div className="aut-task-meta">
            <code className="aut-task-cmd">{t.command || t.url || '—'}</code>
            <span className="aut-task-sched">{fmtInterval(t)}</span>
          </div>
          {t.next_run && (
            <div className="aut-task-next">
              Prochain : {new Date(t.next_run).toLocaleString('fr-FR')}
            </div>
          )}
          {t.last_run && (
            <div className="aut-task-next" style={{ opacity: 0.6 }}>
              Dernier : {new Date(t.last_run).toLocaleString('fr-FR')} · {t.run_count} exéc.
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function TaskForm({ onSaved }) {
  const [name,     setName]     = useState('')
  const [kind,     setKind]     = useState('shell')
  const [command,  setCommand]  = useState('')
  const [url,      setUrl]      = useState('')
  const [schedType,setSchedType]= useState('interval')
  const [interval, setInterval] = useState(3600)
  const [cron,     setCron]     = useState('0 * * * *')
  const [runAt,    setRunAt]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const presets = [
    { label: 'Toutes les heures', type:'interval', val: 3600 },
    { label: 'Toutes les 30min',  type:'interval', val: 1800 },
    { label: 'Chaque jour 8h',    type:'cron',     val: '0 8 * * *' },
    { label: 'Chaque lundi 9h',   type:'cron',     val: '0 9 * * 1' },
  ]

  const save = async () => {
    if (!name.trim()) { setError('Nom requis'); return }
    setLoading(true); setError('')
    try {
      const body = {
        name, kind, command: kind==='shell'?command:undefined,
        url: kind==='http_check'?url:undefined,
        schedule_type: schedType,
        interval_seconds: schedType==='interval' ? Number(interval) : 3600,
        cron: schedType==='cron' ? cron : undefined,
        run_at: schedType==='once' ? runAt : undefined,
      }
      const res = await apiFetch('/autonomy/tasks', { method:'POST', body: JSON.stringify(body) })
      const d = await res.json()
      if (!res.ok) { setError(d.detail || 'Erreur'); return }
      onSaved()
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="lv-add-form">
      <div className="cv-row">
        <input className="cv-input" value={name} onChange={e => setName(e.target.value)} placeholder="Nom de la tâche *" />
        <select className="cv-select" value={kind} onChange={e => setKind(e.target.value)}>
          <option value="shell">🖥️ Shell</option>
          <option value="http_check">🌐 HTTP Check</option>
        </select>
      </div>

      {kind === 'shell'      && <input className="cv-input" value={command} onChange={e => setCommand(e.target.value)} placeholder="Commande (ex: df -h, systemctl status nginx…)" />}
      {kind === 'http_check' && <input className="cv-input" value={url}     onChange={e => setUrl(e.target.value)}     placeholder="URL (ex: http://localhost:8001/)" />}

      <div className="aut-presets">
        {presets.map((p, i) => (
          <button key={i} className="vis-quick-btn" onClick={() => {
            setSchedType(p.type)
            if (p.type === 'interval') setInterval(p.val)
            else setCron(p.val)
          }}>{p.label}</button>
        ))}
      </div>

      <div className="cv-row">
        <select className="cv-select" value={schedType} onChange={e => setSchedType(e.target.value)}>
          <option value="interval">⏱ Intervalle</option>
          <option value="cron">📅 Cron</option>
          <option value="once">1️⃣ Une fois</option>
        </select>
        {schedType === 'interval' && (
          <input type="number" className="cv-input" value={interval} onChange={e => setInterval(e.target.value)}
            placeholder="Secondes" min="30" />
        )}
        {schedType === 'cron' && (
          <input className="cv-input" value={cron} onChange={e => setCron(e.target.value)} placeholder="0 * * * *" />
        )}
        {schedType === 'once' && (
          <input type="datetime-local" className="cv-input" value={runAt} onChange={e => setRunAt(e.target.value)} />
        )}
        <button className="cv-btn cv-btn-green" onClick={save} disabled={loading}>
          {loading ? '…' : 'Créer'}
        </button>
      </div>
      {error && <div className="cv-error">{error}</div>}
    </div>
  )
}

// ── Alertes proactives ────────────────────────────────────────────────────────
function AlertsTab({ onRead }) {
  const [alerts,  setAlerts]  = useState([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try { const d = await api('/autonomy/alerts?limit=50'); setAlerts(d.alerts || []) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const dismiss  = async (id) => { await api(`/autonomy/alerts/${id}`, { method:'DELETE' }); load(); onRead?.() }
  const readAll  = async ()   => { await api('/autonomy/alerts/read-all', { method:'POST' }); load(); onRead?.() }
  const clearAll = async ()   => { await api('/autonomy/alerts', { method:'DELETE' }); load(); onRead?.() }

  return (
    <div className="lv-section">
      <div className="cv-row" style={{ marginBottom: 0 }}>
        <button className="cv-btn-icon" onClick={load} title="Rafraîchir">↻</button>
        <button className="cv-btn" style={{ fontSize:'0.76rem', padding:'5px 10px' }} onClick={readAll}>Tout lire</button>
        <button className="cv-btn" style={{ fontSize:'0.76rem', padding:'5px 10px', background:'#6b7280' }} onClick={clearAll}>Tout effacer</button>
      </div>

      {loading && <div className="cv-hint">Chargement…</div>}
      {!loading && alerts.length === 0 && (
        <div className="cv-hint">
          <div style={{ fontSize: '2rem', marginBottom: 8 }}>🔔</div>
          Aucune alerte. Le système surveille en arrière-plan.
        </div>
      )}

      {alerts.map(a => (
        <div key={a.id} className={`aut-alert-card ${!a.read ? 'unread' : ''}`}
          style={{ borderLeftColor: LEVEL_COLOR[a.level] || '#888' }}>
          <div className="aut-alert-header">
            <span className="aut-alert-icon">{LEVEL_ICON[a.level] || 'ℹ️'}</span>
            <span className="aut-alert-title">{a.title}</span>
            <span className="aut-alert-source">{a.source}</span>
            <button className="kv-del-btn" onClick={() => dismiss(a.id)}>✕</button>
          </div>
          <div className="aut-alert-body">{a.body}</div>
          <div className="aut-alert-ts">{new Date(a.ts).toLocaleString('fr-FR')}</div>
        </div>
      ))}
    </div>
  )
}

// ── Moniteurs ─────────────────────────────────────────────────────────────────
function MonitorsTab() {
  const [monitors, setMonitors] = useState([])
  const [snap,     setSnap]     = useState(null)
  const [loading,  setLoading]  = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [m, s] = await Promise.all([
        api('/autonomy/monitors'),
        api('/autonomy/snapshot'),
      ])
      setMonitors(m.monitors || []); setSnap(s)
    } finally { setLoading(false) }
  }
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t) }, [])

  const bar = (pct, warn=80, crit=90) => {
    const color = pct >= crit ? '#f87171' : pct >= warn ? '#fbbf24' : '#34d399'
    return (
      <div className="aut-metric-bar">
        <div className="aut-metric-fill" style={{ width:`${Math.min(pct,100)}%`, background: color }} />
      </div>
    )
  }

  return (
    <div className="lv-section">
      {/* Snapshot métriques */}
      {snap && !snap.error && (
        <div className="aut-snap-grid">
          <div className="aut-snap-card">
            <div className="aut-snap-label">CPU</div>
            <div className="aut-snap-val">{snap.cpu_pct}%</div>
            {bar(snap.cpu_pct)}
          </div>
          <div className="aut-snap-card">
            <div className="aut-snap-label">RAM</div>
            <div className="aut-snap-val">{snap.ram_pct}%</div>
            {bar(snap.ram_pct)}
            <div className="aut-snap-sub">{snap.ram_used_gb}GB / {snap.ram_total_gb}GB</div>
          </div>
          <div className="aut-snap-card">
            <div className="aut-snap-label">Disque</div>
            <div className="aut-snap-val">{snap.disk_pct}%</div>
            {bar(snap.disk_pct, 80, 95)}
            <div className="aut-snap-sub">{snap.disk_free_gb}GB libres</div>
          </div>
          <div className="aut-snap-card">
            <div className="aut-snap-label">Processus</div>
            <div className="aut-snap-val">{snap.processes}</div>
            <div className="aut-snap-sub">↑{snap.net_sent_mb}MB ↓{snap.net_recv_mb}MB</div>
          </div>
        </div>
      )}

      {/* Liste moniteurs */}
      <div className="vis-label" style={{ margin: '8px 0 4px' }}>Moniteurs actifs</div>
      {loading && monitors.length === 0 && <div className="cv-hint">Chargement…</div>}
      {monitors.map(m => (
        <div key={m.id} className="aut-monitor-row">
          <div className={`aut-monitor-dot ${m.enabled ? 'on' : 'off'}`} />
          <div className="aut-monitor-info">
            <div className="aut-monitor-name">{m.name}</div>
            <div className="aut-monitor-desc">{m.description}</div>
          </div>
          {m.next_run && (
            <div className="aut-monitor-next">
              {new Date(m.next_run).toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' })}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
