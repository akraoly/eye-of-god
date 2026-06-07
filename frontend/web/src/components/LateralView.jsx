/**
 * LATERAL MOVEMENT — SOCKS, PTH, Kerberoast, AS-REP, DCSync, BloodHound.
 */
import { useState, useRef } from 'react'
import { apiFetch } from '../utils/auth'

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button className="osint-copy-btn" onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>
      {copied ? '✓' : '⎘'}
    </button>
  )
}

function OpCard({ title, icon, endpoint, fields, description }) {
  const [values, setValues]   = useState({})
  const [running, setRunning] = useState(false)
  const [output, setOutput]   = useState(null)
  const [error, setError]     = useState(null)
  const outRef = useRef(null)

  const execute = async () => {
    setRunning(true)
    setError(null)
    setOutput(null)
    try {
      const res = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify(values),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      const data = await res.json()
      setOutput(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  const allFilled = fields.every(f => f.optional || values[f.key]?.trim())

  return (
    <div className="lateral-card">
      <div className="lateral-card-header">
        <span className="lateral-card-icon">{icon}</span>
        <div>
          <div className="lateral-card-title">{title}</div>
          {description && <div className="lateral-card-desc">{description}</div>}
        </div>
        {running && <span className="aegis-running-badge" style={{ marginLeft: 'auto' }}>RUN</span>}
      </div>

      <div className="lateral-fields">
        {fields.map(f => (
          <div key={f.key} style={{ flex: f.flex || 1, minWidth: 120 }}>
            <div style={{ fontSize: '0.62rem', color: 'var(--text3)', marginBottom: 3 }}>
              {f.label}{f.optional ? ' (opt)' : ''}
            </div>
            <input
              className="aegis-target-input"
              style={{ width: '100%' }}
              placeholder={f.placeholder || ''}
              value={values[f.key] || ''}
              onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
              type={f.type || 'text'}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
        <button
          className="aegis-launch-btn"
          onClick={execute}
          disabled={running || !allFilled}
        >
          {running ? '⏳ Exécution…' : '▶ Exécuter'}
        </button>
      </div>

      {error && <div className="osint-error-banner">{error}</div>}

      {output && (
        <div className="lateral-output" ref={outRef}>
          {typeof output === 'string' ? (
            <pre>{output}</pre>
          ) : (output.output || output.result || output.results) ? (
            <pre>{
              Array.isArray(output.output || output.result || output.results)
                ? (output.output || output.result || output.results).join('\n')
                : String(output.output || output.result || output.results)
            }</pre>
          ) : (
            <pre>{JSON.stringify(output, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  )
}

const OPS = [
  {
    title: 'SOCKS Proxy Setup',
    icon: '🔀',
    endpoint: '/lateral/socks',
    description: 'Mettre en place un tunnel SOCKS5 via la cible',
    fields: [
      { key: 'target',    label: 'Cible',       placeholder: '192.168.1.10' },
      { key: 'port',      label: 'Port SOCKS',  placeholder: '1080' },
      { key: 'username',  label: 'User',        placeholder: 'admin', optional: true },
    ],
  },
  {
    title: 'Pass-the-Hash',
    icon: '🔑',
    endpoint: '/lateral/pth',
    description: 'Authentification avec NTLM hash sans mot de passe',
    fields: [
      { key: 'target',   label: 'Cible',        placeholder: '192.168.1.10' },
      { key: 'username', label: 'Utilisateur',  placeholder: 'Administrator' },
      { key: 'hash',     label: 'NTLM Hash',    placeholder: 'aad3b435b51404eeaad3b435b51404ee:...' },
      { key: 'domain',   label: 'Domaine',      placeholder: 'CORP', optional: true },
    ],
  },
  {
    title: 'Kerberoasting',
    icon: '🎟️',
    endpoint: '/lateral/kerberoast',
    description: 'Extraction de tickets TGS pour les SPN',
    fields: [
      { key: 'domain',   label: 'Domaine',      placeholder: 'corp.local' },
      { key: 'dc',       label: 'DC IP',        placeholder: '192.168.1.1' },
      { key: 'username', label: 'Utilisateur',  placeholder: 'user@corp.local', optional: true },
      { key: 'password', label: 'Mot de passe', placeholder: '***', optional: true, type: 'password' },
    ],
  },
  {
    title: 'AS-REP Roasting',
    icon: '🍗',
    endpoint: '/lateral/asreproast',
    description: 'Enumérer les comptes sans pré-auth Kerberos',
    fields: [
      { key: 'domain',   label: 'Domaine',      placeholder: 'corp.local' },
      { key: 'dc',       label: 'DC IP',        placeholder: '192.168.1.1' },
      { key: 'userlist', label: 'Liste users',  placeholder: 'users.txt', optional: true },
    ],
  },
  {
    title: 'DCSync',
    icon: '🔄',
    endpoint: '/lateral/dcsync',
    description: 'Synchronisation DC — dump des hashes NTLM',
    fields: [
      { key: 'domain',   label: 'Domaine',      placeholder: 'corp.local' },
      { key: 'dc',       label: 'DC IP',        placeholder: '192.168.1.1' },
      { key: 'user',     label: 'User cible',   placeholder: 'krbtgt', optional: true },
    ],
  },
  {
    title: 'BloodHound Collect',
    icon: '🐕',
    endpoint: '/lateral/bloodhound',
    description: 'Collecte des données AD pour BloodHound',
    fields: [
      { key: 'domain',   label: 'Domaine',      placeholder: 'corp.local' },
      { key: 'dc',       label: 'DC IP',        placeholder: '192.168.1.1' },
      { key: 'username', label: 'Utilisateur',  placeholder: 'user@corp.local', optional: true },
      { key: 'password', label: 'Mot de passe', placeholder: '***', optional: true, type: 'password' },
    ],
  },
]

export default function LateralView() {
  const [history, setHistory] = useState([])

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">↔️</span>
          <div>
            <div className="aegis-title">LATERAL MOVEMENT</div>
            <div className="aegis-subtitle">SOCKS · PTH · Kerberoast · AS-REP · DCSync · BloodHound</div>
          </div>
        </div>
      </div>

      <div className="lateral-grid">
        {OPS.map(op => (
          <OpCard key={op.title} {...op} />
        ))}
      </div>

      {history.length > 0 && (
        <div className="aegis-panel" style={{ marginTop: 16 }}>
          <div className="aegis-panel-header"><span className="aegis-panel-icon">📜</span>Historique</div>
          <div className="creds-vault-table">
            <div className="creds-vault-header" style={{ gridTemplateColumns: '1fr 1fr 80px 100px' }}>
              <span>Opération</span><span>Cible</span><span>Statut</span><span>Date</span>
            </div>
            {history.map((h, i) => (
              <div key={i} className="creds-vault-row" style={{ gridTemplateColumns: '1fr 1fr 80px 100px' }}>
                <span>{h.operation}</span>
                <span>{h.target}</span>
                <span style={{ color: h.success ? '#4ade80' : '#ef4444' }}>{h.success ? 'OK' : 'KO'}</span>
                <span className="creds-date">{h.timestamp ? new Date(h.timestamp).toLocaleTimeString('fr-FR') : '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
