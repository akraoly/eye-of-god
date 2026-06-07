/**
 * LAB — Environnements virtuels de TP/CTF.
 */
import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

const CATEGORY_COLOR = {
  'Active Directory': '#8b5cf6',
  'Network':          '#38bdf8',
  'Web':              '#4ade80',
  'Exploitation':     '#ef4444',
  'Forensics':        '#fbbf24',
  'OSINT':            '#06b6d4',
  'Malware':          '#f97316',
  default:            '#64748b',
}

function TemplateCard({ tpl, onDeploy }) {
  const color = CATEGORY_COLOR[tpl.category] || CATEGORY_COLOR.default
  return (
    <div className="lab-template-card">
      <div className="lab-template-icon">{tpl.icon || '🖥️'}</div>
      <div className="lab-template-info">
        <div className="lab-template-name">{tpl.name}</div>
        <div className="lab-template-desc">{tpl.description || ''}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          {tpl.category && (
            <span style={{
              background: `${color}22`, color, border: `1px solid ${color}55`,
              borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', fontWeight: 700,
            }}>
              {tpl.category}
            </span>
          )}
          {tpl.difficulty && (
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>{tpl.difficulty}</span>
          )}
        </div>
      </div>
      <button className="lab-deploy-btn" onClick={() => onDeploy(tpl)}>
        Déployer
      </button>
    </div>
  )
}

function DeployModal({ template, onClose, onDeploy }) {
  const [name, setName] = useState(template ? `${template.name}-${Date.now().toString(36)}` : '')
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState(null)

  const deploy = async () => {
    if (!name.trim()) return
    setDeploying(true)
    setError(null)
    try {
      const res = await apiFetch('/lab/deploy', {
        method: 'POST',
        body: JSON.stringify({ template_id: template?.id || template?.name, lab_name: name.trim() }),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      onDeploy(data)
      onClose()
    } catch (err) {
      setError(err.message)
      setDeploying(false)
    }
  }

  return (
    <div className="lab-modal-overlay" onClick={onClose}>
      <div className="lab-modal" onClick={e => e.stopPropagation()}>
        <div className="lab-modal-header">
          <span>Déployer : {template?.name}</span>
          <button className="compass-close" onClick={onClose}>✕</button>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 4 }}>Nom du lab</div>
          <input
            className="aegis-target-input"
            style={{ width: '100%' }}
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Mon lab…"
          />
        </div>
        {template?.description && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text2)', marginBottom: 12, lineHeight: 1.5 }}>
            {template.description}
          </div>
        )}
        {error && <div className="osint-error-banner">{error}</div>}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="aegis-stop-btn" onClick={onClose}>Annuler</button>
          <button className="aegis-launch-btn" onClick={deploy} disabled={deploying || !name.trim()}>
            {deploying ? '⏳ Déploiement…' : '▶ Déployer'}
          </button>
        </div>
      </div>
    </div>
  )
}

