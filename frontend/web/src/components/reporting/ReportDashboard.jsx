/**
 * ReportDashboard — Tableau de bord de génération de rapports d'audit.
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../../utils/auth'
import ReportPreview from './ReportPreview'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(2)} Mo`
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function RiskBadge({ score }) {
  if (score == null) return <span style={{ color: '#999' }}>—</span>
  const color =
    score >= 75 ? '#ef4444' :
    score >= 50 ? '#f97316' :
    score >= 25 ? '#eab308' : '#22c55e'
  const label =
    score >= 75 ? 'CRITIQUE' :
    score >= 50 ? 'ÉLEVÉ' :
    score >= 25 ? 'MODÉRÉ' : 'FAIBLE'
  return (
    <span style={{
      background: color, color: 'white',
      padding: '2px 10px', borderRadius: 12,
      fontSize: 11, fontWeight: 'bold', letterSpacing: 1,
    }}>
      {score.toFixed(0)} — {label}
    </span>
  )
}

function FormatBadge({ format }) {
  const colors = {
    pdf: '#ef4444', html: '#3b82f6', docx: '#8b5cf6',
    markdown: '#22c55e', json: '#f59e0b',
  }
  return (
    <span style={{
      background: colors[format] || '#6b7280',
      color: 'white', padding: '2px 8px',
      borderRadius: 4, fontSize: 11, fontWeight: 'bold',
      textTransform: 'uppercase',
    }}>
      {format}
    </span>
  )
}

const GENERATION_STEPS = [
  'Collecte des preuves…',
  'Analyse des données…',
  'Calcul du score de risque…',
  'Génération du document…',
  'Finalisation…',
]

// ── Composant principal ───────────────────────────────────────────────────────

export default function ReportDashboard() {
  const [campaignId, setCampaignId] = useState('')
  const [format, setFormat] = useState('pdf')
  const [title, setTitle] = useState('')
  const [companyName, setCompanyName] = useState('AEGIS AI')
  const [options, setOptions] = useState({
    include_screenshots: true,
    include_network: true,
    include_mitre: true,
    include_recommendations: true,
  })

  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const [error, setError] = useState('')
  const [latestReport, setLatestReport] = useState(null)

  const [reports, setReports] = useState([])
  const [loadingReports, setLoadingReports] = useState(false)

  const [previewReport, setPreviewReport] = useState(null)

  const progressRef = useRef(null)
  const pollRef = useRef(null)

  // ── Chargement des rapports ─────────────────────────────────────────────────

  const loadReports = async (cid) => {
    if (!cid?.trim()) return
    setLoadingReports(true)
    try {
      const res = await apiFetch(`/reports/audit/campaign/${cid.trim()}`)
      if (res.ok) {
        const data = await res.json()
        setReports(data.reports || [])
      }
    } catch (e) {
      console.error('loadReports:', e)
    } finally {
      setLoadingReports(false)
    }
  }

  // ── Animation progression ───────────────────────────────────────────────────

  const startProgress = () => {
    setProgress(0)
    setStepIndex(0)
    let p = 0
    let step = 0
    clearInterval(progressRef.current)
    progressRef.current = setInterval(() => {
      p += Math.random() * 6 + 2
      if (p > 95) p = 95
      setProgress(p)
      const s = Math.floor((p / 100) * (GENERATION_STEPS.length - 1))
      if (s !== step) {
        step = s
        setStepIndex(s)
      }
    }, 400)
  }

  const stopProgress = () => {
    clearInterval(progressRef.current)
    setProgress(100)
    setStepIndex(GENERATION_STEPS.length - 1)
  }

  // ── Polling du statut ───────────────────────────────────────────────────────

  const pollStatus = (reportId) => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/reports/audit/status/${reportId}`)
        if (res.ok) {
          const data = await res.json()
          if (data.status === 'ready' || data.status === 'error') {
            clearInterval(pollRef.current)
            stopProgress()
            setGenerating(false)
            if (data.status === 'ready') {
              setLatestReport(data)
              await loadReports(campaignId)
            } else {
              setError('Erreur lors de la génération du rapport')
            }
          }
        }
      } catch (e) {
        clearInterval(pollRef.current)
        setGenerating(false)
        setError(`Erreur polling: ${e.message}`)
      }
    }, 2000)
  }

  // ── Génération ──────────────────────────────────────────────────────────────

  const handleGenerate = async () => {
    if (!campaignId.trim()) {
      setError('Veuillez saisir un Campaign ID')
      return
    }
    setError('')
    setLatestReport(null)
    setGenerating(true)
    startProgress()

    try {
      const res = await apiFetch('/reports/audit/generate', {
        method: 'POST',
        body: JSON.stringify({
          campaign_id: campaignId.trim(),
          format,
          options,
          title: title.trim() || undefined,
          company_name: companyName.trim() || undefined,
        }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data.status === 'ready') {
        stopProgress()
        setGenerating(false)
        setLatestReport(data)
        await loadReports(campaignId)
      } else {
        pollStatus(data.report_id)
      }
    } catch (e) {
      clearInterval(progressRef.current)
      setGenerating(false)
      setProgress(0)
      setError(`Erreur: ${e.message}`)
    }
  }

  // ── Téléchargement ──────────────────────────────────────────────────────────

  const handleDownload = async (reportId, filename) => {
    try {
      const res = await apiFetch(`/reports/audit/download/${reportId}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || `report-${reportId}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(`Erreur téléchargement: ${e.message}`)
    }
  }

  // ── Suppression ─────────────────────────────────────────────────────────────

  const handleDelete = async (reportId) => {
    if (!window.confirm('Supprimer ce rapport ?')) return
    try {
      const res = await apiFetch(`/reports/audit/${reportId}`, { method: 'DELETE' })
      if (res.ok) {
        setReports(prev => prev.filter(r => r.report_id !== reportId))
      }
    } catch (e) {
      setError(`Erreur suppression: ${e.message}`)
    }
  }

  // ── Cleanup ─────────────────────────────────────────────────────────────────

  useEffect(() => () => {
    clearInterval(progressRef.current)
    clearInterval(pollRef.current)
  }, [])

  // ── Rendu ───────────────────────────────────────────────────────────────────

  if (previewReport) {
    return (
      <ReportPreview
        reportId={previewReport.report_id}
        onClose={() => setPreviewReport(null)}
      />
    )
  }

  return (
    <div style={{ padding: '24px', color: '#1a1a2e', fontFamily: 'Arial, sans-serif', maxWidth: 1200, margin: '0 auto' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 26, color: '#1a237e', fontWeight: 'bold' }}>
            Rapport d'Audit
          </h1>
          <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>
            Génération de rapports d'audit professionnels multi-format
          </div>
        </div>
        <button
          onClick={() => { setTitle(''); setCampaignId(''); setReports([]); setLatestReport(null); }}
          style={{
            background: '#1a237e', color: 'white', border: 'none',
            padding: '10px 20px', borderRadius: 8, cursor: 'pointer',
            fontSize: 14, fontWeight: 'bold',
          }}
        >
          + Nouveau Rapport
        </button>
      </div>

      {/* ── Campaign ID ── */}
      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: 20, marginBottom: 20 }}>
        <label style={{ display: 'block', fontWeight: 'bold', color: '#1a237e', marginBottom: 8, fontSize: 13 }}>
          Campaign ID
        </label>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={campaignId}
            onChange={e => setCampaignId(e.target.value)}
            placeholder="ex: pentest-2026-01 ou op-alpha"
            style={{
              flex: 1, padding: '10px 14px', border: '1px solid #c7d2fe',
              borderRadius: 8, fontSize: 14, outline: 'none',
              background: 'white',
            }}
            onKeyDown={e => e.key === 'Enter' && loadReports(campaignId)}
          />
          <button
            onClick={() => loadReports(campaignId)}
            style={{
              background: '#e0e7ff', color: '#1a237e', border: 'none',
              padding: '10px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13,
            }}
          >
            Charger
          </button>
        </div>
      </div>

      {/* ── Formulaire de génération ── */}
      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 24, marginBottom: 20 }}>
        <h2 style={{ margin: '0 0 20px', fontSize: 16, color: '#1a237e' }}>Nouveau Rapport</h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', color: '#374151', marginBottom: 6 }}>
              Titre du rapport
            </label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Rapport d'Audit Sécurité Q1 2026"
              style={{
                width: '100%', padding: '9px 12px', border: '1px solid #d1d5db',
                borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', color: '#374151', marginBottom: 6 }}>
              Société / Organisation
            </label>
            <input
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder="AEGIS AI"
              style={{
                width: '100%', padding: '9px 12px', border: '1px solid #d1d5db',
                borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Format */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', color: '#374151', marginBottom: 8 }}>
            Format
          </label>
          <div style={{ display: 'flex', gap: 10 }}>
            {['pdf', 'html', 'docx', 'markdown'].map(f => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                style={{
                  padding: '8px 18px', borderRadius: 20,
                  border: `2px solid ${format === f ? '#1a237e' : '#d1d5db'}`,
                  background: format === f ? '#1a237e' : 'white',
                  color: format === f ? 'white' : '#374151',
                  cursor: 'pointer', fontWeight: 'bold', fontSize: 13,
                  textTransform: 'uppercase',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Options */}
        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', color: '#374151', marginBottom: 10 }}>
            Sections incluses
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {[
              { key: 'include_screenshots', label: 'Captures d\'écran' },
              { key: 'include_network', label: 'Réseau' },
              { key: 'include_mitre', label: 'MITRE ATT&CK' },
              { key: 'include_recommendations', label: 'Recommandations' },
            ].map(({ key, label }) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={options[key] !== false}
                  onChange={e => setOptions(prev => ({ ...prev, [key]: e.target.checked }))}
                  style={{ width: 16, height: 16, accentColor: '#1a237e' }}
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Erreur */}
        {error && (
          <div style={{
            background: '#fef2f2', border: '1px solid #fecaca',
            color: '#dc2626', padding: '10px 14px', borderRadius: 8,
            fontSize: 13, marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {/* Bouton générer */}
        <button
          onClick={handleGenerate}
          disabled={generating || !campaignId.trim()}
          style={{
            background: generating ? '#9ca3af' : '#1a237e',
            color: 'white', border: 'none', padding: '12px 32px',
            borderRadius: 8, cursor: generating ? 'not-allowed' : 'pointer',
            fontSize: 15, fontWeight: 'bold', width: '100%',
          }}
        >
          {generating ? 'Génération en cours…' : 'GÉNÉRER LE RAPPORT'}
        </button>
      </div>

      {/* ── Barre de progression ── */}
      {generating && (
        <div style={{
          background: '#f0f4ff', border: '1px solid #c7d2fe',
          borderRadius: 10, padding: 20, marginBottom: 20,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: '#1a237e', fontWeight: 'bold' }}>
              {GENERATION_STEPS[stepIndex]}
            </span>
            <span style={{ fontSize: 13, color: '#1a237e', fontWeight: 'bold' }}>
              {Math.round(progress)}%
            </span>
          </div>
          <div style={{ background: '#e0e7ff', borderRadius: 4, height: 8 }}>
            <div style={{
              background: '#1a237e', height: 8, borderRadius: 4,
              width: `${progress}%`, transition: 'width 0.4s ease',
            }} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {GENERATION_STEPS.map((step, i) => (
              <span key={i} style={{
                fontSize: 11, padding: '3px 8px', borderRadius: 10,
                background: i <= stepIndex ? '#1a237e' : '#e5e7eb',
                color: i <= stepIndex ? 'white' : '#9ca3af',
              }}>
                {step.replace('…', '')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Dernier rapport généré ── */}
      {latestReport && (
        <div style={{
          background: '#f0fdf4', border: '1px solid #86efac',
          borderRadius: 10, padding: 20, marginBottom: 20,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 'bold', color: '#166534', marginBottom: 6 }}>
                Rapport généré avec succès
              </div>
              <div style={{ fontSize: 13, color: '#374151' }}>
                <strong>{latestReport.title}</strong>
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                Score de risque : <RiskBadge score={latestReport.risk_score} /> &nbsp;|&nbsp;
                Format : <FormatBadge format={latestReport.format} /> &nbsp;|&nbsp;
                Taille : {formatSize(latestReport.file_size)}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {latestReport.format === 'html' && (
                <button
                  onClick={() => setPreviewReport(latestReport)}
                  style={{
                    background: '#3b82f6', color: 'white', border: 'none',
                    padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
                  }}
                >
                  Prévisualiser
                </button>
              )}
              <button
                onClick={() => handleDownload(latestReport.report_id, latestReport.file_path?.split('/').pop())}
                style={{
                  background: '#166534', color: 'white', border: 'none',
                  padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
                }}
              >
                Télécharger
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Liste des rapports ── */}
      {(reports.length > 0 || loadingReports) && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{
            padding: '14px 20px', background: '#f8fafc',
            borderBottom: '1px solid #e2e8f0', display: 'flex',
            justifyContent: 'space-between', alignItems: 'center',
          }}>
            <h3 style={{ margin: 0, fontSize: 15, color: '#1a237e' }}>
              Rapports — {campaignId}
            </h3>
            <span style={{ fontSize: 12, color: '#6b7280' }}>{reports.length} rapport(s)</span>
          </div>

          {loadingReports ? (
            <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>Chargement…</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f8fafc' }}>
                  {['Titre', 'Format', 'Date', 'Taille', 'Pages', 'Risque', 'Actions'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      borderBottom: '1px solid #e2e8f0', color: '#374151',
                      fontSize: 12, fontWeight: 600,
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map((r, i) => (
                  <tr key={r.report_id} style={{ background: i % 2 === 0 ? 'white' : '#f8fafc' }}>
                    <td style={{ padding: '10px 14px', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.title}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <FormatBadge format={r.format} />
                    </td>
                    <td style={{ padding: '10px 14px', color: '#6b7280', whiteSpace: 'nowrap' }}>
                      {formatDate(r.created_at)}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#6b7280' }}>
                      {formatSize(r.file_size)}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#6b7280' }}>
                      {r.pages_count || '—'}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <RiskBadge score={r.risk_score} />
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {r.format === 'html' && (
                          <button
                            onClick={() => setPreviewReport(r)}
                            style={{
                              background: '#dbeafe', color: '#1d4ed8',
                              border: 'none', padding: '4px 10px',
                              borderRadius: 4, cursor: 'pointer', fontSize: 11,
                            }}
                          >
                            Preview
                          </button>
                        )}
                        <button
                          onClick={() => handleDownload(r.report_id, r.file_path?.split('/').pop())}
                          style={{
                            background: '#dcfce7', color: '#166534',
                            border: 'none', padding: '4px 10px',
                            borderRadius: 4, cursor: 'pointer', fontSize: 11,
                          }}
                        >
                          DL
                        </button>
                        <button
                          onClick={() => handleDelete(r.report_id)}
                          style={{
                            background: '#fee2e2', color: '#dc2626',
                            border: 'none', padding: '4px 10px',
                            borderRadius: 4, cursor: 'pointer', fontSize: 11,
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
