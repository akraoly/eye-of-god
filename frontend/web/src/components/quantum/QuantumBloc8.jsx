import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'quantum',       label: '⚛️ Attaques Quantiques', color: '#44aaff' },
  { id: 'pqc',          label: '🔐 Post-Quantum (PQC)',   color: '#44ff88' },
  { id: 'cryptoattacks', label: '🔓 Attaques Crypto',     color: '#ff6644' },
  { id: 'cryptoimpl',   label: '🔬 Impl. Attacks',        color: '#ffaa00' },
  { id: 'keymanager',   label: '🗝️ Key Manager / QKD',   color: '#cc44ff' },
]

function ResultBox({ data }) {
  if (!data) return null
  const isErr = data?.error
  return (
    <pre style={{
      background: '#0a0f1a', color: isErr ? '#ff6666' : '#7affb2',
      border: `1px solid ${isErr ? '#3a1a1a' : '#1a3a1a'}`,
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 360, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
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
  auth: { display: 'flex', alignItems: 'center', gap: 6, color: '#ff4444', fontSize: 12, margin: '10px 0', cursor: 'pointer' },
  info: { background: '#0a1a2a', border: '1px solid #1a3a4a', borderRadius: 6, padding: '8px 12px', color: '#44aaff', fontSize: 11, marginBottom: 10 },
}

function F({ label, children }) { return <div><label style={css.lbl}>{label}</label>{children}</div> }
function I({ value, onChange, type = 'text', placeholder = '', rows }) {
  if (rows) return <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={rows} style={{...css.inp, resize: 'vertical'}} />
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

// ─── QUANTUM ATTACKS ──────────────────────────────────────────────────────────
function QuantumPanel() {
  const [algo, setAlgo]     = useState('RSA')
  const [keySize, setSize]  = useState(2048)
  const [qubits, setQubits] = useState(10000)
  const [symAlgo, setSym]   = useState('AES_128')
  const [targets, setTargets] = useState('[{"algorithm":"RSA","key_size":2048,"data_type":"financial","retention_years":10}]')
  const [auth, setAuth]     = useState(false)
  const api = useApi()

  const rsaSizes  = [512, 1024, 2048, 3072, 4096, 7680, 15360]
  const eccSizes  = [160, 224, 256, 384, 521]
  const symAlgos  = ['DES_56','3DES_112','AES_128','AES_192','AES_256','ChaCha20']

  const parseTargets = () => { try { return JSON.parse(targets) } catch { return [] } }

  return (
    <div style={css.panel}>
      <H3 color="#44aaff">⚛️ Attaques Quantiques — Shor / Grover / Q-Day{api.loading && <Sp />}</H3>
      <div style={css.info}>Simulation mathématique — aucune infrastructure quantique réelle. Q-Day consensus: 2033.</div>
      <div style={css.grid3}>
        <F label="Algorithme asymétrique"><Sl value={algo} onChange={setAlgo} opts={['RSA','ECC','ECDH','ECDSA','DH']} /></F>
        <F label="Taille clé RSA/ECC (bits)"><Sl value={String(keySize)} onChange={v => setSize(+v)} opts={[...rsaSizes,...eccSizes].map(String)} /></F>
        <F label="Qubits disponibles (sim)"><I type="number" value={qubits} onChange={setQubits} /></F>
        <F label="Algorithme symétrique (Grover)"><Sl value={symAlgo} onChange={setSym} opts={symAlgos} /></F>
        <F label="Cibles HNDL (JSON)"><I value={targets} onChange={setTargets} placeholder='[{"algorithm":"RSA",...}]' /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/algorithms')}>📋 Algorithmes quantiques</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/rsa-analysis')}>🔢 Analyse RSA</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/ecc-analysis')}>🔢 Analyse ECC</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/symmetric-analysis')}>🔑 Analyse symétriques</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/hash-analysis')}>#️⃣ Analyse hashes</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/quantum/qday-estimates')}>📅 Q-Day estimates</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/quantum/simulate-shor', { authorization_confirmed: auth, algorithm: algo, key_size: keySize, qubits_available: qubits })}>⚡ Simuler Shor</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/quantum/simulate-grover', { authorization_confirmed: auth, algorithm: symAlgo, key_size: 128, qubits_available: qubits })}>⚡ Simuler Grover</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/quantum/harvest-now-decrypt-later', { authorization_confirmed: auth, targets: parseTargets() })}>🕵️ Harvest-Now Decrypt-Later</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── POST-QUANTUM ─────────────────────────────────────────────────────────────
