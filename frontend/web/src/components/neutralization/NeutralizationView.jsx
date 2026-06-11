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

function Warn() {
  return <div style={{ background:'#1a0000', border:'1px solid #ff3333', borderRadius:5,
    padding:'7px 12px', marginBottom:10, fontSize:12, color:'#ff6666' }}>
    ⚠️ CAPACITÉS OFFENSIVES CRITIQUES — Autorisation contractuelle obligatoire — Simulation by default
  </div>
}

// ── SCADA/ICS Panel ────────────────────────────────────────────────────────────
function ScadaPanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [ip, setIp]   = useState('192.168.1.100')
  const [auth, setAuth] = useState(false)
  const [addr, setAddr] = useState(0)
  const [val, setVal]   = useState(0)

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/neutralization/scada/scan').then(setRes)}>Scan ICS Network</button>
        <button style={btn()} onClick={() => get('/neutralization/scada/protocols').then(setRes)}>Protocols</button>
        <button style={btn()} onClick={() => get('/neutralization/scada/attack-vectors').then(setRes)}>Attack Vectors</button>
        <button style={btn()} onClick={() => get('/neutralization/scada/sectors').then(setRes)}>Critical Sectors</button>
      </div>
      <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>Target IP</div>
          <input style={inp} value={ip} onChange={e => setIp(e.target.value)} />
          <div style={{ color:'#888', fontSize:11 }}>Modbus Address / Value</div>
          <div style={{ display:'flex', gap:4 }}>
            <input style={{...inp, width:'45%'}} type="number" value={addr} onChange={e => setAddr(Number(e.target.value))} placeholder="Address" />
            <input style={{...inp, width:'45%'}} type="number" value={val}  onChange={e => setVal(Number(e.target.value))}  placeholder="Value" />
          </div>
          <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
            authorization_confirmed
          </label>
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
          <button style={btn()} onClick={() => get(`/neutralization/scada/read?target_ip=${ip}&function_code=3&count=10`).then(setRes)}>Modbus Read</button>
          <button style={btn()} onClick={() => get(`/neutralization/scada/opc-browse?target_ip=${ip}`).then(setRes)}>OPC-UA Browse</button>
          <button style={btn()} onClick={() => get(`/neutralization/scada/firmware?target_ip=${ip}`).then(setRes)}>Firmware Extract</button>
          <button style={btn()} onClick={() => get(`/neutralization/scada/s7-upload?target_ip=${ip}`).then(setRes)}>S7 Block Upload</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/scada/write', { target_ip: ip, address: addr, value: val, authorization_confirmed: auth }).then(setRes)}>Modbus Write</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/scada/s7-stop', { target_ip: ip, authorization_confirmed: auth }).then(setRes)}>S7 PLC STOP</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/scada/dnp3-restart', { target_ip: ip, authorization_confirmed: auth }).then(setRes)}>DNP3 Cold Restart</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/scada/goose-spoof', { target_ip: ip, goose_id: 'IED01XCBR1$GO$gseDATASET1', trip_command: true, authorization_confirmed: auth }).then(setRes)}>IEC 61850 GOOSE TRIP</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Military Protocols Panel ────────────────────────────────────────────────────
function MilProtPanel() {
  const { get, post } = useApi()
  const [res, setRes] = useState(null)
  const [auth, setAuth] = useState(false)
  const [uavIp, setUavIp] = useState('10.0.0.50')

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/neutralization/milprot/protocols').then(setRes)}>List Protocols</button>
        <button style={btn()} onClick={() => get('/neutralization/milprot/attack-scenarios').then(setRes)}>Attack Scenarios</button>
        <button style={btn()} onClick={() => get('/neutralization/milprot/link16/j-series').then(setRes)}>Link-16 J-Series</button>
        <button style={btn()} onClick={() => get('/neutralization/milprot/1553/scan').then(setRes)}>MIL-1553 Scan</button>
        <button style={btn()} onClick={() => get('/neutralization/milprot/link16/traffic').then(setRes)}>Link-16 Traffic</button>
      </div>
      <div style={{ marginTop:8 }}>
        <input style={{...inp, width:160}} value={uavIp} onChange={e => setUavIp(e.target.value)} placeholder="UAV IP" />
        <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer', marginLeft:8 }}>
          <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
          auth_confirmed
        </label>
      </div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginTop:4 }}>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/milprot/1553/inject', { rt_address: 5, subaddress: 3, data_words: [0x1234,0x5678], authorization_confirmed: auth }).then(setRes)}>1553 Inject</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/milprot/arinc429/spoof', { label: 0o206, value: 99999.0, authorization_confirmed: auth }).then(setRes)}>ARINC-429 Spoof Altitude</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/milprot/link16/jam', { authorization_confirmed: auth }).then(setRes)}>Link-16 Jam</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/milprot/iff/spoof', { mode:'3A', code:'7700', authorization_confirmed: auth }).then(setRes)}>IFF Spoof</button>
        <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/milprot/stanag/hijack', { uav_ip: uavIp, new_waypoint_lat: 48.85, new_waypoint_lon: 2.35, authorization_confirmed: auth }).then(setRes)}>STANAG UAV Hijack</button>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Network Neutralization Panel ───────────────────────────────────────────────
