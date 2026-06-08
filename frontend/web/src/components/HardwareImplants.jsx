import { useState } from 'react'
import { apiFetch } from '../utils/auth'

const IMPLANTS = [
  { id: 'ducky', label: '🦆 Rubber Ducky', color: '#f6ad55' },
  { id: 'bunny', label: '🐰 Bash Bunny', color: '#68d391' },
  { id: 'omg', label: '🔌 O.MG Cable', color: '#fc8181' },
  { id: 'poisontap', label: '💉 PoisonTap', color: '#9f7aea' },
  { id: 'lan_turtle', label: '🐢 Lan Turtle', color: '#38b2ac' },
  { id: 'badusb', label: '💾 BadUSB', color: '#e53e3e' },
]

export default function HardwareImplants() {
  const [implant, setImplant] = useState('ducky')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [auth, setAuth] = useState(false)
  const [payloads, setPayloads] = useState(null)

  const [form, setForm] = useState({
    lhost: '', lport: 4444, target: 'target',
    os_target: 'windows', payload_type: 'credentials_exfil',
    attack_mode: 'HID_STORAGE',
    modules: ['autossh', 'responder'],
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function call(endpoint, body) {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiFetch(`/hardware${endpoint}`, { method: 'POST', body: JSON.stringify({ ...body, authorization_confirmed: auth }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText) }
      setResult(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function loadPayloads() {
    const r = await apiFetch('/hardware/payloads/list')
    if (r.ok) setPayloads(await r.json())
  }

  const base = { lhost: form.lhost, lport: form.lport, target: form.target }

  return (
    <div style={{ padding: '1.5rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
      <h2 style={{ color: '#f6ad55', marginBottom: '1rem' }}>🔌 Hardware Implants</h2>

      <div style={{ background: '#1a1a2e', border: '1px solid #f6ad55', borderRadius: 8, padding: '0.75rem', marginBottom: '1rem', fontSize: 13 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
          <span style={{ color: '#f6ad55' }}>⚠️ Red team autorisé — déploiement hardware explicitement autorisé dans le périmètre défini</span>
        </label>
      </div>

      {/* Implant selector */}
      <div style={{ display: 'flex', gap: 6, marginBottom: '1rem', flexWrap: 'wrap' }}>
        {IMPLANTS.map(imp => (
          <button key={imp.id} onClick={() => { setImplant(imp.id); setResult(null); setError('') }}
            style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13,
              background: implant === imp.id ? imp.color : '#2d3748', color: implant === imp.id ? '#1a202c' : '#a0aec0' }}>
            {imp.label}
          </button>
        ))}
        <button onClick={loadPayloads}
          style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #4a5568', cursor: 'pointer', fontSize: 13, background: 'transparent', color: '#a0aec0', marginLeft: 'auto' }}>
          📂 Mes payloads
        </button>
      </div>

      {/* Common fields */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: '1rem' }}>
        {[['lhost', 'LHOST (callback)'], ['lport', 'LPORT'], ['target', 'Target name']].map(([k, lbl]) => (
          <div key={k}>
            <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>{lbl}</div>
            <input value={form[k]} type={k === 'lport' ? 'number' : 'text'}
              onChange={e => set(k, k === 'lport' ? parseInt(e.target.value) : e.target.value)}
              style={{ width: '100%', background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', boxSizing: 'border-box' }} />
          </div>
        ))}
      </div>

      {/* Implant-specific */}
      <div style={{ background: '#1e2233', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
        {implant === 'ducky' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#f6ad55', marginTop: 0 }}>Rubber Ducky / Hak5</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select value={form.payload_type} onChange={e => set('payload_type', e.target.value)}
                style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', flex: 1 }}>
                <option value="credentials_exfil">Exfiltration credentials</option>
                <option value="reverse_shell">Reverse shell PowerShell</option>
                <option value="persistence">Persistence (registre)</option>
                <option value="wifi_passwords">Vol mots de passe WiFi</option>
              </select>
              <select value={form.os_target} onChange={e => set('os_target', e.target.value)}
                style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }}>
                <option value="windows">Windows</option>
                <option value="macos">macOS</option>
                <option value="linux">Linux</option>
              </select>
              <button onClick={() => call('/rubber-ducky/generate', { ...base, payload_type: form.payload_type, os_target: form.os_target })}
                style={btnStyle('#f6ad55')}>⚡ Générer payload</button>
            </div>
          </div>
        )}

        {implant === 'bunny' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <h3 style={{ color: '#68d391', marginTop: 0, marginRight: 16 }}>Bash Bunny</h3>
            <select value={form.attack_mode} onChange={e => set('attack_mode', e.target.value)}
              style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0', flex: 1 }}>
              <option value="HID_STORAGE">HID + Storage</option>
              <option value="HID_ETHERNET">HID + Ethernet</option>
              <option value="ETHERNET">Ethernet only</option>
            </select>
            <button onClick={() => call('/bash-bunny/generate', { ...base, attack_mode: form.attack_mode })}
              style={btnStyle('#68d391')}>⚡ Générer payload</button>
          </div>
        )}

        {implant === 'omg' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <h3 style={{ color: '#fc8181', marginTop: 0, marginRight: 16 }}>O.MG Cable</h3>
            <button onClick={() => call('/omg-cable/generate', base)} style={btnStyle('#fc8181')}>⚡ Générer payload</button>
          </div>
        )}

        {implant === 'poisontap' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <h3 style={{ color: '#9f7aea', marginTop: 0, marginRight: 16 }}>PoisonTap (Raspberry Pi Zero)</h3>
            <button onClick={() => call('/poisontap/generate', base)} style={btnStyle('#9f7aea')}>⚡ Générer payload + serveur</button>
          </div>
        )}

        {implant === 'lan_turtle' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h3 style={{ color: '#38b2ac', marginTop: 0 }}>Lan Turtle</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {['autossh', 'responder', 'nmap', 'meterpreter'].map(m => (
                <label key={m} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 13 }}>
                  <input type="checkbox"
                    checked={form.modules.includes(m)}
                    onChange={e => set('modules', e.target.checked ? [...form.modules, m] : form.modules.filter(x => x !== m))} />
                  {m}
                </label>
              ))}
            </div>
            <button onClick={() => call('/lan-turtle/configure', { ...base, modules: form.modules })} style={btnStyle('#38b2ac')}>⚙️ Configurer</button>
          </div>
        )}

        {implant === 'badusb' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <h3 style={{ color: '#e53e3e', marginTop: 0, marginRight: 16 }}>BadUSB générique</h3>
            <select value={form.os_target} onChange={e => set('os_target', e.target.value)}
              style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }}>
              <option value="windows">Windows</option>
              <option value="linux">Linux</option>
              <option value="macos">macOS</option>
            </select>
            <button onClick={() => call('/badusb/generate', { ...base, target_os: form.os_target })} style={btnStyle('#e53e3e')}>⚡ Générer script</button>
          </div>
        )}
      </div>

      {loading && <div style={{ color: '#f6ad55' }}>⏳ Génération en cours...</div>}
      {error && <div style={{ background: '#1a1a2e', border: '1px solid #e53e3e', borderRadius: 6, padding: '0.75rem', color: '#fc8181', fontSize: 13 }}>❌ {error}</div>}

      {result && (
        <div style={{ background: '#0f0f1a', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
          <span style={{ color: '#68d391', fontWeight: 600 }}>✅ Payload généré</span>
          {result.simulation && <span style={{ marginLeft: 8, background: '#2d3748', color: '#a0aec0', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>SIMULATION</span>}
          <pre style={{ margin: '0.5rem 0 0', fontSize: 12, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 400, overflowY: 'auto' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      {payloads && (
        <div style={{ background: '#1e2233', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem' }}>
          <h3 style={{ color: '#a0aec0', marginTop: 0 }}>📂 Payloads générés ({payloads.count})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {payloads.payloads.map((p, i) => (
              <div key={i} style={{ background: '#2d3748', borderRadius: 6, padding: '0.5rem 0.75rem', fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#e2e8f0' }}>{p.name}</span>
                <span style={{ color: '#a0aec0' }}>{p.file_count} fichiers</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function btnStyle(bg) {
  return { background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '7px 14px', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap' }
}
