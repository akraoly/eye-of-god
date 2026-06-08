import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'satellite', label: '🛰️ Satellite',    color: '#44ccff' },
  { id: 'maritime',  label: '🚢 Maritime',      color: '#4488ff' },
  { id: 'aviation',  label: '✈️ Aviation',      color: '#44ff88' },
  { id: 'darkweb',   label: '🕸️ Dark Web',     color: '#ff4466' },
  { id: 'crypto',    label: '₿ Crypto Tracer', color: '#ffaa00' },
]

function ResultBox({ data }) {
  if (!data) return null
  const isErr = data?.error
  return (
    <pre style={{
      background: '#0a0f1a', color: isErr ? '#ff6666' : '#7affb2',
      border: `1px solid ${isErr ? '#3a1a1a' : '#1a3a1a'}`,
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

const Sp = () => <span style={{ color: '#44ccff', marginLeft: 6 }}>⏳</span>

function useApi() {
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)
  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }
  const get = async (path) => {
    setLoading(true)
    try { setRes(await apiFetch(path)) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }
  return { res, loading, call, get }
}

const css = {
  panel: { background: '#0a1520', border: '1px solid #1a2a3a', borderRadius: 12, padding: 20 },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 },
  grid3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 },
  lbl: { display: 'block', fontSize: 11, color: '#667', marginBottom: 3 },
  inp: { width: '100%', background: '#060b14', border: '1px solid #1a2a3a', color: '#ccc', padding: '6px 9px', borderRadius: 6, fontSize: 12, boxSizing: 'border-box' },
  btns: { display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0' },
  btn: { background: '#1a2a3a', border: '1px solid #2a3a4a', color: '#aaccff', padding: '6px 13px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  sec: (c) => ({ fontSize: 11, color: c + '66', fontWeight: 700, margin: '12px 0 8px' }),
  auth: { display: 'flex', alignItems: 'center', gap: 6, color: '#ff4444', fontSize: 12, margin: '10px 0', cursor: 'pointer' },
}

function F({ label, children }) { return <div><label style={css.lbl}>{label}</label>{children}</div> }
function I({ value, onChange, type = 'text', placeholder = '' }) {
  return <input type={type} value={value} onChange={e => onChange(type === 'number' ? +e.target.value : e.target.value)} placeholder={placeholder} style={css.inp} />
}
function Sl({ value, onChange, opts }) {
  return <select value={value} onChange={e => onChange(e.target.value)} style={css.inp}>{opts.map(o => <option key={o}>{o}</option>)}</select>
}
function Btn({ onClick, children }) { return <button onClick={onClick} style={css.btn}>{children}</button> }
function Auth({ v, set }) {
  return <label style={css.auth}><input type="checkbox" checked={v} onChange={e => set(e.target.checked)} /> authorization_confirmed</label>
}
function H3({ color, children }) { return <h3 style={{ color, margin: '0 0 14px', fontSize: 15 }}>{children}</h3> }

// ─── SATELLITE ───────────────────────────────────────────────────────────────
function SatellitePanel() {
  const [lat, setLat]       = useState(48.8566)
  const [lon, setLon]       = useState(2.3522)
  const [sat, setSat]       = useState('sentinel2')
  const [analysis, setAna]  = useState('change_det')
  const [d1, setD1]         = useState('2024-01-01')
  const [d2, setD2]         = useState('2025-01-01')
  const [radius, setRadius] = useState(50.0)
  const [instName, setInst] = useState('Target Base')
  const [instType, setInstType] = useState('military_base')
  const [auth, setAuth]     = useState(false)
  const { res, loading, call, get } = useApi()

  const sats = ['sentinel2','sentinel1','landsat9','planet','maxar','capella','skysat']
  const analyses = ['change_det','ndvi','ndwi','nbr','object_det','sar_coh','thermal']
  const instTypes = ['military_base','nuclear_facility','missile_silo','airfield','submarine_base','radar_installation','port_activity','oil_terminal']

  return (
    <div style={css.panel}>
      <H3 color="#44ccff">🛰️ Satellite Intelligence — Sentinel / Maxar / Planet{loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Latitude"><I type="number" value={lat} onChange={setLat} /></F>
        <F label="Longitude"><I type="number" value={lon} onChange={setLon} /></F>
        <F label="Satellite"><Sl value={sat} onChange={setSat} opts={sats} /></F>
        <F label="Analyse"><Sl value={analysis} onChange={setAna} opts={analyses} /></F>
        <F label="Date avant"><I type="date" value={d1} onChange={setD1} /></F>
        <F label="Date après"><I type="date" value={d2} onChange={setD2} /></F>
        <F label="Rayon (km)"><I type="number" value={radius} onChange={setRadius} /></F>
        <F label="Installation"><I value={instName} onChange={setInst} /></F>
        <F label="Type installation"><Sl value={instType} onChange={setInstType} opts={instTypes} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => get('/geoint/satellite/list')}>📋 Satellites</Btn>
        <Btn onClick={() => get('/geoint/satellite/analysis-types')}>📊 Analyses</Btn>
        <Btn onClick={() => call('/geoint/satellite/acquire', { authorization_confirmed: auth, lat, lon, satellite: sat, cloud_cover_max: 20 })}>📷 Acquérir</Btn>
        <Btn onClick={() => call('/geoint/satellite/change-detection', { authorization_confirmed: auth, lat, lon, date_before: d1, date_after: d2, analysis_type: analysis, satellite: sat })}>🔄 Détection Changements</Btn>
        <Btn onClick={() => call('/geoint/satellite/military-activity', { authorization_confirmed: auth, lat, lon, radius_km: radius })}>🎯 Activité Militaire</Btn>
        <Btn onClick={() => call('/geoint/satellite/monitor', { authorization_confirmed: auth, name: instName, lat, lon, installation_type: instType })}>👁️ Surveiller Installation</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── MARITIME ────────────────────────────────────────────────────────────────
function MaritimePanel() {
  const [id, setId]           = useState('123456789')
  const [idType, setIdType]   = useState('mmsi')
  const [lat, setLat]         = useState(26.0)
  const [lon, setLon]         = useState(53.0)
  const [radius, setRadius]   = useState(50.0)
  const [region, setRegion]   = useState('Persian Gulf')
  const [mmsiList, setMmsiList] = useState('123456789,987654321')
  const [auth, setAuth]       = useState(false)
  const { res, loading, call, get } = useApi()

  const regions = ['Persian Gulf','Arabian Sea','Black Sea','South China Sea','Baltic Sea','Mediterranean']

  return (
    <div style={css.panel}>
      <H3 color="#4488ff">🚢 Maritime Intelligence — AIS / Dark Shipping / Sanctions{loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Identifiant navire"><I value={id} onChange={setId} /></F>
        <F label="Type ID"><Sl value={idType} onChange={setIdType} opts={['mmsi','imo','name']} /></F>
        <F label="Latitude"><I type="number" value={lat} onChange={setLat} /></F>
        <F label="Longitude"><I type="number" value={lon} onChange={setLon} /></F>
        <F label="Rayon (nm)"><I type="number" value={radius} onChange={setRadius} /></F>
        <F label="Région"><Sl value={region} onChange={setRegion} opts={regions} /></F>
        <F label="Liste MMSI (sanctions)"><I value={mmsiList} onChange={setMmsiList} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => get('/geoint/maritime/high-risk-ports')}>⚠️ Ports à risque</Btn>
        <Btn onClick={() => call('/geoint/maritime/track', { authorization_confirmed: auth, identifier: id, id_type: idType, history_days: 30 })}>🔍 Tracker navire</Btn>
        <Btn onClick={() => call('/geoint/maritime/search-area', { authorization_confirmed: auth, lat, lon, radius_nm: radius })}>🗺️ Zone de recherche</Btn>
        <Btn onClick={() => call('/geoint/maritime/dark-shipping', { authorization_confirmed: auth, region, days: 30 })}>🌑 Dark Shipping</Btn>
        <Btn onClick={() => call('/geoint/maritime/sts-transfer', { authorization_confirmed: auth, area: region })}>🔄 STS Transfer</Btn>
        <Btn onClick={() => call('/geoint/maritime/sanctions-screen', { authorization_confirmed: auth, mmsi_list: mmsiList.split(',').map(s => s.trim()) })}>🚫 Sanctions Check</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── AVIATION ────────────────────────────────────────────────────────────────
function AviationPanel() {
  const [icao, setIcao]       = useState('a00001')
  const [idType, setIdType]   = useState('icao24')
  const [lat, setLat]         = useState(50.0)
  const [lon, setLon]         = useState(14.0)
  const [radius, setRadius]   = useState(200.0)
  const [owner, setOwner]     = useState('')
  const [tail, setTail]       = useState('')
  const [region, setRegion]   = useState('Eastern Europe')
  const [squawk, setSquawk]   = useState('7700')
  const [auth, setAuth]       = useState(false)
  const { res, loading, call } = useApi()

  const regions = ['Eastern Europe','Middle East','South China Sea','Baltic Region','Arctic','Pacific','Atlantic']
  const squawks = ['7500','7600','7700','0000']

  return (
    <div style={css.panel}>
      <H3 color="#44ff88">✈️ Aviation Intelligence — ADS-B / Militaire / Jets Privés{loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="ICAO24 / Callsign"><I value={icao} onChange={setIcao} /></F>
        <F label="Type ID"><Sl value={idType} onChange={setIdType} opts={['icao24','callsign','registration']} /></F>
        <F label="Latitude"><I type="number" value={lat} onChange={setLat} /></F>
        <F label="Longitude"><I type="number" value={lon} onChange={setLon} /></F>
        <F label="Rayon (nm)"><I type="number" value={radius} onChange={setRadius} /></F>
        <F label="Région militaire"><Sl value={region} onChange={setRegion} opts={regions} /></F>
        <F label="Propriétaire (jet privé)"><I value={owner} onChange={setOwner} placeholder="VIP name" /></F>
        <F label="Immatriculation"><I value={tail} onChange={setTail} placeholder="N12345" /></F>
        <F label="Squawk code"><Sl value={squawk} onChange={setSquawk} opts={squawks} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => call('/geoint/aviation/track', { authorization_confirmed: auth, identifier: icao, id_type: idType, history_hours: 24 })}>🔍 Tracker vol</Btn>
        <Btn onClick={() => call('/geoint/aviation/monitor-region', { authorization_confirmed: auth, lat, lon, radius_nm: radius })}>🗺️ Surveiller région</Btn>
        <Btn onClick={() => call('/geoint/aviation/private-jet', { authorization_confirmed: auth, owner_name: owner, tail_number: tail, history_days: 90 })}>✈️ Jet privé</Btn>
        <Btn onClick={() => call('/geoint/aviation/military-ops', { authorization_confirmed: auth, region, hours: 48 })}>🎯 Ops militaires</Btn>
        <Btn onClick={() => call('/geoint/aviation/squawk-alert', { authorization_confirmed: auth, squawk })}>🚨 Squawk {squawk}</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── DARK WEB ─────────────────────────────────────────────────────────────────
function DarkWebPanel() {
  const [keywords, setKeywords] = useState('company.com,admin@company.com')
  const [domain, setDomain]     = useState('company.com')
  const [gang, setGang]         = useState('LockBit')
  const [terms, setTerms]       = useState('0day,initial access')
  const [onion, setOnion]       = useState('')
  const [depth, setDepth]       = useState(2)
  const [auth, setAuth]         = useState(false)
  const { res, loading, call, get } = useApi()

  const gangs = ['LockBit','BlackCat','Cl0p','RansomHub','Play','Akira','DragonForce','Qilin']

  return (
    <div style={css.panel}>
      <H3 color="#ff4466">🕸️ Dark Web Intelligence — Tor / Forums / Ransomware{loading && <Sp />}</H3>
      <div style={css.grid2}>
        <F label="Mots-clés (monitoring)"><I value={keywords} onChange={setKeywords} placeholder="company.com,email@corp.com" /></F>
        <F label="Domaine (credential leaks)"><I value={domain} onChange={setDomain} placeholder="company.com" /></F>
        <F label="Gang ransomware"><Sl value={gang} onChange={setGang} opts={gangs} /></F>
        <F label="Termes marchés"><I value={terms} onChange={setTerms} placeholder="0day,initial access" /></F>
        <F label="URL .onion (crawl)"><I value={onion} onChange={setOnion} placeholder="xxxx...xxxx.onion" /></F>
        <F label="Profondeur crawl"><I type="number" value={depth} onChange={setDepth} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => get('/geoint/darkweb/gangs')}>💀 Gangs</Btn>
        <Btn onClick={() => get('/geoint/darkweb/markets')}>🏪 Marchés</Btn>
        <Btn onClick={() => call('/geoint/darkweb/monitor', { authorization_confirmed: auth, keywords: keywords.split(',').map(s => s.trim()), sources: null, depth: 'standard' })}>🔍 Monitorer</Btn>
        <Btn onClick={() => call('/geoint/darkweb/credential-leak', { authorization_confirmed: auth, email_or_domain: domain })}>🔑 Credential Leaks</Btn>
        <Btn onClick={() => call('/geoint/darkweb/ransomware/track', { authorization_confirmed: auth, gang_name: gang })}>🎯 Tracker Gang</Btn>
        <Btn onClick={() => call('/geoint/darkweb/markets/search', { authorization_confirmed: auth, search_terms: terms.split(',').map(s => s.trim()) })}>🛒 Rechercher Marchés</Btn>
        <Btn onClick={() => call('/geoint/darkweb/onion/crawl', { authorization_confirmed: auth, onion_url: onion, depth })}>🕷️ Crawl .onion</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── CRYPTO TRACER ────────────────────────────────────────────────────────────
function CryptoPanel() {
  const [address, setAddress]   = useState('')
  const [blockchain, setChain]  = useState('bitcoin')
  const [algorithm, setAlgo]    = useState('common_input_ownership')
  const [ransomAddr, setRansom] = useState('')
  const [gang, setGang]         = useState('LockBit')
  const [contract, setContract] = useState('')
  const [network, setNetwork]   = useState('ethereum')
  const [auth, setAuth]         = useState(false)
  const { res, loading, call, get } = useApi()

  const chains = ['bitcoin','ethereum','tron','litecoin','zcash','monero']
  const algos = ['common_input_ownership','change_address','dust_attack','peeling_chain']
  const gangs = ['LockBit','BlackCat','Cl0p','RansomHub','Play','Akira']

  return (
    <div style={css.panel}>
      <H3 color="#ffaa00">₿ Crypto Tracer — Blockchain Analysis / Mixer / Ransomware{loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Adresse wallet"><I value={address} onChange={setAddress} placeholder="1A1zP1... / 0x..." /></F>
        <F label="Blockchain"><Sl value={blockchain} onChange={setChain} opts={chains} /></F>
        <F label="Algorithme clustering"><Sl value={algorithm} onChange={setAlgo} opts={algos} /></F>
        <F label="Adresse ransom"><I value={ransomAddr} onChange={setRansom} placeholder="bc1q..." /></F>
        <F label="Gang ransomware"><Sl value={gang} onChange={setGang} opts={gangs} /></F>
        <F label="Contrat DeFi"><I value={contract} onChange={setContract} placeholder="0x..." /></F>
        <F label="Réseau DeFi"><Sl value={network} onChange={setNetwork} opts={['ethereum','bsc','polygon','arbitrum','avalanche']} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => get('/geoint/crypto/blockchains')}>📋 Blockchains</Btn>
        <Btn onClick={() => get('/geoint/crypto/known-entities')}>🏦 Entités connues</Btn>
        <Btn onClick={() => call('/geoint/crypto/trace', { authorization_confirmed: auth, address, blockchain, depth: 3 })}>🔍 Tracer adresse</Btn>
        <Btn onClick={() => call('/geoint/crypto/cluster', { authorization_confirmed: auth, seed_address: address, blockchain, algorithm })}>🕸️ Clustering</Btn>
        <Btn onClick={() => call('/geoint/crypto/ransomware/track', { authorization_confirmed: auth, ransom_address: ransomAddr, gang, blockchain })}>💰 Tracker ransom</Btn>
        <Btn onClick={() => call('/geoint/crypto/mixer/detect', { authorization_confirmed: auth, address, blockchain, lookback_txs: 100 })}>🔀 Détecter mixer</Btn>
        <Btn onClick={() => call('/geoint/crypto/defi/analyze', { authorization_confirmed: auth, contract_address: contract, network })}>⚙️ Analyser DeFi</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function GeointBloc6() {
  const [tab, setTab] = useState('satellite')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          🌍 OSINT Géopolitique — Bloc 6
          <span style={{ marginLeft: 12, fontSize: 12, color: '#ff4444', fontWeight: 700 }}>SIMULATION + API LIVE</span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          Satellite (Sentinel/Maxar) · Maritime AIS / Dark Shipping · Aviation ADS-B · Dark Web / Ransomware · Crypto Blockchain
        </p>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '8px 18px', borderRadius: 8,
            border: `1px solid ${tab === t.id ? t.color : '#1a2a3a'}`,
            background: tab === t.id ? t.color + '22' : '#0a1520',
            color: tab === t.id ? t.color : '#667',
            cursor: 'pointer', fontSize: 13, fontWeight: tab === t.id ? 700 : 400,
            transition: 'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {tab === 'satellite' && <SatellitePanel />}
      {tab === 'maritime'  && <MaritimePanel />}
      {tab === 'aviation'  && <AviationPanel />}
      {tab === 'darkweb'   && <DarkWebPanel />}
      {tab === 'crypto'    && <CryptoPanel />}
    </div>
  )
}
