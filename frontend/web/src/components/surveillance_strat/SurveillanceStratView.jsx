import { useState } from 'react'

const BASE = ''

function useApi() {
  const token = localStorage.getItem('eye_token') || ''
  const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
  return {
    get:  (p)    => fetch(`${BASE}${p}`, { headers: h }).then(r => r.json()),
    post: (p, b) => fetch(`${BASE}${p}`, { method:'POST', headers: h, body: JSON.stringify(b) }).then(r => r.json()),
  }
}

const btn = (c='#003300', tc='#00ff41') => ({
  background: c, color: tc, border: `1px solid ${tc}`, borderRadius: 4,
  padding: '5px 12px', cursor: 'pointer', fontSize: 12, margin: 3
})
const inp = { background: '#050505', color: '#00ff41', border: '1px solid #1a3a1a',
  borderRadius: 4, padding: '4px 8px', fontSize: 12, width: '100%', marginBottom: 6 }

function Result({ data }) {
  if (!data) return null
  return <pre style={{ background:'#0a0a0a', border:'1px solid #1a3a1a', borderRadius:6,
    padding:12, fontSize:11, color:'#00ff41', maxHeight:380, overflow:'auto',
    whiteSpace:'pre-wrap', wordBreak:'break-word', marginTop:8 }}>{JSON.stringify(data, null, 2)}</pre>
}

