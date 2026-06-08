import { useState } from 'react'

const BASE = 'http://localhost:8001'

function useApi() {
  const token = localStorage.getItem('token') || ''
  const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
  return {
    get:  (p)    => fetch(`${BASE}${p}`, { headers: h }).then(r => r.json()),
    post: (p, b) => fetch(`${BASE}${p}`, { method:'POST', headers: h, body: JSON.stringify(b) }).then(r => r.json()),
    del:  (p)    => fetch(`${BASE}${p}`, { method:'DELETE', headers: h }).then(r => r.json()),
  }
}

const btn = (c='#003300', tc='#00ff41') => ({
  background: c, color: tc, border: `1px solid ${tc}`, borderRadius: 4,
  padding: '5px 12px', cursor: 'pointer', fontSize: 12, margin: '3px'
})
const inp = { background: '#050505', color: '#00ff41', border: '1px solid #1a3a1a',
  borderRadius: 4, padding: '4px 8px', fontSize: 12, width: '100%', marginBottom: 6 }

function Result({ data }) {
  if (!data) return null
  return <pre style={{ background:'#0a0a0a', border:'1px solid #1a3a1a', borderRadius:6,
    padding:12, fontSize:11, color:'#00ff41', maxHeight:360, overflow:'auto',
    whiteSpace:'pre-wrap', wordBreak:'break-word', marginTop:8 }}>{JSON.stringify(data, null, 2)}</pre>
}

function Warn({ msg = 'Usage légal uniquement — pentest contractuel / red team autorisé' }) {
  return <div style={{ background:'#1a0a00', border:'1px solid #ff6600', borderRadius:5,
    padding:'6px 12px', marginBottom:10, fontSize:12, color:'#ff9944' }}>⚠️ {msg}</div>
}

// ── Jamming Panel ────────────────────────────────────────────────────────────
function JammingPanel() {
  const { get, post, del } = useApi()
  const [res, setRes] = useState(null)
  const [freq, setFreq] = useState(433000000)
  const [power, setPower] = useState(30)
  const [band, setBand] = useState('2.4ghz_wifi')
  const [auth, setAuth] = useState(false)

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/ew/jamming/bands').then(setRes)}>List Bands</button>
        <button style={btn()} onClick={() => get('/ew/jamming/scan').then(setRes)}>Scan Spectrum</button>
        <button style={btn()} onClick={() => get('/ew/jamming').then(setRes)}>Active Jams</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => del('/ew/jamming').then(setRes)}>Stop All</button>
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:10 }}>
        <div>
          <div style={{ color:'#888', fontSize:11, marginBottom:4 }}>Frequency (Hz)</div>
          <input style={inp} type="number" value={freq} onChange={e => setFreq(Number(e.target.value))} />
          <div style={{ color:'#888', fontSize:11, marginBottom:4 }}>Power (dBm)</div>
          <input style={inp} type="number" value={power} onChange={e => setPower(Number(e.target.value))} />
          <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:6 }} />
            authorization_confirmed
          </label>
          <br />
          <button style={btn('#1a0000','#ff4444')} onClick={() =>
            post('/ew/jamming/frequency', { frequency_hz: freq, power_dbm: power, authorization_confirmed: auth }).then(setRes)
          }>Jam Frequency</button>
        </div>
        <div>
          <div style={{ color:'#888', fontSize:11, marginBottom:4 }}>Band</div>
          <input style={inp} value={band} onChange={e => setBand(e.target.value)} placeholder="2.4ghz_wifi, gps_l1, gsm900..." />
          <button style={btn('#1a0000','#ff4444')} onClick={() =>
            post('/ew/jamming/band', { band_name: band, power_dbm: power, authorization_confirmed: auth }).then(setRes)
          }>Jam Band</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Drone Panel ──────────────────────────────────────────────────────────────
function DronePanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [cid, setCid] = useState('')
  const [auth, setAuth] = useState(false)
  const [lat, setLat]   = useState(48.85)
  const [lon, setLon]   = useState(2.35)

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get(`/ew/drone/detect?observer_lat=${lat}&observer_lon=${lon}&radius_m=2000`).then(d => { setRes(d); if(d?.contacts?.[0]) setCid(d.contacts[0].contact_id) })}>Detect Drones</button>
        <button style={btn()} onClick={() => get('/ew/drone/contacts').then(setRes)}>All Contacts</button>
        {cid && <button style={btn()} onClick={() => get(`/ew/drone/${cid}/classify`).then(setRes)}>Classify</button>}
        {cid && <button style={btn()} onClick={() => get(`/ew/drone/${cid}/track`).then(setRes)}>Track</button>}
        {cid && <button style={btn()} onClick={() => get(`/ew/drone/${cid}/locate`).then(setRes)}>Locate</button>}
      </div>
      <div style={{ marginTop:8 }}>
        <input style={{...inp, width:'auto', marginRight:8}} placeholder="Contact ID" value={cid} onChange={e => setCid(e.target.value)} />
        <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer' }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
          auth_confirmed
        </label>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop:6 }}>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/drone/jam-control', { contact_id: cid, authorization_confirmed: auth }).then(setRes)}>Jam Control</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/drone/jam-video',   { contact_id: cid, authorization_confirmed: auth }).then(setRes)}>Jam Video</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/drone/hijack-dji',  { contact_id: cid, authorization_confirmed: auth }).then(setRes)}>Hijack DJI</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/drone/forced-landing', { contact_id: cid, authorization_confirmed: auth }).then(setRes)}>Forced Landing</button>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── WiFi/BT Panel ─────────────────────────────────────────────────────────────
function WiFiBtPanel() {
  const { get, post } = useApi()
  const [res, setRes]  = useState(null)
  const [bssid, setBssid] = useState('AA:BB:CC:DD:EE:FF')
  const [auth, setAuth] = useState(false)

  return (
    <div>
      <Warn />
      <div style={{ color:'#aaffaa', fontSize:12, marginBottom:8 }}>WiFi Attacks</div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/ew/wifi/scan').then(setRes)}>Scan APs</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/wifi/deauth', { bssid, client_mac: 'FF:FF:FF:FF:FF:FF', count: 100, authorization_confirmed: auth }).then(setRes)
        }>Deauth</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/wifi/beacon-flood', null).then(setRes)
        }>Beacon Flood</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/wifi/pmkid', null).then(setRes)
        }>PMKID Capture</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/wifi/jam', { channel: 6, authorization_confirmed: auth }).then(setRes)
        }>WiFi Jam</button>
      </div>
      <div style={{ color:'#aaffaa', fontSize:12, margin:'10px 0 6px' }}>Bluetooth Attacks</div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/ew/bluetooth/scan').then(setRes)}>BT Scan</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/bluetooth/ble-jam', { authorization_confirmed: auth }).then(setRes)
        }>BLE Jam</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() =>
          post('/ew/bluetooth/classic-jam', { authorization_confirmed: auth }).then(setRes)
        }>Classic Jam</button>
      </div>
      <div style={{ marginTop:8 }}>
        <input style={{...inp, width:200}} value={bssid} onChange={e => setBssid(e.target.value)} placeholder="Target BSSID" />
        <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer', marginLeft:8 }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
          auth_confirmed
        </label>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Radar Panel ───────────────────────────────────────────────────────────────
function RadarPanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [rid, setRid] = useState('')

  return (
    <div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/ew/radar/scan').then(d => { setRes(d); if(d?.detected?.[0]) setRid(d.detected[0].radar_id) })}>Scan Radar</button>
        <button style={btn()} onClick={() => get('/ew/radar/contacts').then(setRes)}>Contacts</button>
        <button style={btn()} onClick={() => get('/ew/radar/types').then(setRes)}>Radar Types</button>
        <button style={btn()} onClick={() => get('/ew/radar/jamming-techniques').then(setRes)}>Jam Techniques</button>
        <button style={btn()} onClick={() => get('/ew/radar/threat-assessment').then(setRes)}>Threat Assessment</button>
      </div>
      {rid && (
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop:6 }}>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/radar/noise-jam', { radar_id: rid, waveform: 'noise_spot' }).then(setRes)}>Noise Jam</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/radar/deception-jam', { radar_id: rid }).then(setRes)}>Deception Jam</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/radar/false-targets', { radar_id: rid, num_targets: 10 }).then(setRes)}>False Targets</button>
        </div>
      )}
      <div style={{ marginTop:6 }}>
        <input style={{...inp, width:200}} value={rid} onChange={e => setRid(e.target.value)} placeholder="Radar ID" />
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Cellular Panel ────────────────────────────────────────────────────────────
function CellularPanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [msisdn, setMsisdn] = useState('+33612345678')
  const [imsi, setImsi]     = useState('208010000000001')
  const [auth, setAuth]     = useState(false)

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/ew/cellular/bts-scan').then(setRes)}>BTS Scan</button>
        <button style={btn()} onClick={() => post('/ew/cellular/imsi-catch', { band: 'gsm900', capture_mode: 'passive' }).then(setRes)}>IMSI Catch</button>
        <button style={btn()} onClick={() => get('/ew/cellular/captures').then(setRes)}>Captures</button>
      </div>
      <div style={{ marginTop:8, display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
        <div>
          <div style={{ color:'#888', fontSize:11, marginBottom:3 }}>MSISDN / IMSI Target</div>
          <input style={inp} value={msisdn} onChange={e => setMsisdn(e.target.value)} placeholder="MSISDN" />
          <input style={inp} value={imsi}   onChange={e => setImsi(e.target.value)}   placeholder="IMSI" />
          <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
            auth_confirmed
          </label>
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:4, justifyContent:'center' }}>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/cellular/ss7', { msisdn, attack_type: 'location_query', authorization_confirmed: auth }).then(setRes)}>SS7 Location</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/cellular/ss7', { msisdn, attack_type: 'sms_intercept', authorization_confirmed: auth }).then(setRes)}>SS7 SMS Intercept</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/cellular/diameter', { imsi, attack_type: 'location_query', authorization_confirmed: auth }).then(setRes)}>Diameter Attack</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/cellular/bts-spoof', { mcc:'208', mnc:'01', cell_id:12345, band:'gsm900', authorization_confirmed: auth }).then(setRes)}>BTS Spoof</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/ew/cellular/downgrade', null).then(setRes)}>Downgrade Attack</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Main View ─────────────────────────────────────────────────────────────────
const TABS = [
  { id:'jam',    label:'RF Jamming' },
  { id:'drone',  label:'Drone Defense' },
  { id:'wifi',   label:'WiFi / BT' },
  { id:'radar',  label:'Radar EW' },
  { id:'cell',   label:'Cellular / SS7' },
]

export default function ElectronicWarfareView() {
  const [tab, setTab] = useState('jam')

  return (
    <div style={{ padding:20, color:'#00ff41', fontFamily:'monospace', maxWidth:900 }}>
      <div style={{ fontSize:18, fontWeight:'bold', marginBottom:4, color:'#44ff88' }}>
        ⚡ Guerre Électronique — Bloc 11
      </div>
      <div style={{ color:'#888', fontSize:12, marginBottom:14 }}>
        RF Jamming · Drone Defense · WiFi/BT Attacks · Radar EW · Cellular/SS7
      </div>

      <div style={{ display:'flex', gap:6, marginBottom:16, borderBottom:'1px solid #1a3a1a', paddingBottom:8 }}>
        {TABS.map(t => (
          <button key={t.id} style={{ ...btn(tab === t.id ? '#003300' : '#050505', tab === t.id ? '#00ff41' : '#448844'),
            borderColor: tab === t.id ? '#00ff41' : '#1a3a1a' }}
            onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      {tab === 'jam'   && <JammingPanel />}
      {tab === 'drone' && <DronePanel />}
      {tab === 'wifi'  && <WiFiBtPanel />}
      {tab === 'radar' && <RadarPanel />}
      {tab === 'cell'  && <CellularPanel />}
    </div>
  )
}