function LabDetailModal({ lab, onClose }) {
  return (
    <div className="lab-modal-overlay" onClick={onClose}>
      <div className="lab-modal" onClick={e => e.stopPropagation()}>
        <div className="lab-modal-header">
          <span>Lab : {lab.name}</span>
          <button className="compass-close" onClick={onClose}>✕</button>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 6 }}>IP Principale</div>
          <code style={{ color: 'var(--accent)' }}>{lab.ip || lab.address || '—'}</code>
        </div>
        {(lab.services || lab.ports || []).length > 0 && (
          <div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 6 }}>Services exposés</div>
            <div className="lab-services-table">
              {(lab.services || lab.ports || []).map((s, i) => (
                <div key={i} className="lab-service-row">
                  <span style={{ color: 'var(--accent)', fontFamily: 'monospace' }}>
                    {s.port || s}
                  </span>
                  <span>{s.service || s.name || '—'}</span>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                    {s.protocol || 'tcp'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <button className="aegis-stop-btn" onClick={onClose}>Fermer</button>
        </div>
      </div>
    </div>
  )
}

export default function LabView() {
  const [templates, setTemplates] = useState([])
  const [instances, setInstances] = useState([])
  const [loading, setLoading]     = useState(true)
  const [deployModal, setDeployModal] = useState(null)
  const [detailModal, setDetailModal] = useState(null)

  const loadAll = () => {
    apiFetch('/lab/templates').then(r => r.json()).then(d => setTemplates(d.templates || d || [])).catch(() => {})
    apiFetch('/lab/instances').then(r => r.json()).then(d => {
      setInstances(d.instances || d || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadAll()
    const t = setInterval(() => {
      apiFetch('/lab/instances').then(r => r.json()).then(d => setInstances(d.instances || d || [])).catch(() => {})
    }, 10000)
    return () => clearInterval(t)
  }, [])

  const stopInstance = async (id) => {
    try {
      await apiFetch(`/lab/instances/${id}/stop`, { method: 'POST' })
      loadAll()
    } catch {}
  }

  const scanInstance = async (instance) => {
    try {
      await apiFetch(`/lab/instances/${instance.id}/scan`, { method: 'POST' })
    } catch {}
  }

  const STATUS_COLOR = {
    running:  '#4ade80',
    starting: '#fbbf24',
    stopped:  '#64748b',
    error:    '#ef4444',
  }

  return (
    <div className="osint-view">
      {deployModal && (
        <DeployModal
          template={deployModal}
          onClose={() => setDeployModal(null)}
          onDeploy={loadAll}
        />
      )}
      {detailModal && (
        <LabDetailModal
          lab={detailModal}
          onClose={() => setDetailModal(null)}
        />
      )}

      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🧬</span>
          <div>
            <div className="aegis-title">LAB ENVIRONMENTS</div>
            <div className="aegis-subtitle">Templates · Déploiement · Instances actives</div>
          </div>
        </div>
        <div className="aegis-header-right">
          <span style={{ fontSize: '0.7rem', color: instances.length > 0 ? '#4ade80' : 'var(--text3)' }}>
            {instances.length} instance{instances.length !== 1 ? 's' : ''} active{instances.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {instances.length > 0 && (
        <div className="aegis-panel" style={{ marginBottom: 12 }}>
          <div className="aegis-panel-header">
            <span className="aegis-panel-icon">🟢</span>
            <span>Instances actives</span>
          </div>
          <div className="lab-instances-table">
            {instances.map((inst, i) => (
              <div key={inst.id || i} className="lab-instance-row">
                <span style={{ color: STATUS_COLOR[inst.status] || 'var(--text2)', fontSize: '0.7rem' }}>●</span>
                <span className="lab-inst-name">{inst.name || inst.lab_name || '—'}</span>
                <span className="lab-inst-ip" style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>
                  {inst.ip || inst.address || '—'}
                </span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                  {(inst.ports || inst.services || []).length} ports
                </span>
                <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button
                    className="osint-reload-btn"
                    onClick={() => setDetailModal(inst)}
                    title="Détails"
                  >
                    🔍
                  </button>
                  <button
                    className="osint-reload-btn"
                    onClick={() => scanInstance(inst)}
                    title="Scanner"
                    style={{ color: 'var(--accent)' }}
                  >
                    Scan
                  </button>
                  <button
                    className="aegis-stop-btn"
                    onClick={() => stopInstance(inst.id)}
                    style={{ padding: '3px 10px', fontSize: '0.7rem' }}
                  >
                    Stop
                  </button>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="aegis-panel">
        <div className="aegis-panel-header">
          <span className="aegis-panel-icon">📦</span>
          <span>Galerie de templates</span>
          <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>
            {templates.length} templates
          </span>
        </div>
        {loading ? (
          <div className="aegis-feed-empty">Chargement des templates…</div>
        ) : templates.length === 0 ? (
          <div className="aegis-feed-empty">Aucun template disponible — configurez le backend Lab</div>
        ) : (
          <div className="lab-template-gallery">
            {templates.map((tpl, i) => (
              <TemplateCard key={tpl.id || i} tpl={tpl} onDeploy={setDeployModal} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
