import { useState } from 'react'
import { apiFetch } from '../utils/auth'

const SECTIONS = ['detect', 'enumerate', 'kerberos', 'adcs', 'bloodhound', 'postexploit']
const SECTION_LABELS = {
  detect: '🎯 Détection DC',
  enumerate: '📋 Énumération',
  kerberos: '🎫 Kerberos',
  adcs: '📜 AD CS',
  bloodhound: '🩸 BloodHound',
  postexploit: '💣 Post-Exploit',
}

export default function ADServices() {
  const [section, setSection] = useState('detect')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    target_ip: '', dc_ip: '', domain: 'corp.local', username: '', password: '',
    target_user: 'krbtgt', ntlm_hash: '', krbtgt_hash: '', command: 'whoami',
    ca_name: '', authorization_confirmed: false,
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function call(endpoint, body) {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiFetch(`/ad${endpoint}`, { method: 'POST', body: JSON.stringify({ ...body, authorization_confirmed: form.authorization_confirmed }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText) }
      setResult(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const creds = { dc_ip: form.dc_ip, domain: form.domain, username: form.username, password: form.password }

  return (
    <div style={{ padding: '1.5rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
      <h2 style={{ color: '#f6ad55', marginBottom: '1rem' }}>🏢 Active Directory Attacks</h2>

      {/* Auth guard notice */}
      <div style={{ background: '#1a1a2e', border: '1px solid #f6ad55', borderRadius: 8, padding: '0.75rem', marginBottom: '1rem', fontSize: 13 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={form.authorization_confirmed} onChange={e => set('authorization_confirmed', e.target.checked)} />
          <span style={{ color: '#f6ad55' }}>⚠️ Pentest autorisé — je confirme avoir l'autorisation explicite du propriétaire de la cible</span>
        </label>
      </div>

      {/* Credentials panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8, marginBottom: '1rem' }}>
        {[['dc_ip', 'DC IP'], ['domain', 'Domaine'], ['username', 'Username'], ['password', 'Password']].map(([k, label]) => (
          <div key={k}>
            <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>{label}</div>
            <input value={form[k]} onChange={e => set(k, e.target.value)}
              type={k === 'password' ? 'password' : 'text'}
              style={{ width: '100%', background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', boxSizing: 'border-box' }} />
          </div>
        ))}
      </div>

      {/* Section tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: '1rem', flexWrap: 'wrap' }}>
        {SECTIONS.map(s => (
          <button key={s} onClick={() => setSection(s)}
            style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13,
              background: section === s ? '#f6ad55' : '#2d3748', color: section === s ? '#1a202c' : '#a0aec0' }}>
            {SECTION_LABELS[s]}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div style={{ background: '#1e2233', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
        {section === 'detect' && (
          <div>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Détection Domain Controller</h3>
            <input placeholder="Target IP" value={form.target_ip} onChange={e => set('target_ip', e.target.value)}
              style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', marginRight: 8 }} />
            <button onClick={() => call('/detect', { target_ip: form.target_ip })}
              style={{ background: '#4299e1', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', cursor: 'pointer' }}>
              Détecter
            </button>
          </div>
        )}

        {section === 'enumerate' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Énumération LDAP / SMB</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/enumerate/users', creds)} style={btnStyle('#4299e1')}>Utilisateurs LDAP</button>
              <button onClick={() => call('/enumerate/shares', { target_ip: form.dc_ip, username: form.username, password: form.password })} style={btnStyle('#9f7aea')}>Partages SMB</button>
              <button onClick={() => call('/enumerate/gpo', creds)} style={btnStyle('#38b2ac')}>GPO</button>
            </div>
          </div>
        )}

        {section === 'kerberos' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Attaques Kerberos</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button onClick={() => call('/kerberoast', creds)} style={btnStyle('#e53e3e')}>🎫 Kerberoasting</button>
              <button onClick={() => call('/asrep-roast', { target_ip: form.dc_ip })} style={btnStyle('#dd6b20')}>🔓 AS-REP Roasting</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
              <input placeholder="krbtgt hash" value={form.krbtgt_hash} onChange={e => set('krbtgt_hash', e.target.value)}
                style={{ flex: 1, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <input placeholder="Target user" value={form.target_user} onChange={e => set('target_user', e.target.value)}
                style={{ width: 140, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <button onClick={() => call('/golden-ticket', { domain: form.domain, dc_ip: form.dc_ip, krbtgt_hash: form.krbtgt_hash, target_user: form.target_user })}
                style={btnStyle('#805ad5')}>🥇 Golden Ticket</button>
            </div>
          </div>
        )}

        {section === 'adcs' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>AD Certificate Services</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button onClick={() => call('/adcs/enumerate', creds)} style={btnStyle('#4299e1')}>🔍 Énumérer templates vulnérables</button>
              <input placeholder="CA Name" value={form.ca_name} onChange={e => set('ca_name', e.target.value)}
                style={{ flex: 1, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <button onClick={() => call('/adcs/esc1-exploit', { dc_ip: form.dc_ip, domain: form.domain, ca_name: form.ca_name, target_user: form.target_user })}
                style={btnStyle('#e53e3e')}>💥 ESC1 Exploit</button>
            </div>
          </div>
        )}

        {section === 'bloodhound' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>BloodHound — Attack Paths</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/bloodhound/ingest', creds)} style={btnStyle('#e53e3e')}>📥 Ingestion données</button>
              <button onClick={() => call('/bloodhound/analyze', { zip_path: '/tmp/bloodhound.zip' })} style={btnStyle('#805ad5')}>🔍 Analyser chemins</button>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/domain/sid', {})} style={btnStyle('#38b2ac')}>🆔 Domain SID</button>
              <button onClick={() => call('/defender/check', creds)} style={btnStyle('#dd6b20')}>🛡️ Check Defender</button>
            </div>
          </div>
        )}

        {section === 'postexploit' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Post-Exploitation</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Target user (DCSync)" value={form.target_user} onChange={e => set('target_user', e.target.value)}
                style={{ width: 160, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <button onClick={() => call('/dcsync', { ...creds, target_user: form.target_user })} style={btnStyle('#e53e3e')}>⚡ DCSync</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="NTLM hash" value={form.ntlm_hash} onChange={e => set('ntlm_hash', e.target.value)}
                style={{ flex: 1, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <input placeholder="Command" value={form.command} onChange={e => set('command', e.target.value)}
                style={{ width: 120, background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }} />
              <button onClick={() => call('/pass-the-hash', { target_ip: form.dc_ip, username: form.username, domain: form.domain, ntlm_hash: form.ntlm_hash, command: form.command })}
                style={btnStyle('#805ad5')}>🔑 Pass-the-Hash</button>
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && <div style={{ color: '#f6ad55', marginBottom: 8 }}>⏳ Exécution en cours...</div>}

      {/* Error */}
      {error && <div style={{ background: '#1a1a2e', border: '1px solid #e53e3e', borderRadius: 6, padding: '0.75rem', color: '#fc8181', marginBottom: 8, fontSize: 13 }}>❌ {error}</div>}

      {/* Results */}
      {result && (
        <div style={{ background: '#0f0f1a', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ color: '#68d391', fontWeight: 600 }}>✅ Résultat</span>
            {result.simulation && <span style={{ background: '#2d3748', color: '#a0aec0', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>SIMULATION</span>}
          </div>
          <ResultView data={result} />
        </div>
      )}
    </div>
  )
}

function ResultView({ data }) {
  if (Array.isArray(data)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map((item, i) => (
          <div key={i} style={{ background: '#1e2233', borderRadius: 6, padding: '0.6rem', fontSize: 12 }}>
            <pre style={{ margin: 0, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(item, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    )
  }
  return (
    <pre style={{ margin: 0, fontSize: 12, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 400, overflowY: 'auto' }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function btnStyle(bg) {
  return { background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '7px 14px', cursor: 'pointer', fontSize: 13 }
}
