import { useState } from 'react'
import { apiFetch } from '../utils/auth'

export default function MobileServices() {
  const [tab, setTab] = useState('android')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [auth, setAuth] = useState(false)

  const [android, setAndroid] = useState({ serial: 'emulator-5554', remote_path: '/sdcard/DCIM', command: 'id', lhost: '', lport: 4444, app_name: 'Calculator', package: 'com.banking.app', script_type: 'ssl_bypass' })
  const [ios, setIos] = useState({ device_id: '', ipa_path: '' })
  const [phishing, setPhishing] = useState({ target_app: 'Instagram', lhost: '', lport: 8080 })
  const [apk, setApk] = useState({ apk_path: '' })

  async function call(endpoint, body) {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiFetch(`/mobile${endpoint}`, { method: 'POST', body: JSON.stringify({ ...body, authorization_confirmed: auth }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText) }
      setResult(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function getDevices() {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await apiFetch(`/mobile/android/devices?authorization_confirmed=${auth}`)
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText) }
      setResult(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ padding: '1.5rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
      <h2 style={{ color: '#9f7aea', marginBottom: '1rem' }}>📱 Mobile Exploitation</h2>

      <div style={{ background: '#1a1a2e', border: '1px solid #9f7aea', borderRadius: 8, padding: '0.75rem', marginBottom: '1rem', fontSize: 13 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
          <span style={{ color: '#9f7aea' }}>⚠️ Pentest autorisé — appareil appartient à moi ou j'ai autorisation explicite</span>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: '1rem' }}>
        {[['android', '🤖 Android'], ['ios', '🍎 iOS'], ['apk', '📦 Analyse APK'], ['phishing', '🎣 Phishing Mobile']].map(([t, lbl]) => (
          <button key={t} onClick={() => { setTab(t); setResult(null); setError('') }}
            style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13,
              background: tab === t ? '#9f7aea' : '#2d3748', color: tab === t ? '#1a202c' : '#a0aec0' }}>
            {lbl}
          </button>
        ))}
      </div>

      <div style={{ background: '#1e2233', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
        {tab === 'android' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Android / ADB</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Device serial" value={android.serial} onChange={e => setAndroid(a => ({ ...a, serial: e.target.value }))}
                style={{ flex: 1, ...inp }} />
              <button onClick={getDevices} style={btn('#4299e1')}>📱 Lister devices</button>
              <button onClick={() => call('/android/enumerate', { serial: android.serial })} style={btn('#9f7aea')}>📋 Énumérer apps</button>
              <button onClick={() => call('/android/sms', { serial: android.serial })} style={btn('#e53e3e')}>💬 SMS dump</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Remote path" value={android.remote_path} onChange={e => setAndroid(a => ({ ...a, remote_path: e.target.value }))}
                style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/android/pull', { serial: android.serial, remote_path: android.remote_path })} style={btn('#38b2ac')}>⬇️ Pull fichier</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Shell command" value={android.command} onChange={e => setAndroid(a => ({ ...a, command: e.target.value }))}
                style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/android/shell', { serial: android.serial, command: android.command })} style={btn('#f6ad55')}>🖥️ Shell ADB</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="LHOST" value={android.lhost} onChange={e => setAndroid(a => ({ ...a, lhost: e.target.value }))} style={{ flex: 1, ...inp }} />
              <input placeholder="LPORT" type="number" value={android.lport} onChange={e => setAndroid(a => ({ ...a, lport: parseInt(e.target.value) }))} style={{ width: 80, ...inp }} />
              <input placeholder="App name" value={android.app_name} onChange={e => setAndroid(a => ({ ...a, app_name: e.target.value }))} style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/android/rat/generate', android)} style={btn('#e53e3e')}>🐀 Générer RAT APK</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Package (Frida)" value={android.package} onChange={e => setAndroid(a => ({ ...a, package: e.target.value }))} style={{ flex: 1, ...inp }} />
              <select value={android.script_type} onChange={e => setAndroid(a => ({ ...a, script_type: e.target.value }))}
                style={{ background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px', color: '#e2e8f0' }}>
                <option value="ssl_bypass">SSL Bypass</option>
                <option value="root_bypass">Root Bypass</option>
                <option value="biometric_bypass">Biometric Bypass</option>
                <option value="debugger_bypass">Anti-Debug Bypass</option>
              </select>
              <button onClick={() => call('/android/frida', { device_serial: android.serial, package: android.package, script_type: android.script_type })} style={btn('#805ad5')}>🔬 Frida Hook</button>
            </div>
          </div>
        )}

        {tab === 'ios' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>iOS / iDevice</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Device ID (vide = connecté en USB)" value={ios.device_id} onChange={e => setIos(i => ({ ...i, device_id: e.target.value }))}
                style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/ios/backup', { device_id: ios.device_id })} style={btn('#4299e1')}>💾 Extraction backup</button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Chemin IPA" value={ios.ipa_path} onChange={e => setIos(i => ({ ...i, ipa_path: e.target.value }))}
                style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/ios/ipa/analyze', { ipa_path: ios.ipa_path })} style={btn('#9f7aea')}>🔍 Analyser IPA</button>
            </div>
          </div>
        )}

        {tab === 'apk' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Analyse APK statique</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input placeholder="Chemin APK" value={apk.apk_path} onChange={e => setApk({ apk_path: e.target.value })}
                style={{ flex: 1, ...inp }} />
              <button onClick={() => call('/android/apk/analyze', { apk_path: apk.apk_path })} style={btn('#f6ad55')}>📦 Analyser APK</button>
            </div>
          </div>
        )}

        {tab === 'phishing' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h3 style={{ color: '#68d391', marginTop: 0 }}>Page phishing mobile</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {[['target_app', 'App ciblée'], ['lhost', 'LHOST'], ['lport', 'LPORT']].map(([k, lbl]) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: '#a0aec0', marginBottom: 3 }}>{lbl}</div>
                  <input value={phishing[k]} type={k === 'lport' ? 'number' : 'text'}
                    onChange={e => setPhishing(p => ({ ...p, [k]: k === 'lport' ? parseInt(e.target.value) : e.target.value }))}
                    style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
                </div>
              ))}
            </div>
            <button onClick={() => call('/android/phishing', phishing)} style={btn('#e53e3e')}>🎣 Créer page phishing</button>
          </div>
        )}
      </div>

      {loading && <div style={{ color: '#9f7aea' }}>⏳ Opération en cours...</div>}
      {error && <div style={{ background: '#1a1a2e', border: '1px solid #e53e3e', borderRadius: 6, padding: '0.75rem', color: '#fc8181', fontSize: 13 }}>❌ {error}</div>}
      {result && (
        <div style={{ background: '#0f0f1a', border: '1px solid #2d3748', borderRadius: 8, padding: '1rem' }}>
          <span style={{ color: '#68d391', fontWeight: 600 }}>✅ Résultat</span>
          {(result.simulation || result.simulated) && <span style={{ marginLeft: 8, background: '#2d3748', color: '#a0aec0', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>SIMULATION</span>}
          <pre style={{ margin: '0.5rem 0 0', fontSize: 12, color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 450, overflowY: 'auto' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

const inp = { background: '#2d3748', border: '1px solid #4a5568', borderRadius: 4, padding: '6px 8px', color: '#e2e8f0' }
function btn(bg) {
  return { background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '7px 14px', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap' }
}
