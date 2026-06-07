/**
 * REPORTS — Génération et téléchargement de rapports PDF.
 */
import { useState, useEffect } from 'react'
import { apiFetch, auth } from '../utils/auth'

function GeneratorSection({ type, title, icon, jobs, incidents, onGenerate, generating }) {
  const [selectedJob, setSelectedJob]       = useState('')
  const [selectedIncident, setSelectedIncident] = useState('')

  const submit = () => {
    const payload = {}
    if (type === 'pentest'   && selectedJob)      payload.job_id = selectedJob
    if (type === 'incident'  && selectedIncident) payload.incident_id = selectedIncident
    onGenerate(type, payload)
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">{icon}</span>
        <span>{title}</span>
      </div>

      {type === 'pentest' && jobs?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 4 }}>Sélectionner une opération</div>
          <select
            className="soc-select"
            style={{ width: '100%' }}
            value={selectedJob}
            onChange={e => setSelectedJob(e.target.value)}
          >
            <option value="">— Choisir un job —</option>
            {jobs.map(j => (
              <option key={j.job_id || j.id} value={j.job_id || j.id}>
                {j.target} — {j.status} ({j.job_id || j.id})
              </option>
            ))}
          </select>
        </div>
      )}

      {type === 'incident' && incidents?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 4 }}>Sélectionner un incident</div>
          <select
            className="soc-select"
            style={{ width: '100%' }}
            value={selectedIncident}
            onChange={e => setSelectedIncident(e.target.value)}
          >
            <option value="">— Choisir un incident —</option>
            {incidents.map(inc => (
              <option key={inc.id} value={inc.id}>
                {inc.title} — {inc.severity}
              </option>
            ))}
          </select>
        </div>
      )}

      <button
        className="aegis-launch-btn"
        style={{ width: '100%' }}
        onClick={submit}
        disabled={generating === type ||
          (type === 'pentest'  && jobs?.length > 0 && !selectedJob) ||
          (type === 'incident' && incidents?.length > 0 && !selectedIncident)
        }
      >
        {generating === type ? '⏳ Génération en cours…' : `Générer ${title}`}
      </button>
    </div>
  )
}

const FMT_SIZE = bytes => {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export default function ReportsView() {
  const [reports,   setReports]   = useState([])
  const [jobs,      setJobs]      = useState([])
  const [incidents, setIncidents] = useState([])
  const [generating, setGenerating] = useState(null)
  const [error, setError]         = useState(null)
  const [success, setSuccess]     = useState(null)

  const loadReports = () => {
    apiFetch('/reports/list').then(r => r.json()).then(d => setReports(d.reports || d || [])).catch(() => {})
  }

  useEffect(() => {
    loadReports()
    apiFetch('/pentest/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
    apiFetch('/soc/incidents?per_page=20').then(r => r.json()).then(d => setIncidents(d.incidents || [])).catch(() => {})
    const t = setInterval(loadReports, 15000)
    return () => clearInterval(t)
  }, [])

  const generate = async (type, payload = {}) => {
    setGenerating(type)
    setError(null)
    setSuccess(null)
    try {
      const res = await apiFetch(`/reports/generate/${type}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setSuccess(`Rapport généré : ${data.filename || data.file || type}`)
      loadReports()
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(null)
    }
  }

  const download = (filename) => {
    const token = auth.getToken()
    window.open(`/api/reports/download/${filename}${token ? `?token=${token}` : ''}`, '_blank')
  }

  const TYPE_BADGE_COLOR = {
    pentest:  '#8b5cf6',
    incident: '#ef4444',
    weekly:   '#38bdf8',
    soc:      '#f97316',
    default:  '#64748b',
  }

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">📄</span>
          <div>
            <div className="aegis-title">REPORTS</div>
            <div className="aegis-subtitle">Génération PDF · Pentest · SOC · Weekly Threat</div>
          </div>
        </div>
      </div>

      {error   && <div className="osint-error-banner">{error}</div>}
      {success && <div className="osint-success-banner">{success}</div>}

      <div className="reports-generators-grid">
        <GeneratorSection
          type="pentest"
          title="Pentest Report"
          icon="⚔️"
          jobs={jobs}
          onGenerate={generate}
          generating={generating}
        />
        <GeneratorSection
          type="incident"
          title="SOC Incident Report"
          icon="🚨"
          incidents={incidents}
          onGenerate={generate}
          generating={generating}
        />
        <GeneratorSection
          type="weekly"
          title="Weekly Threat Report"
          icon="📊"
          onGenerate={generate}
          generating={generating}
        />
      </div>

      <div className="aegis-panel" style={{ marginTop: 12 }}>
        <div className="aegis-panel-header">
          <span className="aegis-panel-icon">📁</span>
          <span>Rapports générés</span>
          <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>
            {reports.length} fichiers
          </span>
        </div>

        {reports.length === 0 ? (
          <div className="aegis-feed-empty">Aucun rapport généré — lancez une génération ci-dessus</div>
        ) : (
          <div className="creds-vault-table">
            <div className="creds-vault-header" style={{ gridTemplateColumns: '2fr 80px 100px 60px 80px' }}>
              <span>Nom du fichier</span><span>Type</span><span>Date</span><span>Taille</span><span>Action</span>
            </div>
            {reports.map((r, i) => {
              const typeKey = (r.type || r.report_type || '').toLowerCase()
              const color = TYPE_BADGE_COLOR[typeKey] || TYPE_BADGE_COLOR.default
              return (
                <div key={i} className="creds-vault-row" style={{ gridTemplateColumns: '2fr 80px 100px 60px 80px' }}>
                  <span className="creds-user" style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {r.filename || r.file || r.name || '—'}
                  </span>
                  <span>
                    {typeKey && (
                      <span style={{
                        background: `${color}22`, color, border: `1px solid ${color}55`,
                        borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', fontWeight: 700,
                      }}>
                        {typeKey}
                      </span>
                    )}
                  </span>
                  <span className="creds-date">
                    {r.created_at || r.generated_at
                      ? new Date(r.created_at || r.generated_at).toLocaleString('fr-FR')
                      : '—'
                    }
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
                    {FMT_SIZE(r.size || r.file_size)}
                  </span>
                  <span>
                    <button
                      className="osint-reload-btn"
                      onClick={() => download(r.filename || r.file || r.name)}
                      style={{ color: 'var(--accent)' }}
                      title="Télécharger"
                    >
                      ↓ DL
                    </button>
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