// ── Air Surveillance ──────────────────────────────────────────────────────────
function AirPanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [icao, setIcao] = useState('')
  const [fid, setFid]   = useState('')

  return (
    <div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => post('/surveillance/air/start', null).then(d => { setRes(d) })}>Start ADS-B</button>
        <button style={btn()} onClick={() => get('/surveillance/air/contacts').then(setRes)}>All Contacts</button>
        <button style={btn('#002200','#44ff88')} onClick={() => get('/surveillance/air/military').then(setRes)}>Military Contacts</button>
        <button style={btn('#002200','#44ff88')} onClick={() => get('/surveillance/air/military-detect').then(setRes)}>Military Detection</button>
        <button style={btn()} onClick={() => get('/surveillance/air/acars').then(setRes)}>ACARS Decode</button>
        <button style={btn()} onClick={() => post('/surveillance/air/stop', null).then(setRes)}>Stop Receiver</button>
      </div>
      <div style={{ marginTop:8, display:'flex', gap:8, alignItems:'center' }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>ICAO24</div>
          <input style={{...inp, width:120}} value={icao} onChange={e => setIcao(e.target.value)} placeholder="3C4B2E" />
        </div>
        <button style={btn()} onClick={() => icao && get(`/surveillance/air/aircraft/${icao}`).then(setRes)}>Aircraft Detail</button>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>Flight ID</div>
          <input style={{...inp, width:120}} value={fid} onChange={e => setFid(e.target.value)} placeholder="AFR1234" />
        </div>
        <button style={btn()} onClick={() => fid && post('/surveillance/air/predict', { flight_id: fid, time_horizon_minutes: 30 }).then(setRes)}>Predict</button>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Maritime AIS ──────────────────────────────────────────────────────────────
function MaritimePanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [mmsi, setMmsi] = useState('')

  return (
    <div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => post('/surveillance/maritime/start', null).then(d => { setRes(d) })}>Start AIS</button>
        <button style={btn()} onClick={() => get('/surveillance/maritime/vessels').then(setRes)}>All Vessels</button>
        <button style={btn('#002200','#44ff88')} onClick={() => get('/surveillance/maritime/military').then(setRes)}>Military</button>
        <button style={btn('#220000','#ff8844')} onClick={() => get('/surveillance/maritime/suspicious').then(setRes)}>Suspicious</button>
        <button style={btn()} onClick={() => get('/surveillance/maritime/eez').then(setRes)}>EEZ Monitor</button>
        <button style={btn()} onClick={() => post('/surveillance/maritime/stop', null).then(setRes)}>Stop AIS</button>
      </div>
      <div style={{ marginTop:8, display:'flex', gap:8, alignItems:'center' }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>MMSI</div>
          <input style={{...inp, width:140}} value={mmsi} onChange={e => setMmsi(e.target.value)} placeholder="226000000" />
        </div>
        <button style={btn()} onClick={() => mmsi && get(`/surveillance/maritime/vessel/${mmsi}`).then(setRes)}>Detail</button>
        <button style={btn()} onClick={() => mmsi && get(`/surveillance/maritime/anomaly/${mmsi}`).then(setRes)}>Anomaly</button>
        <button style={btn()} onClick={() => mmsi && get(`/surveillance/maritime/predict/${mmsi}?hours=12`).then(setRes)}>Predict</button>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── SIGINT Panel ──────────────────────────────────────────────────────────────
function SigintPanel() {
  const { get, post } = useApi()
  const [res, setRes]   = useState(null)
  const [fstart, setFs] = useState(87500000)
  const [fstop, setFe]  = useState(108000000)
  const [fmhz, setFmhz] = useState(100.0)
  const [mod, setMod]   = useState('FM')

  return (
    <div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/surveillance/sigint/protocols').then(setRes)}>Protocols</button>
        <button style={btn()} onClick={() => get('/surveillance/sigint/df-methods').then(setRes)}>DF Methods</button>
        <button style={btn()} onClick={() => get('/surveillance/sigint/emitters').then(setRes)}>Emitters DB</button>
      </div>
      <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div>
          <div style={{ color:'#aaffaa', fontSize:12, marginBottom:6 }}>Wideband Scan</div>
          <div style={{ color:'#888', fontSize:11 }}>Start Hz</div>
          <input style={inp} type="number" value={fstart} onChange={e => setFs(Number(e.target.value))} />
          <div style={{ color:'#888', fontSize:11 }}>Stop Hz</div>
          <input style={inp} type="number" value={fstop} onChange={e => setFe(Number(e.target.value))} />
          <button style={btn()} onClick={() => post('/surveillance/sigint/scan', { start_freq: fstart, stop_freq: fstop }).then(setRes)}>Scan</button>
          <button style={btn()} onClick={() => get(`/surveillance/sigint/classify?freq_mhz=${fmhz}`).then(setRes)}>Auto-Classify</button>
        </div>
        <div>
          <div style={{ color:'#aaffaa', fontSize:12, marginBottom:6 }}>Demodulate</div>
          <div style={{ color:'#888', fontSize:11 }}>Freq (MHz)</div>
          <input style={inp} type="number" value={fmhz} onChange={e => setFmhz(Number(e.target.value))} />
          <div style={{ color:'#888', fontSize:11 }}>Modulation</div>
          <input style={inp} value={mod} onChange={e => setMod(e.target.value)} placeholder="FM, AM, NFM, FSK..." />
          <button style={btn()} onClick={() => post('/surveillance/sigint/demodulate', { freq_mhz: fmhz, modulation: mod }).then(setRes)}>Demodulate</button>
          <button style={btn()} onClick={() => get(`/surveillance/sigint/burst?freq_mhz=${fmhz}`).then(setRes)}>Burst Detection</button>
          <button style={btn()} onClick={() => post('/surveillance/sigint/fhss', { base_freq_mhz: fmhz, hop_rate_hz: 100 }).then(setRes)}>FHSS Track</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Satellite ISR Panel ───────────────────────────────────────────────────────
function SatellitePanel() {
  const { get, post } = useApi()
  const [res, setRes]   = useState(null)
  const [satName, setSat] = useState('PLEIADES_NEO3')
  const [lat, setLat]   = useState(48.85)
  const [lon, setLon]   = useState(2.35)

  return (
    <div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/surveillance/satellite/list').then(setRes)}>All Satellites</button>
        <button style={btn()} onClick={() => get('/surveillance/satellite/list?sat_type=SAR').then(setRes)}>SAR Sats</button>
        <button style={btn()} onClick={() => get('/surveillance/satellite/list?sat_type=EO').then(setRes)}>EO Sats</button>
        <button style={btn()} onClick={() => get('/surveillance/satellite/orbit-types').then(setRes)}>Orbits</button>
        <button style={btn()} onClick={() => get('/surveillance/satellite/tasking-modes').then(setRes)}>Tasking Modes</button>
      </div>
      <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>Satellite Name</div>
          <input style={inp} value={satName} onChange={e => setSat(e.target.value)} />
          <div style={{ color:'#888', fontSize:11 }}>Target Lat / Lon</div>
          <input style={{...inp, width:'45%', marginRight:'3%'}} type="number" value={lat} onChange={e => setLat(Number(e.target.value))} />
          <input style={{...inp, width:'45%'}} type="number" value={lon} onChange={e => setLon(Number(e.target.value))} />
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:4, justifyContent:'center' }}>
          <button style={btn()} onClick={() => get(`/surveillance/satellite/${satName}`).then(setRes)}>Satellite Detail</button>
          <button style={btn()} onClick={() => get(`/surveillance/satellite/${satName}/passes?lat=${lat}&lon=${lon}`).then(setRes)}>Predict Passes</button>
          <button style={btn()} onClick={() => post('/surveillance/satellite/task', { sat_name: satName, target_lat: lat, target_lon: lon, mode: 'spotlight' }).then(setRes)}>Task Satellite</button>
          <button style={btn()} onClick={() => post('/surveillance/satellite/isr-plan', { target_name: 'Target', lat, lon, priority: 'HIGH' }).then(setRes)}>ISR Plan</button>
          <button style={btn()} onClick={() => post('/surveillance/satellite/sar-analysis', { target_lat: lat, target_lon: lon }).then(setRes)}>SAR Analysis</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

const TABS = [
  { id:'air',  label:'Air / ADS-B' },
  { id:'sea',  label:'Maritime / AIS' },
  { id:'sig',  label:'SIGINT / DF' },
  { id:'sat',  label:'Satellite ISR' },
]

export default function SurveillanceStratView() {
  const [tab, setTab] = useState('air')

  return (
    <div style={{ padding:20, color:'#00ff41', fontFamily:'monospace', maxWidth:960 }}>
      <div style={{ fontSize:18, fontWeight:'bold', marginBottom:4, color:'#44aaff' }}>
        👁 Surveillance Stratégique — Bloc 12
      </div>
      <div style={{ color:'#888', fontSize:12, marginBottom:14 }}>
        ADS-B · MLAT · ACARS · AIS Maritime · SIGINT · Direction Finding · Satellite ISR
      </div>

      <div style={{ display:'flex', gap:6, marginBottom:16, borderBottom:'1px solid #1a3a1a', paddingBottom:8 }}>
        {TABS.map(t => (
          <button key={t.id} style={{ ...btn(tab===t.id ? '#002040':'#050505', tab===t.id ? '#44aaff':'#336688'),
            borderColor: tab===t.id ? '#44aaff':'#1a3a1a' }}
            onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      {tab === 'air' && <AirPanel />}
      {tab === 'sea' && <MaritimePanel />}
      {tab === 'sig' && <SigintPanel />}
      {tab === 'sat' && <SatellitePanel />}
    </div>
  )
}