function NetworkPanel() {
  const { get, post } = useApi()
  const [res, setRes]     = useState(null)
  const [auth, setAuth]   = useState(false)
  const [prefix, setPrefix] = useState('203.0.113.0/24')
  const [asn, setAsn]       = useState(64512)
  const [domain, setDomain] = useState('target.example.com')
  const [targetIp, setTip]  = useState('192.0.2.1')

  return (
    <div>
      <Warn />
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/neutralization/network/attack-types').then(setRes)}>Attack Types</button>
        <button style={btn()} onClick={() => get('/neutralization/network/amplification-factors').then(setRes)}>Amplification Factors</button>
        <button style={btn()} onClick={() => get('/neutralization/network/bgp-communities').then(setRes)}>BGP Communities</button>
        <button style={btn()} onClick={() => get(`/neutralization/network/infra-scan?target_asn=${asn}`).then(setRes)}>Infra Scan</button>
      </div>
      <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>BGP Prefix</div>
          <input style={inp} value={prefix} onChange={e => setPrefix(e.target.value)} />
          <div style={{ color:'#888', fontSize:11 }}>Attacker ASN</div>
          <input style={inp} type="number" value={asn} onChange={e => setAsn(Number(e.target.value))} />
          <div style={{ color:'#888', fontSize:11 }}>Target Domain / IP</div>
          <input style={inp} value={domain} onChange={e => setDomain(e.target.value)} />
          <input style={inp} value={targetIp} onChange={e => setTip(e.target.value)} placeholder="Target IP" />
          <label style={{ fontSize:12, color:'#ff9944', cursor:'pointer' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} style={{ marginRight:4 }} />
            auth_confirmed
          </label>
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/bgp-hijack', { target_prefix: prefix, attacker_asn: asn, authorization_confirmed: auth }).then(setRes)}>BGP Hijack</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/bgp-blackhole', { target_prefix: prefix, authorization_confirmed: auth }).then(setRes)}>BGP Blackhole</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/dns-poison', { target_domain: domain, malicious_ip: '1.2.3.4', authorization_confirmed: auth }).then(setRes)}>DNS Cache Poison</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/dns-amplification', { target_ip: targetIp, authorization_confirmed: auth }).then(setRes)}>DNS Amplification DDoS</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/arp-spoof', { gateway_ip:'192.168.1.1', gateway_mac:'00:11:22:33:44:55', victim_ip: targetIp, attacker_mac:'AA:BB:CC:DD:EE:FF', authorization_confirmed: auth }).then(setRes)}>ARP Spoof</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/dhcp-starvation', { interface:'eth0', authorization_confirmed: auth }).then(setRes)}>DHCP Starvation</button>
          <button style={btn('#1a0000','#ff4444')} onClick={() => post('/neutralization/network/stp-attack', { interface:'eth0', authorization_confirmed: auth }).then(setRes)}>STP Root Takeover</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