function PQCPanel() {
  const [algoFilter, setFilter] = useState('')
  const [selectedAlgo, setSel]  = useState('kyber_768')
  const [components, setComps]  = useState('[{"name":"TLS API","algorithm":"ECDH-P256","protocol":"TLS","internet_exposed":true}]')
  const [currentAlgo, setCurr]  = useState('RSA-2048')
  const [targetAlgo, setTarget] = useState('kyber_768')
  const [system, setSystem]     = useState('API Gateway TLS')
  const [months, setMonths]     = useState(18)
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const pqcAlgos = ['kyber_512','kyber_768','kyber_1024','dilithium_2','dilithium_3','dilithium_5','sphincs_sha2_128s','falcon_512','falcon_1024']
  const parseComps = () => { try { return JSON.parse(components) } catch { return [] } }

  return (
    <div style={css.panel}>
      <H3 color="#44ff88">🔐 Post-Quantum Cryptography (PQC) — NIST FIPS 203/204/205/206{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Filtre type (KEM/Signature)"><Sl value={algoFilter} onChange={setFilter} opts={['','KEM','Signature']} /></F>
        <F label="Algorithme détaillé"><Sl value={selectedAlgo} onChange={setSel} opts={pqcAlgos} /></F>
        <F label="Algo actuel (migration)"><I value={currentAlgo} onChange={setCurr} /></F>
        <F label="Algo cible (migration)"><Sl value={targetAlgo} onChange={setTarget} opts={pqcAlgos} /></F>
        <F label="Système à migrer"><I value={system} onChange={setSystem} /></F>
        <F label="Timeline migration (mois)"><I type="number" value={months} onChange={setMonths} /></F>
        <F label="Composants audit (JSON)"><I value={components} onChange={setComps} placeholder='[{"name":"...","algorithm":"RSA-2048",...}]' /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get(`/quantum-crypto/pqc/algorithms${algoFilter ? '?type='+algoFilter : ''}`)}>📋 Algorithmes PQC</Btn>
        <Btn onClick={() => api.get(`/quantum-crypto/pqc/algorithm/${selectedAlgo}`)}>🔍 Détail algo</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/pqc/hybrid-schemes')}>🔀 Schémas hybrides</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/pqc/migration-roadmap')}>🗺️ Roadmap NIST</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/pqc/audit-surface', { authorization_confirmed: auth, components: parseComps() })}>🔍 Audit surface crypto</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/pqc/migration-plan', { authorization_confirmed: auth, current_algo: currentAlgo, target_algo: targetAlgo, system_name: system, timeline_months: months })}>📅 Plan de migration</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── CLASSICAL CRYPTO ATTACKS ─────────────────────────────────────────────────
function CryptoAttackPanel() {
  const [attackName, setAttack] = useState('POODLE')
  const [paddingVariant, setPad] = useState('cbc_padding_oracle')
  const [ciphers, setCiphers]   = useState('TLS_RSA_WITH_AES_128_CBC_SHA\nTLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384')
  const [tlsVers, setTlsVers]   = useState('TLSv1.0\nTLSv1.2\nTLSv1.3')
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const attacks  = ['BEAST','POODLE','CRIME','BREACH','HEARTBLEED','DROWN','ROBOT','lucky13','logjam','freak','sloth']
  const padVars  = ['cbc_padding_oracle','bleichenbacher','manger']

  return (
    <div style={css.panel}>
      <H3 color="#ff6644">🔓 Attaques Cryptographiques Classiques — TLS / Padding / GCM{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Attaque TLS"><Sl value={attackName} onChange={setAttack} opts={attacks} /></F>
        <F label="Variant Padding Oracle"><Sl value={paddingVariant} onChange={setPad} opts={padVars} /></F>
        <F label="Cipher suites (1 par ligne)"><I value={ciphers} onChange={setCiphers} rows={4} /></F>
        <F label="Versions TLS (1 par ligne)"><I value={tlsVers} onChange={setTlsVers} rows={3} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-attacks/tls-attacks')}>📋 Attaques TLS</Btn>
        <Btn onClick={() => api.get(`/quantum-crypto/crypto-attacks/tls-attack/${attackName}`)}>🔍 Détail attaque</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-attacks/hash-attacks')}>🔨 Hash attacks</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-attacks/padding-oracles')}>🎯 Padding oracles</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-attacks/aes-attacks')}>🔑 AES attacks</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-attacks/simulate-padding-oracle', { authorization_confirmed: auth, variant: paddingVariant, block_size: 16 })}>⚡ Simuler padding oracle</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-attacks/simulate-md5-collision', { authorization_confirmed: auth })}>💥 Simuler MD5 collision</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-attacks/simulate-gcm-nonce-reuse', { authorization_confirmed: auth })}>⚡ Simuler GCM nonce reuse</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-attacks/analyze-tls-config', {
          authorization_confirmed: auth,
          cipher_suites: ciphers.split('\n').map(s => s.trim()).filter(Boolean),
          tls_versions: tlsVers.split('\n').map(s => s.trim()).filter(Boolean),
        })}>🔍 Analyser config TLS</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── CRYPTO IMPL ATTACKS ──────────────────────────────────────────────────────
