import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../utils/auth'

function fetchDiag() {
  return apiFetch('/system/diagnostic').then(r => r.json())
}

// ── Gauge circulaire ──────────────────────────────────────────────────────────
function Gauge({ value, label, unit = '%', color }) {
  const r = 28, c = 2 * Math.PI * r
  const pct = Math.min(100, Math.max(0, value))
  const stroke = c - (pct / 100) * c
  const col = pct > 85 ? '#ff4466' : pct > 60 ? '#e8c14a' : color || 'var(--accent)'
  return (
    <div className="diag-gauge">
      <svg viewBox="0 0 72 72" className="diag-gauge-svg">
        <circle cx="36" cy="36" r={r} fill="none" stroke="var(--border)" strokeWidth="5" />
        <circle cx="36" cy="36" r={r} fill="none" stroke={col} strokeWidth="5"
          strokeDasharray={c} strokeDashoffset={stroke}
          strokeLinecap="round" transform="rotate(-90 36 36)" />
        <text x="36" y="36" textAnchor="middle" dominantBaseline="central"
          fill={col} fontSize="11" fontWeight="800" fontFamily="var(--font-ui)">
          {Math.round(pct)}{unit}
        </text>
      </svg>
      <div className="diag-gauge-label">{label}</div>
    </div>
  )
}

// ── Badge statut ──────────────────────────────────────────────────────────────
function StatusDot({ status }) {
  const colors = { online: '#00ff88', offline: '#ff4466', ready: '#00d4ff', degraded: '#e8c14a' }
  return (
    <span className="diag-status-dot" style={{ background: colors[status] || '#888' }} />
  )
}

// ── Barre de progression ──────────────────────────────────────────────────────
function Bar({ value, max = 100 }) {
  const pct = Math.min(100, (value / max) * 100)
  const col = pct > 85 ? '#ff4466' : pct > 60 ? '#e8c14a' : 'var(--accent)'
  return (
    <div className="diag-bar-track">
      <div className="diag-bar-fill" style={{ width: `${pct}%`, background: col }} />
    </div>
  )
}

