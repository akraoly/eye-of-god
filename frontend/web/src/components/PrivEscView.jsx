/**
 * PRIVESC — Privilege Escalation checks (Linux/Windows) + GTFOBins.
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const RISK_COLOR = {
  HIGH:   '#ef4444',
  MEDIUM: '#fbbf24',
  LOW:    '#4ade80',
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      className="osint-copy-btn"
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      title="Copier"
    >
      {copied ? '✓' : '⎘'}
    </button>
  )
}

function FindingCard({ finding }) {
  const [expanded, setExpanded] = useState(false)
  const risk = (finding.risk || finding.severity || 'LOW').toUpperCase()
  return (
    <div className="privesc-finding-card" style={{ borderLeft: `3px solid ${RISK_COLOR[risk] || '#64748b'}` }}>
      <div className="privesc-finding-header" onClick={() => setExpanded(v => !v)} style={{ cursor: 'pointer' }}>
        <span style={{
          fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 4,
          background: `${RISK_COLOR[risk] || '#64748b'}22`,
          color: RISK_COLOR[risk] || '#64748b',
          border: `1px solid ${RISK_COLOR[risk] || '#64748b'}55`,
        }}>
          {risk}
        </span>
        <span className="privesc-finding-name">{finding.technique || finding.name || finding.title || '—'}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text3)' }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>
      {expanded && (
        <div className="privesc-finding-body">
          {(finding.description || finding.detail) && (
            <div className="privesc-desc">{finding.description || finding.detail}</div>
          )}
          {(finding.exploit || finding.command || finding.exploit_command) && (
            <div className="privesc-cmd-block">
              <div className="privesc-cmd-header">
                <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>Commande</span>
                <CopyBtn text={finding.exploit || finding.command || finding.exploit_command} />
              </div>
              <code className="privesc-cmd-code">
                {finding.exploit || finding.command || finding.exploit_command}
              </code>
            </div>
          )}
          {finding.references?.length > 0 && (
            <div style={{ marginTop: 6, fontSize: '0.65rem', color: 'var(--text3)' }}>
              Refs : {finding.references.join(' · ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ResultsPanel({ findings }) {
  if (!findings?.length) return null
  const byRisk = ['HIGH', 'MEDIUM', 'LOW'].reduce((acc, r) => {
    const items = findings.filter(f => (f.risk || f.severity || '').toUpperCase() === r)
    if (items.length) acc[r] = items
    return acc
  }, {})
  const other = findings.filter(f => !['HIGH', 'MEDIUM', 'LOW'].includes((f.risk || f.severity || '').toUpperCase()))

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">📋</span>
        <span>Résultats</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>
          {findings.length} vecteurs
        </span>
      </div>
      {Object.entries(byRisk).map(([risk, items]) => (
        <div key={risk} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: RISK_COLOR[risk], marginBottom: 6 }}>
            {risk} ({items.length})
          </div>
          {items.map((f, i) => <FindingCard key={i} finding={f} />)}
        </div>
      ))}
      {other.map((f, i) => <FindingCard key={`o${i}`} finding={f} />)}
    </div>
  )
}

function GtfoBins() {
  const [binary, setBinary] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const lookup = async () => {
    if (!binary.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiFetch('/privesc/gtfobins', {
        method: 'POST',
        body: JSON.stringify({ binary: binary.trim() }),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      setResult(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📖</span>GTFOBins Lookup</div>
      <div className="aegis-launch-row">
        <input
          className="aegis-target-input"
          placeholder="Binaire (ex: find, python, vim, wget…)"
          value={binary}
          onChange={e => setBinary(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && lookup()}
        />
        <button className="aegis-launch-btn" onClick={lookup} disabled={loading || !binary.trim()}>
          {loading ? '⏳' : '▶ Chercher'}
        </button>
      </div>

      {error && <div className="osint-error-banner">{error}</div>}

      {result && (
        <div style={{ marginTop: 8 }}>
          {result.found === false ? (
            <div className="aegis-feed-empty">Aucun résultat GTFOBins pour "{binary}"</div>
          ) : (
            (result.functions || result.results || [result]).map((fn, i) => (
              <div key={i} className="privesc-finding-card" style={{ borderLeft: '3px solid var(--accent)' }}>
                <div className="privesc-finding-header">
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{fn.type || fn.function || fn.name || 'Function'}</span>
                </div>
                {(fn.description || fn.details) && (
                  <div className="privesc-desc">{fn.description || fn.details}</div>
                )}
                {(fn.code || fn.example || fn.command) && (
                  <div className="privesc-cmd-block">
                    <div className="privesc-cmd-header">
                      <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>Exemple</span>
                      <CopyBtn text={fn.code || fn.example || fn.command} />
                    </div>
                    <code className="privesc-cmd-code">{fn.code || fn.example || fn.command}</code>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function PrivEscView() {
  const [target, setTarget]   = useState('localhost')
  const [os, setOs]           = useState('linux')
  const [running, setRunning] = useState(false)
  const [findings, setFindings] = useState(null)
  const [error, setError]     = useState(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    setFindings(null)
    try {
      const endpoint = os === 'linux' ? '/privesc/linux' : '/privesc/windows'
      const res = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify({ target: target.trim() }),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setFindings(data.findings || data.results || data || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">⬆️</span>
          <div>
            <div className="aegis-title">PRIVILEGE ESCALATION</div>
            <div className="aegis-subtitle">Linux/Windows checks · GTFOBins · vecteurs d'élévation</div>
          </div>
        </div>
      </div>

      <div className="aegis-panel" style={{ marginBottom: 12 }}>
        <div className="aegis-panel-header"><span className="aegis-panel-icon">⚙️</span>Configuration</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            className="aegis-target-input"
            placeholder="Cible (IP ou localhost)"
            value={target}
            onChange={e => setTarget(e.target.value)}
            style={{ flex: 2, minWidth: 200 }}
          />
          <div className="privesc-os-selector">
            {['linux', 'windows'].map(o => (
              <button
                key={o}
                className={`privesc-os-btn ${os === o ? 'active' : ''}`}
                onClick={() => setOs(o)}
              >
                {o === 'linux' ? '🐧 Linux' : '🪟 Windows'}
              </button>
            ))}
          </div>
          <button className="aegis-launch-btn" onClick={run} disabled={running || !target.trim()}>
            {running ? '⏳ Scan…' : '▶ Lancer'}
          </button>
        </div>
        {error && <div className="osint-error-banner" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      {findings && <ResultsPanel findings={Array.isArray(findings) ? findings : []} />}

      {!findings && !running && (
        <div className="aegis-panel">
          <div className="aegis-feed-empty">
            Lance un scan pour détecter les vecteurs d'élévation de privilèges
          </div>
        </div>
      )}

      <GtfoBins />
    </div>
  )
}