// ── Missile Defense Panel ──────────────────────────────────────────────────────
function MissilePanel() {
  const { get, post } = useApi()
  const [res, setRes]   = useState(null)
  const [tid, setTid]   = useState('')
  const [sam, setSam]   = useState('patriot_pac3')
  const [threat, setTh] = useState('SRBM')

  return (
    <div>
      <div style={{ color:'#aaffaa', fontSize:12, marginBottom:8 }}>C-ABM / SAM Simulation</div>
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button style={btn()} onClick={() => get('/neutralization/missile/sam-systems').then(setRes)}>SAM Systems</button>
        <button style={btn()} onClick={() => get('/neutralization/missile/threat-classes').then(setRes)}>Threat Classes</button>
        <button style={btn()} onClick={() => get('/neutralization/missile/countermeasures').then(setRes)}>Countermeasures</button>
        <button style={btn()} onClick={() => get('/neutralization/missile/tracks').then(setRes)}>Active Tracks</button>
        <button style={btn()} onClick={() => get(`/neutralization/missile/effectiveness?threat_type=${threat}&cm_type=kinetic_intercept`).then(setRes)}>CM Effectiveness</button>
      </div>
      <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div>
          <div style={{ color:'#888', fontSize:11 }}>Threat Type</div>
          <select style={{...inp, background:'#050505'}} value={threat} onChange={e => setTh(e.target.value)}>
            {['SRBM','MRBM','ICBM','cruise','hypersonic','aircraft','UAV','swarm_UAV'].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <div style={{ color:'#888', fontSize:11 }}>SAM System</div>
          <select style={{...inp, background:'#050505'}} value={sam} onChange={e => setSam(e.target.value)}>
            {['patriot_pac3','s400','s500','thaad','arrow3','iron_dome','aster_30','aster_30_b1nt','nasams','crotale_ng'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <div style={{ color:'#888', fontSize:11 }}>Track ID</div>
          <input style={inp} value={tid} onChange={e => setTid(e.target.value)} placeholder="trk_xxxxxxxx" />
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
          <button style={btn()} onClick={() =>
            post('/neutralization/missile/track', { threat_type: threat, launch_lat: 51.5, launch_lon: 37.6, target_lat: 48.85, target_lon: 2.35 }).then(d => { setRes(d); if(d?.track_id) setTid(d.track_id) })
          }>Simulate Inbound Track</button>
          <button style={btn()} onClick={() =>
            post('/neutralization/missile/engage', { track_id: tid, sam_system: sam, salvo_size: 2 }).then(setRes)
          }>Engage Track (Salvo 2)</button>
          <button style={btn()} onClick={() =>
            post('/neutralization/missile/multi-layer', { threat_type: threat, available_systems: ['thaad','patriot_pac3','aster_30','nasams'] }).then(setRes)
          }>Multi-Layer Analysis</button>
          <button style={btn()} onClick={() =>
            post('/neutralization/missile/saturation', { num_threats: 20, sam_systems: ['patriot_pac3','aster_30','nasams'] }).then(setRes)
          }>Saturation Analysis (20 threats)</button>
        </div>
      </div>
      <Result data={res} />
    </div>
  )
}

const TABS = [
  { id:'scada', label:'SCADA / ICS' },
  { id:'mil',   label:'Military Protocols' },
  { id:'net',   label:'Network Neutralization' },
  { id:'miss',  label:'Missile Defense' },
]

export default function NeutralizationView() {
  const [tab, setTab] = useState('scada')

  return (
    <div style={{ padding:20, color:'#00ff41', fontFamily:'monospace', maxWidth:960 }}>
      <div style={{ fontSize:18, fontWeight:'bold', marginBottom:4, color:'#ff4444' }}>
        💣 Neutralisation — Bloc 13
      </div>
      <div style={{ color:'#888', fontSize:12, marginBottom:14 }}>
        SCADA/ICS · Military Protocols (1553/Link-16/STANAG) · Network Neutralization · Missile Defense Sim
      </div>

      <div style={{ display:'flex', gap:6, marginBottom:16, borderBottom:'1px solid #3a1a1a', paddingBottom:8 }}>
        {TABS.map(t => (
          <button key={t.id} style={{ ...btn(tab===t.id ? '#200000':'#050505', tab===t.id ? '#ff4444':'#664444'),
            borderColor: tab===t.id ? '#ff4444':'#3a1a1a' }}
            onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      {tab === 'scada' && <ScadaPanel />}
      {tab === 'mil'   && <MilProtPanel />}
      {tab === 'net'   && <NetworkPanel />}
      {tab === 'miss'  && <MissilePanel />}
    </div>
  )
}