function CryptoImplPanel() {
  const [timingAttack, setTiming] = useState('hmac_timing')
  const [samples, setSamples]     = useState(10000)
  const [faultAttack, setFault]   = useState('differential_fault_analysis')
  const [codeSnippet, setCode]    = useState('import hashlib\nkey = b"hardcoded_secret"\nh = hashlib.md5(password.encode()).hexdigest()\nif h == expected_hash:  # timing oracle\n    return True')
  const [codeLang, setLang]       = useState('python')
  const [auth, setAuth]           = useState(false)
  const api = useApi()

  const timingAttacks = ['rsa_timing','ecdsa_timing','aes_cache_timing','hmac_timing','lattice_timing']
  const faultAttacks  = ['differential_fault_analysis','rsa_dfa','clock_glitching','voltage_glitching']

  return (
    <div style={css.panel}>
      <H3 color="#ffaa00">🔬 Attaques d'Implémentation — Timing / Fault / ECDSA Nonce{api.loading && <Sp />}</H3>
      <div style={css.grid2}>
        <F label="Timing attack"><Sl value={timingAttack} onChange={setTiming} opts={timingAttacks} /></F>
        <F label="Nombre d'échantillons"><I type="number" value={samples} onChange={setSamples} /></F>
        <F label="Fault attack"><Sl value={faultAttack} onChange={setFault} opts={faultAttacks} /></F>
        <F label="Langage analyse code"><Sl value={codeLang} onChange={setLang} opts={['python','java','c','csharp','javascript','go']} /></F>
      </div>
      <F label="Code à analyser (crypto audit)">
        <I value={codeSnippet} onChange={setCode} rows={5} />
      </F>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-impl/timing-attacks')}>📋 Timing attacks</Btn>
        <Btn onClick={() => api.get(`/quantum-crypto/crypto-impl/timing-attack/${timingAttack}`)}>🔍 Détail timing</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-impl/fault-attacks')}>⚡ Fault attacks</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-impl/nonce-attacks')}>🎲 Nonce attacks (PS3)</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/crypto-impl/cold-boot')}>❄️ Cold Boot Attack</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-impl/simulate-ecdsa-nonce-reuse', { authorization_confirmed: auth })}>⚡ Simuler ECDSA nonce reuse</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-impl/simulate-timing-oracle', { authorization_confirmed: auth, attack_type: timingAttack, samples })}>⏱️ Simuler timing oracle</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/crypto-impl/analyze-code', { authorization_confirmed: auth, code_snippet: codeSnippet, language: codeLang })}>🔍 Analyser code crypto</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── KEY MANAGER / QKD ────────────────────────────────────────────────────────
