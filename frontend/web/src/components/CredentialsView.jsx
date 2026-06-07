/**
 * CREDENTIALS — Hash cracking, vault, KerBrute, CME.
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

function ProgressBar({ value, color = 'var(--accent)' }) {
  return (
    <div className="creds-progress-track">
      <div className="creds-progress-fill" style={{ width: `${Math.min(100, value)}%`, background: color }} />
    </div>
  )
}

function HashCrackSection() {
  const [hash, setHash]       = useState('')
  const [hashType, setHashType] = useState('')
  const [cracking, setCracking] = useState(false)
  const [progress, setProgress] = useState(0)
  const [speed, setSpeed]     = useState(null)
  const [eta, setEta]         = useState(null)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)
  const pollRef = useRef(null)
  const jobRef  = useRef(null)

  const identify = async (h) => {
    if (!h.trim()) return
    try {
      const res = await apiFetch('/credentials/identify', {
        method: 'POST',
        body: JSON.stringify({ hash: h.trim() }),
      })
      if (res.ok) {
        const d = await res.json()
        setHashType(d.type || d.hash_type || '')
      }
    } catch {}
  }

  const crack = async () => {
    if (!hash.trim()) return
    setCracking(true)
    setError(null)
    setResult(null)
    setProgress(0)
    setSpeed(null)
    setEta(null)
    try {
      const res = await apiFetch('/credentials/crack', {
        method: 'POST',
        body: JSON.stringify({ hash: hash.trim(), hash_type: hashType }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Erreur lors du cracking')
      }
      const data = await res.json()
      if (data.job_id) {
        jobRef.current = data.job_id
        pollRef.current = setInterval(async () => {
          try {
            const r = await apiFetch(`/credentials/crack/${data.job_id}`)
            const s = await r.json()
            setProgress(s.progress || 0)
            setSpeed(s.speed)
            setEta(s.eta)
            if (s.status === 'done') {
              setResult(s)
              setCracking(false)
              clearInterval(pollRef.current)
            }
            if (s.status === 'failed') {
              setError('Hash non cracké — wordlist épuisée')
              setCracking(false)
              clearInterval(pollRef.current)
            }
          } catch {}
        }, 1000)
      } else {
        setResult(data)
        setCracking(false)
      }
    } catch (err) {
      setError(err.message)
      setCracking(false)
    }
  }

  useEffect(() => () => clearInterval(pollRef.current), [])

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🔓</span>
        <span>Hash Cracking</span>
        {cracking && <span className="aegis-running-badge">CRACKING</span>}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <input
          className="aegis-target-input"
          placeholder="Hash à cracker…"
          value={hash}
          onChange={e => { setHash(e.target.value); setHashType('') }}
          onBlur={e => identify(e.target.value)}
          style={{ flex: 2 }}
        />
        <input
          className="aegis-target-input"
          placeholder="Type (auto-detect)"
          value={hashType}
          onChange={e => setHashType(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="aegis-launch-btn" onClick={crack} disabled={cracking || !hash.trim()}>
          {cracking ? '⏳' : '▶ Crack'}
        </button>
      </div>

      {hashType && (
        <div style={{ fontSize: '0.7rem', color: 'var(--accent)', marginBottom: 8 }}>
          Type détecté : <strong>{hashType}</strong>
        </div>
      )}

      {cracking && (
        <div className="creds-crack-status">
          <ProgressBar value={progress} />
          <div className="creds-crack-stats">
            <span>{progress.toFixed(1)}%</span>
            {speed && <span>{speed} H/s</span>}
            {eta && <span>ETA : {eta}</span>}
          </div>
        </div>
      )}

      {result && (
        <div className="creds-result-box" style={{ borderColor: result.cracked ? '#4ade80' : '#f97316' }}>
          {result.cracked
            ? <><span style={{ color: '#4ade80' }}>Cracké !</span> <code className="creds-plaintext">{result.plaintext}</code></>
            : <span style={{ color: '#f97316' }}>Non trouvé dans la wordlist</span>
          }
        </div>
      )}

      {error && <div className="osint-error-banner">{error}</div>}
    </div>
  )
}

function VaultSection() {
  const [creds, setCreds] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    apiFetch('/credentials/').then(r => r.json()).then(d => {
      setCreds(d.credentials || d || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">🗝️</span>Vault</div>
      <div className="aegis-feed-empty">Chargement…</div>
    </div>
  )

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🗝️</span>
        <span>Credential Vault</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>{creds.length} entrées</span>
      </div>

      {creds.length === 0 ? (
        <div className="aegis-feed-empty">Vault vide — aucun credential stocké</div>
      ) : (
        <div className="creds-vault-table">
          <div className="creds-vault-header">
            <span>Utilisateur</span><span>Cible</span><span>Type</span><span>Hash/Pass</span><span>Date</span>
          </div>
          {creds.map((c, i) => (
            <div key={i} className="creds-vault-row">
              <span className="creds-user">{c.username || c.user || '—'}</span>
              <span className="creds-host">{c.target || c.host || '—'}</span>
              <span className="creds-type">{c.type || c.cred_type || '—'}</span>
              <span className="creds-hash">
                {c.hash || c.password_hash || c.value
                  ? <code>{(c.hash || c.password_hash || c.value || '').slice(0, 24)}…</code>
                  : '—'
                }
              </span>
              <span className="creds-date">{c.created_at ? new Date(c.created_at).toLocaleDateString('fr-FR') : '—'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function KerBruteSection() {
  const [domain, setDomain]   = useState('')
  const [dc, setDc]           = useState('')
  const [file, setFile]       = useState(null)
  const [running, setRunning] = useState(false)
  const [output, setOutput]   = useState([])
  const [error, setError]     = useState(null)
  const outRef = useRef(null)

  useEffect(() => {
    if (outRef.current) outRef.current.scrollTop = outRef.current.scrollHeight
  }, [output])

  const run = async () => {
    if (!domain || !dc) return
    setRunning(true)
    setError(null)
    setOutput([`[${new Date().toLocaleTimeString()}] KerBrute lancé sur ${dc}…`])
    try {
      const fd = new FormData()
      fd.append('domain', domain)
      fd.append('dc', dc)
      if (file) fd.append('userlist', file)
      const token = localStorage.getItem('eye_token')
      const res = await fetch('/api/credentials/kerbrute', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      const lines = data.output || data.results || []
      setOutput(Array.isArray(lines) ? lines.map(l => typeof l === 'string' ? l : JSON.stringify(l)) : [JSON.stringify(data)])
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🎟️</span>
        <span>KerBrute — Username Enumeration</span>
      </div>

      <div className="creds-form-grid">
        <input className="aegis-target-input" placeholder="Domaine (ex: corp.local)" value={domain} onChange={e => setDomain(e.target.value)} />
        <input className="aegis-target-input" placeholder="DC IP (ex: 192.168.1.1)" value={dc} onChange={e => setDc(e.target.value)} />
      </div>
      <div className="creds-file-row">
        <label className="creds-file-label">
          <input type="file" accept=".txt" onChange={e => setFile(e.target.files[0])} style={{ display: 'none' }} />
          {file ? file.name : 'Choisir liste usernames (.txt)'}
        </label>
        <button className="aegis-launch-btn" onClick={run} disabled={running || !domain || !dc}>
          {running ? '⏳ En cours…' : '▶ Lancer'}
        </button>
      </div>

      {error && <div className="osint-error-banner">{error}</div>}

      {output.length > 0 && (
        <div className="aegis-log" ref={outRef}>
          {output.map((l, i) => <div key={i} className="aegis-log-line">{l}</div>)}
        </div>
      )}
    </div>
  )
}

function CmeSection() {
  const [target, setTarget]   = useState('')
  const [user, setUser]       = useState('')
  const [pass, setPass]       = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)

  const run = async () => {
    if (!target || !user) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiFetch('/credentials/cme', {
        method: 'POST',
        body: JSON.stringify({ target, username: user, password: pass }),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">🕹️</span>
        <span>CME — CrackMapExec Validation</span>
      </div>

      <div className="creds-form-grid">
        <input className="aegis-target-input" placeholder="Cible (IP/CIDR)" value={target} onChange={e => setTarget(e.target.value)} />
        <input className="aegis-target-input" placeholder="Utilisateur" value={user} onChange={e => setUser(e.target.value)} />
        <input className="aegis-target-input" placeholder="Mot de passe ou hash" value={pass} onChange={e => setPass(e.target.value)} type="password" />
        <button className="aegis-launch-btn" onClick={run} disabled={running || !target || !user}>
          {running ? '⏳' : '▶ Valider'}
        </button>
      </div>

      {error && <div className="osint-error-banner">{error}</div>}

      {result && (
        <div className="creds-result-box" style={{ borderColor: result.success ? '#4ade80' : '#ef4444' }}>
          <pre style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function CredentialsView() {
  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🔑</span>
          <div>
            <div className="aegis-title">CREDENTIALS</div>
            <div className="aegis-subtitle">Hash Cracking · Vault · KerBrute · CME</div>
          </div>
        </div>
      </div>

      <div className="osint-grid">
        <HashCrackSection />
        <VaultSection />
        <KerBruteSection />
        <CmeSection />
      </div>
    </div>
  )
}
