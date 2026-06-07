/**
 * THREAT INTEL — CVEs, CISA KEV, Exploits, IOC Lookup.
 */
import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

const SEV_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f97316',
  MEDIUM:   '#fbbf24',
  LOW:      '#4ade80',
  NONE:     '#64748b',
}

function SevBadge({ sev }) {
  const s = (sev || 'NONE').toUpperCase()
  return (
    <span style={{
      background: `${SEV_COLOR[s] || '#ffffff10'}22`,
      color:  SEV_COLOR[s] || 'var(--text2)',
      border: `1px solid ${SEV_COLOR[s] || '#ffffff30'}55`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', fontWeight: 700,
    }}>
      {s}
    </span>
  )
}

function CvesPanel({ cves, loading }) {
  if (loading) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">⚠️</span>CVEs récents</div>
      <div className="aegis-feed-empty">Chargement…</div>
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">⚠️</span>
        <span>CVEs Récents</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>{cves?.length || 0}</span>
      </div>
      <div className="aegis-feed">
        {!cves?.length ? (
          <div className="aegis-feed-empty">Aucun CVE chargé</div>
        ) : cves.slice(0, 20).map((c, i) => (
          <div key={i} className="aegis-feed-row">
            <SevBadge sev={c.severity || c.cvss_severity} />
            <span className="aegis-feed-ip" style={{ color: 'var(--accent)', fontFamily: 'monospace' }}>
              {c.id || c.cve_id}
            </span>
            <span className="aegis-feed-title" style={{ flex: 1 }}>
              {c.description || c.title || c.summary || '—'}
            </span>
            {(c.cvss || c.cvss_score) && (
              <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                CVSS {(c.cvss || c.cvss_score).toFixed(1)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function KevPanel({ kev, loading }) {
  if (loading) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">💥</span>CISA KEV</div>
      <div className="aegis-feed-empty">Chargement…</div>
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">💥</span>
        <span>CISA KEV — Exploités dans la nature</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: '#ef4444' }}>{kev?.length || 0}</span>
      </div>
      <div className="aegis-feed">
        {!kev?.length ? (
          <div className="aegis-feed-empty">Aucune entrée KEV</div>
        ) : kev.slice(0, 20).map((k, i) => (
          <div key={i} className="aegis-feed-row">
            <span style={{ color: '#ef4444', fontSize: '0.7rem', fontWeight: 700 }}>
              {k.cveID || k.cve_id || k.id}
            </span>
            <span className="aegis-feed-title" style={{ flex: 1 }}>
              {k.vulnerabilityName || k.name || k.description || '—'}
            </span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
              {k.vendor || k.vendorProject || '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ExploitsPanel({ exploits, loading }) {
  if (loading) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">🎯</span>Exploits</div>
      <div className="aegis-feed-empty">Chargement…</div>
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🎯</span>
        <span>Exploits Récents — ExploitDB</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>{exploits?.length || 0}</span>
      </div>
      <div className="aegis-feed">
        {!exploits?.length ? (
          <div className="aegis-feed-empty">Aucun exploit chargé</div>
        ) : exploits.slice(0, 20).map((e, i) => (
          <div key={i} className="aegis-feed-row">
            <span className="aegis-feed-ip" style={{ color: '#a78bfa', fontFamily: 'monospace', fontSize: '0.65rem' }}>
              EDB-{e.id || e.edb_id || '?'}
            </span>
            <span className="aegis-feed-title" style={{ flex: 1 }}>
              {e.title || e.name || e.description || '—'}
            </span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
              {e.type || e.platform || '—'}
            </span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
              {e.date ? new Date(e.date).toLocaleDateString('fr-FR') : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function IocLookupPanel() {
  const [ioc, setIoc]       = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const check = async () => {
    if (!ioc.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiFetch('/threat-intel/ioc/check', {
        method: 'POST',
        body: JSON.stringify({ ioc: ioc.trim(), value: ioc.trim() }),
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
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🔎</span>
        <span>IOC Lookup</span>
      </div>

      <div className="aegis-launch-row">
        <input
          className="aegis-target-input"
          placeholder="IP, domaine, hash MD5/SHA256, URL…"
          value={ioc}
          onChange={e => setIoc(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && check()}
        />
        <button className="aegis-launch-btn" onClick={check} disabled={loading || !ioc.trim()}>
          {loading ? '⏳' : '▶ Vérifier'}
        </button>
      </div>

      {error && <div className="osint-error-banner">{error}</div>}

      {result && (
        <div className="threat-ioc-result" style={{
          borderLeft: `3px solid ${result.malicious || result.status === 'malicious' ? '#ef4444' : '#4ade80'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: '1rem' }}>
              {result.malicious || result.status === 'malicious' ? '🚨' : '✅'}
            </span>
            <span style={{
              fontWeight: 700, fontSize: '0.85rem',
              color: result.malicious || result.status === 'malicious' ? '#ef4444' : '#4ade80',
            }}>
              {result.malicious || result.status === 'malicious' ? 'MALVEILLANT' : 'Propre'}
            </span>
            {result.confidence !== undefined && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text2)' }}>
                Confiance : {result.confidence}%
              </span>
            )}
          </div>
          {result.threat_type && (
            <div style={{ fontSize: '0.75rem', color: '#f97316', marginBottom: 4 }}>
              Type : {result.threat_type}
            </div>
          )}
          {result.sources && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text2)', marginBottom: 4 }}>
              Sources : {Array.isArray(result.sources) ? result.sources.join(', ') : result.sources}
            </div>
          )}
          {result.description && (
            <div style={{ fontSize: '0.72rem', color: 'var(--text2)', lineHeight: 1.4 }}>
              {result.description}
            </div>
          )}
          {result.tags?.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {result.tags.map(t => (
                <span key={t} style={{
                  background: '#ffffff10', border: '1px solid var(--border2)',
                  borderRadius: 4, padding: '1px 6px', fontSize: '0.62rem', color: 'var(--text2)',
                }}>
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ThreatIntelView() {
  const [cves,    setCves]    = useState(null)
  const [kev,     setKev]     = useState(null)
  const [exploits, setExploits] = useState(null)
  const [loadingCves, setLoadingCves]     = useState(true)
  const [loadingKev,  setLoadingKev]      = useState(true)
  const [loadingExp,  setLoadingExp]      = useState(true)
  const [refreshing, setRefreshing]       = useState(false)
  const [lastUpdated, setLastUpdated]     = useState(null)

  const loadAll = () => {
    setLoadingCves(true)
    apiFetch('/threat-intel/cves').then(r => r.json()).then(d => {
      setCves(d.cves || d || [])
    }).catch(() => setCves([])).finally(() => setLoadingCves(false))

    setLoadingKev(true)
    apiFetch('/threat-intel/cisa-kev').then(r => r.json()).then(d => {
      setKev(d.vulnerabilities || d.kev || d || [])
    }).catch(() => setKev([])).finally(() => setLoadingKev(false))

    setLoadingExp(true)
    apiFetch('/threat-intel/exploits').then(r => r.json()).then(d => {
      setExploits(d.exploits || d || [])
    }).catch(() => setExploits([])).finally(() => setLoadingExp(false))

    setLastUpdated(new Date())
  }

  useEffect(() => {
    loadAll()
    const t = setInterval(loadAll, 5 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  const refresh = async () => {
    setRefreshing(true)
    try {
      await apiFetch('/threat-intel/refresh', { method: 'POST' })
      setTimeout(loadAll, 1000)
    } catch {}
    setRefreshing(false)
  }

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🌐</span>
          <div>
            <div className="aegis-title">THREAT INTELLIGENCE</div>
            <div className="aegis-subtitle">CVEs · CISA KEV · ExploitDB · IOC Lookup</div>
          </div>
        </div>
        <div className="aegis-header-right">
          {lastUpdated && (
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)', marginRight: 8 }}>
              MAJ : {lastUpdated.toLocaleTimeString('fr-FR')}
            </span>
          )}
          <button className="aegis-launch-btn" onClick={refresh} disabled={refreshing} style={{ padding: '5px 14px' }}>
            {refreshing ? '⏳' : '↻ Refresh'}
          </button>
        </div>
      </div>

      <div className="osint-grid">
        <CvesPanel    cves={cves}       loading={loadingCves} />
        <KevPanel     kev={kev}         loading={loadingKev}  />
        <ExploitsPanel exploits={exploits} loading={loadingExp} />
        <IocLookupPanel />
      </div>
    </div>
  )
}