export default function DiagnosticView() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      const d = await fetchDiag()
      setData(d)
      setLastRefresh(new Date())
      setError(null)
    } catch (e) {
      setError('Impossible de joindre le backend — port 8001 ?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [autoRefresh, refresh])

  const s = data?.system

  return (
    <div className="diag-view">
      {/* ── En-tête ── */}
      <div className="diag-header">
        <div className="diag-header-left">
          <span className="diag-header-icon">🩺</span>
          <div>
            <div className="diag-header-title">Diagnostic Système</div>
            <div className="diag-header-sub">
              {s ? `${s.hostname} · ${s.os} · Uptime système: ${s.sys_uptime} · Backend: ${s.app_uptime}` : 'Chargement…'}
            </div>
          </div>
        </div>
        <div className="diag-header-actions">
          <button
            className={`diag-btn-auto ${autoRefresh ? 'active' : ''}`}
            onClick={() => setAutoRefresh(v => !v)}
            title="Auto-refresh 5s"
          >
            {autoRefresh ? '⟳ Auto' : '⟳ Manuel'}
          </button>
          <button className="diag-btn-refresh" onClick={refresh} disabled={loading}>
            {loading ? '…' : '↻ Actualiser'}
          </button>
          {lastRefresh && (
            <span className="diag-last-refresh">
              {lastRefresh.toLocaleTimeString('fr-FR')}
            </span>
          )}
        </div>
      </div>

      {error && <div className="diag-error">⚠️ {error}</div>}

      {data && (
        <>
          {/* ── Métriques système ── */}
          <div className="diag-section-title">⚙️ Ressources système</div>
          <div className="diag-metrics-row">
            <Gauge value={s.cpu_percent} label="CPU" color="var(--accent)" />
            <Gauge value={s.ram_percent} label="RAM" color="#7c3aed" />
            <Gauge value={s.disk_percent} label="Disque" color="#0891b2" />
            <div className="diag-metric-card">
              <div className="diag-metric-val">{s.ram_used_gb}<span className="diag-metric-unit">/{s.ram_total_gb} Go</span></div>
              <div className="diag-metric-label">RAM</div>
              <Bar value={s.ram_used_gb} max={s.ram_total_gb} />
            </div>
            <div className="diag-metric-card">
              <div className="diag-metric-val">{s.disk_used_gb}<span className="diag-metric-unit">/{s.disk_total_gb} Go</span></div>
              <div className="diag-metric-label">Disque</div>
              <Bar value={s.disk_used_gb} max={s.disk_total_gb} />
            </div>
            <div className="diag-metric-card">
              <div className="diag-metric-val">{s.cpu_count}</div>
              <div className="diag-metric-label">CPUs</div>
              <div className="diag-metric-sub">Load: {s.load_avg?.join(' / ')}</div>
            </div>
          </div>

          <div className="diag-two-col">
            {/* ── Services ── */}
            <div className="diag-card">
              <div className="diag-card-title">🔌 Services</div>
              {data.services.map(svc => (
                <div key={svc.name} className="diag-service-row">
                  <StatusDot status={svc.status} />
                  <div className="diag-service-info">
                    <span className="diag-service-name">{svc.name}</span>
                    {svc.port && <span className="diag-service-port">:{svc.port}</span>}
                    <span className="diag-service-detail">{svc.detail}</span>
                  </div>
                  <span className={`diag-service-badge ${svc.status}`}>{svc.status}</span>
                </div>
              ))}

              <div className="diag-card-title" style={{ marginTop: '14px' }}>🗄️ ChromaDB</div>
              <div className="diag-chroma-row">
                <StatusDot status={data.chroma.status === 'ok' ? 'online' : 'offline'} />
                <span className="diag-service-name">Vecteurs persistants</span>
                <span className="diag-chroma-stat">{data.chroma.collections} collections</span>
                <span className="diag-chroma-stat">{data.chroma.size_mb} Mo</span>
              </div>
            </div>

            {/* ── Agents ── */}
            <div className="diag-card">
              <div className="diag-card-title">🤖 Agents IA</div>
              <div className="diag-agents-grid">
                {data.agents.map(a => (
                  <div key={a.name} className="diag-agent-card">
                    <div className="diag-agent-header">
                      <StatusDot status={a.status} />
                      <span className="diag-agent-name">{a.name.toUpperCase()}</span>
                    </div>
                    <div className="diag-agent-desc">{a.description}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Base de données ── */}
          <div className="diag-card">
            <div className="diag-card-title">💾 Base de données — Tables</div>
            <div className="diag-db-grid">
              {data.db_stats.map(t => (
                <div key={t.table} className="diag-db-row">
                  <span className="diag-db-label">{t.label}</span>
                  <span className="diag-db-count">{t.count.toLocaleString('fr-FR')}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="diag-two-col">
            {/* ── Top processus ── */}
            <div className="diag-card">
              <div className="diag-card-title">📊 Top Processus</div>
              <table className="diag-proc-table">
                <thead>
                  <tr>
                    <th>PID</th><th>Nom</th><th>CPU%</th><th>MEM%</th><th>État</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_processes.map(p => (
                    <tr key={p.pid}>
                      <td className="diag-proc-pid">{p.pid}</td>
                      <td className="diag-proc-name">{p.name}</td>
                      <td className={`diag-proc-cpu ${p.cpu > 20 ? 'high' : ''}`}>{p.cpu}%</td>
                      <td>{p.mem}%</td>
                      <td><span className={`diag-proc-status ${p.status}`}>{p.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* ── Logs ── */}
            <div className="diag-card diag-card-logs">
              <div className="diag-card-title">📋 Logs récents</div>
              <div className="diag-log-box">
                {data.logs.length === 0
                  ? <div className="diag-log-empty">Aucun fichier log détecté</div>
                  : data.logs.map((line, i) => (
                    <div key={i} className={`diag-log-line ${
                      line.includes('ERROR') || line.includes('error') ? 'log-error' :
                      line.includes('WARNING') || line.includes('warn') ? 'log-warn' :
                      line.includes('INFO') ? 'log-info' : ''
                    }`}>{line}</div>
                  ))
                }
              </div>
            </div>
          </div>
        </>
      )}

      {loading && !data && (
        <div className="diag-loading">
          <div className="diag-loading-spinner" />
          <div>Analyse du système en cours…</div>
        </div>
      )}
    </div>
  )
}
