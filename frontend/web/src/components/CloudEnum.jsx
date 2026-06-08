import { useState } from 'react'
import { apiFetch } from '../utils/auth'

const TABS = ['aws', 'azure', 'gcp', 'firebase', 'dns']
const TAB_LABELS = { aws: '☁️ AWS', azure: '🔷 Azure', gcp: '🌐 GCP', firebase: '🔥 Firebase', dns: '🌍 DNS/CF' }

export default function CloudEnum() {
  const [tab, setTab] = useState('aws')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [auth, setAuth] = useState(false)

  const [aws, setAws] = useState({ access_key: '', secret_key: '', region: 'us-east-1', bucket_name: '', function_name: '', target_ip: '' })
  const [azure, setAzure] = useState({ tenant_id: '', client_id: '', client_secret: '', subscription_id: '', connection_string: '' })
  const [gcp, setGcp] = useState({ project_id: '', credentials_json: '', target_ip: '' })
  const [firebase, setFirebase] = useState({ project_id: '' })
  const [dns, setDns] = useState({ domain: '', cf_api_token: '' })

  async function call(endpoint, body) {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiFetch(`/cloud${endpoint}`, { method: 'POST', body: JSON.stringify({ ...body, authorization_confirmed: auth }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText) }
      setResult(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ padding: '1.5rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
      <h2 style={{ color: '#63b3ed', marginBottom: '1rem' }}>☁️ Cloud Enumeration</h2>

      <div style={{ background: '#1a1a2e', border: '1px solid #63b3ed', borderRadius: 8, padding: '0.75rem', marginBottom: '1rem', fontSize: 13 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
          <span style={{ color: '#63b3ed' }}>⚠️ Pentest cloud autorisé — j'ai l'autorisation explicite du propriétaire du compte</span>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: '1rem' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => { setTab(t); setResult(null); setError('') }}
            style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13,
              background: tab === t ? '#63b3ed' : '#2d3748', color: tab === t ? '#1a202c' : '#a0aec0' }}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div style={{ background: '#1e2233', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
        {tab === 'aws' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#fc8181', marginTop: 0 }}>Amazon Web Services</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {[['access_key', 'Access Key'], ['secret_key', 'Secret Key'], ['region', 'Region']].map(([k, lbl]) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>{lbl}</div>
                  <input value={aws[k]} onChange={e => setAws(a => ({ ...a, [k]: e.target.value }))}
                    style={inputStyle} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button onClick={() => call('/aws/s3/enumerate', aws)} style={btnStyle('#fc8181')}>📦 Lister buckets S3</button>
              <button onClick={() => call('/aws/iam/enumerate', aws)} style={btnStyle('#f6ad55')}>👤 IAM Users</button>
              <button onClick={() => call('/aws/lambda/enumerate', aws)} style={btnStyle('#9f7aea')}>λ Fonctions Lambda</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Bucket name" value={aws.bucket_name} onChange={e => setAws(a => ({ ...a, bucket_name: e.target.value }))}
                style={{ flex: 1, ...inputStyle2 }} />
              <button onClick={() => call('/aws/s3/objects', aws)} style={btnStyle('#38b2ac')}>🗂️ Objets bucket</button>
              <input placeholder="Function name" value={aws.function_name} onChange={e => setAws(a => ({ ...a, function_name: e.target.value }))}
                style={{ flex: 1, ...inputStyle2 }} />
              <button onClick={() => call('/aws/lambda/env-vars', { ...aws, function_name: aws.function_name })} style={btnStyle('#e53e3e')}>🔑 Env vars Lambda</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="EC2 IP (metadata)" value={aws.target_ip} onChange={e => setAws(a => ({ ...a, target_ip: e.target.value }))}
                style={{ flex: 1, ...inputStyle2 }} />
              <button onClick={() => call('/aws/metadata', { target_ip: aws.target_ip })} style={btnStyle('#dd6b20')}>🖥️ Instance metadata (SSRF)</button>
            </div>
          </div>
        )}

        {tab === 'azure' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#4299e1', marginTop: 0 }}>Microsoft Azure</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[['tenant_id', 'Tenant ID'], ['client_id', 'Client ID'], ['client_secret', 'Client Secret'], ['subscription_id', 'Subscription ID']].map(([k, lbl]) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>{lbl}</div>
                  <input value={azure[k]} onChange={e => setAzure(a => ({ ...a, [k]: e.target.value }))}
                    style={inputStyle} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/azure/resources', azure)} style={btnStyle('#4299e1')}>🔍 Ressources</button>
              <button onClick={() => call('/azure/storage', { connection_string: azure.connection_string })} style={btnStyle('#9f7aea')}>💾 Storage Containers</button>
            </div>
          </div>
        )}

        {tab === 'gcp' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Google Cloud Platform</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>Project ID</div>
                <input value={gcp.project_id} onChange={e => setGcp(g => ({ ...g, project_id: e.target.value }))} style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>VM IP (metadata)</div>
                <input value={gcp.target_ip} onChange={e => setGcp(g => ({ ...g, target_ip: e.target.value }))} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/gcp/storage', gcp)} style={btnStyle('#68d391')}>📦 GCS Buckets</button>
              <button onClick={() => call('/gcp/metadata', { target_ip: gcp.target_ip })} style={btnStyle('#dd6b20')}>🖥️ GCE Metadata</button>
            </div>
          </div>
        )}

        {tab === 'firebase' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#f6ad55', marginTop: 0 }}>Firebase</h3>
            <div>
              <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>Project ID</div>
              <input value={firebase.project_id} onChange={e => setFirebase(f => ({ ...f, project_id: e.target.value }))} style={{ ...inputStyle, width: 320 }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/firebase/database', firebase)} style={btnStyle('#e53e3e')}>🔥 Test base de données</button>
              <button onClick={() => call('/firebase/storage', firebase)} style={btnStyle('#f6ad55')}>💾 Firebase Storage</button>
            </div>
          </div>
        )}

        {tab === 'dns' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#63b3ed', marginTop: 0 }}>DNS / Cloudflare</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>Domaine</div>
                <input value={dns.domain} onChange={e => setDns(d => ({ ...d, domain: e.target.value }))} style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>Cloudflare API Token</div>
                <input value={dns.cf_api_token} onChange={e => setDns(d => ({ ...d, cf_api_token: e.target.value }))} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => call('/dns/cloudflare', dns)} style={btnStyle('#63b3ed')}>📋 Enregistrements DNS</button>
              <button onClick={() => call('/dns/subdomain-bruteforce', dns)} style={btnStyle('#9f7aea')}>🔍 Bruteforce sous-domaines</button>
            </div>
          </div>
        )}
      </div>

      {loading && <div style={{ color: '#63b3ed' }}>⏳ Énumération en cours...</div>}
      {error && <div style={{ background: '#1a1a2e', border: '1px solid #e53e3e', borderRadius: 6, padding: '0.75rem', color: '#fc8181', fontSize: 13 }}>❌ {error}</div>}
      {result && (
        <div style={{ background: '#0f0f1a', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ color: '#68d391', fontWeight: 600 }}>✅ Résultat</span>
            {result.simulation && <span style={{ background: '#2d3748', color: '#a0aec0', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>SIMULATION</span>}
          </div>
          <pre style={{ margin: 0, fontSize: 12, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 450, overflowY: 'auto' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

const inputStyle = { width: '100%', background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', boxSizing: 'border-box' }
const inputStyle2 = { background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }
function btnStyle(bg) {
  return { background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '7px 14px', cursor: 'pointer', fontSize: 13 }
}