function KeyManagerPanel() {
  const [keyAlgo, setKeyAlgo]   = useState('kyber_768_sim')
  const [keyLabel, setLabel]    = useState('')
  const [exportable, setExport] = useState(false)
  const [qkdProto, setQkd]      = useState('bb84')
  const [distance, setDist]     = useState(50.0)
  const [targetBits, setBits]   = useState(256)
  const [protocol, setProto]    = useState('signal_protocol')
  const [masterKey, setMaster]  = useState('')
  const [context, setContext]   = useState('encryption')
  const [keyId, setKeyId]       = useState('')
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const keyAlgos = ['aes_256','aes_128','chacha20','ed25519','x25519','kyber_768_sim','dilithium_3_sim']
  const qkdProtos = ['bb84','e91','b92','sarg04','cv_qkd']
  const protocols = ['signal_protocol','matrix_megolm','tls_13','ike_v2','ssh']

  return (
    <div style={css.panel}>
      <H3 color="#cc44ff">🗝️ Key Manager & QKD — Génération / Distribution / Dérivation{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Algorithme clé"><Sl value={keyAlgo} onChange={setKeyAlgo} opts={keyAlgos} /></F>
        <F label="Label"><I value={keyLabel} onChange={setLabel} placeholder="ma-clé-critique" /></F>
        <F label="Exportable"><Sl value={String(exportable)} onChange={v => setExport(v === 'true')} opts={['false','true']} /></F>
        <F label="Protocole QKD"><Sl value={qkdProto} onChange={setQkd} opts={qkdProtos} /></F>
        <F label="Distance QKD (km)"><I type="number" value={distance} onChange={setDist} /></F>
        <F label="Bits clé QKD"><I type="number" value={targetBits} onChange={setBits} /></F>
        <F label="Protocole analyse PFS"><Sl value={protocol} onChange={setProto} opts={protocols} /></F>
        <F label="Clé maître (hex, derive)"><I value={masterKey} onChange={setMaster} placeholder="deadbeef..." /></F>
        <F label="Contexte dérivation"><I value={context} onChange={setContext} /></F>
        <F label="Key ID (get)"><I value={keyId} onChange={setKeyId} placeholder="uuid" /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/quantum-crypto/keymanager/algorithms')}>📋 Algorithmes</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/keymanager/qkd-protocols')}>📡 Protocoles QKD</Btn>
        <Btn onClick={() => api.get(`/quantum-crypto/keymanager/qkd/${qkdProto}`)}>🔍 Détail QKD</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/keymanager/secure-protocols')}>🛡️ Protocoles sécurisés</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/keymanager/hsm-operations')}>🏦 Opérations HSM</Btn>
        <Btn onClick={async () => {
          const data = await apiFetch('/quantum-crypto/keymanager/generate', {
            method: 'POST',
            body: JSON.stringify({ authorization_confirmed: auth, algorithm: keyAlgo, label: keyLabel, exportable, hsm_protected: true })
          }).catch(e => ({ error: e.message }))
          if (data?.key_id) setKeyId(data.key_id)
          else api.get('/quantum-crypto/keymanager/list')
        }}>🔑 Générer clé</Btn>
        <Btn onClick={() => api.get('/quantum-crypto/keymanager/list')}>📋 Toutes les clés</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/keymanager/qkd-session', { authorization_confirmed: auth, protocol: qkdProto, distance_km: distance, target_key_bits: targetBits })}>🌌 Session QKD</Btn>
        <Btn onClick={() => api.call('/quantum-crypto/keymanager/derive', { authorization_confirmed: auth, master_key_hex: masterKey || '0'.repeat(64), context, output_bits: 256 })}>🔄 Dériver clé (HKDF)</Btn>
        <Btn onClick={() => api.get(`/quantum-crypto/keymanager/pfs/${protocol}`)}>🔒 Analyse PFS</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function QuantumBloc8() {
  const [tab, setTab] = useState('quantum')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          ⚛️ Quantum & Cryptographie — Bloc 8
          <span style={{ marginLeft: 12, fontSize: 12, color: '#44aaff', fontWeight: 700 }}>SIMULATION MATHÉMATIQUE</span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          Shor / Grover / Q-Day · PQC NIST (Kyber/Dilithium/FALCON/SPHINCS+) · Attaques TLS/padding/GCM · Timing / Fault · QKD / Key Management
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

      {tab === 'quantum'        && <QuantumPanel />}
      {tab === 'pqc'            && <PQCPanel />}
      {tab === 'cryptoattacks'  && <CryptoAttackPanel />}
      {tab === 'cryptoimpl'     && <CryptoImplPanel />}
      {tab === 'keymanager'     && <KeyManagerPanel />}
    </div>
  )
}
