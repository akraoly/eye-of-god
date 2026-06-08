import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'em',          label: '📡 EM / TEMPEST',    color: '#ff4444' },
  { id: 'acoustic',    label: '🔊 Acoustique',       color: '#ff8800' },
  { id: 'sidechannel', label: '⚡ Side-Channel',     color: '#ffcc00' },
  { id: 'thermal',     label: '🌡️ Thermal/Optical', color: '#44ff88' },
  { id: 'usb',         label: '🔌 USB / BadUSB',    color: '#aa44ff' },
]

function ResultBox({ data }) {
  if (!data) return null
  return (
    <pre style={{
      background: '#0a0f1a', color: '#7affb2', border: '1px solid #1a3a1a',
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 300, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function Spinner() { return <span style={{ color: '#44ccff', marginLeft: 6 }}>⏳</span> }

function Panel({ children, color }) {
  return (
    <div style={{
      background: '#0a1520', border: `1px solid ${color}33`,
      borderRadius: 12, padding: 20,
    }}>{children}</div>
  )
}

function AuthCheck({ checked, onChange }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#ff4444', fontSize: 12, margin: '10px 0', cursor: 'pointer' }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      authorization_confirmed — Pentest autorisé
    </label>
  )
}

function Grid({ children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>{children}</div>
}

function Field({ label, children }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 11, color: '#667', marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  )
}

function Inp({ ...props }) {
  return <input {...props} style={{ width: '100%', background: '#060b14', border: '1px solid #1a2a3a', color: '#ccc', padding: '6px 10px', borderRadius: 6, fontSize: 12, boxSizing: 'border-box' }} />
}

function Sel({ value, onChange, opts }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{ width: '100%', background: '#060b14', border: '1px solid #1a2a3a', color: '#ccc', padding: '6px 10px', borderRadius: 6, fontSize: 12 }}>
      {opts.map(o => <option key={o}>{o}</option>)}
    </select>
  )
}

function Btns({ children }) {
  return <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0' }}>{children}</div>
}

function Btn({ onClick, children }) {
  return (
    <button onClick={onClick} style={{ background: '#1a2a3a', border: '1px solid #2a3a4a', color: '#aaccff', padding: '7px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
      {children}
    </button>
  )
}

// ─── EM / TEMPEST ─────────────────────────────────────────────────────────────
function EMPanel() {
  const [targetIp, setTargetIp]   = useState('192.168.1.1')
  const [distance, setDistance]   = useState(5.0)
  const [freqMhz, setFreqMhz]     = useState(165.0)
  const [duration, setDuration]   = useState(60)
  const [targetDev, setTargetDev] = useState('smartcard')
  const [attackType, setAtk]      = useState('secure_boot_bypass')
  const [data, setData]           = useState('SECRET')
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }

  return (
    <Panel color="#ff4444">
      <h3 style={{ color: '#ff4444', margin: '0 0 14px' }}>📡 EM Injection & TEMPEST{loading && <Spinner />}</h3>
      <Grid>
        <Field label="Target IP / Cible"><Inp value={targetIp} onChange={e => setTargetIp(e.target.value)} /></Field>
        <Field label="Distance (m)"><Inp type="number" value={distance} onChange={e => setDistance(+e.target.value)} /></Field>
        <Field label="Fréquence (MHz)"><Inp type="number" value={freqMhz} onChange={e => setFreqMhz(+e.target.value)} /></Field>
        <Field label="Durée (sec)"><Inp type="number" value={duration} onChange={e => setDuration(+e.target.value)} /></Field>
        <Field label="Target Device (EMFI)"><Sel value={targetDev} onChange={setTargetDev} opts={['smartcard','hsm','microcontroller','fpga','router']} /></Field>
        <Field label="Type d'attaque EMFI"><Sel value={attackType} onChange={setAtk} opts={['secure_boot_bypass','key_extraction','privilege_escalation','rng_bias']} /></Field>
        <Field label="Données (ODINI)"><Inp value={data} onChange={e => setData(e.target.value)} /></Field>
      </Grid>
      <AuthCheck checked={auth} onChange={setAuth} />
      <Btns>
        <Btn onClick={() => apiFetch('/airgap/em/techniques').then(setRes).catch(e => setRes({error: e.message}))}>📋 Techniques</Btn>
        <Btn onClick={() => call('/airgap/em/scan', { authorization_confirmed: auth, target_ip: targetIp, duration_sec: duration })}>🔍 Scan EM</Btn>
        <Btn onClick={() => call('/airgap/em/van-eck', { authorization_confirmed: auth, target_distance_m: distance, frequency_mhz: freqMhz, duration_sec: duration })}>📺 Van Eck</Btn>
        <Btn onClick={() => call('/airgap/em/tempest/keyboard', { authorization_confirmed: auth, duration_sec: duration, antenna_gain_db: 12.0 })}>⌨️ TEMPEST Keylog</Btn>
        <Btn onClick={() => call('/airgap/em/fault-inject', { authorization_confirmed: auth, target_device: targetDev, attack_type: attackType })}>⚡ EMFI</Btn>
        <Btn onClick={() => call('/airgap/em/odini', { authorization_confirmed: auth, mode: 'transmit', data, receiver_device: 'smartphone' })}>💾 ODINI HDD</Btn>
      </Btns>
      <ResultBox data={res} />
    </Panel>
  )
}

// ─── ACOUSTIC ─────────────────────────────────────────────────────────────────
function AcousticPanel() {
  const [surface, setSurface]     = useState('window')
  const [distAc, setDistAc]       = useState(100.0)
  const [duration, setDuration]   = useState(60)
  const [data, setData]           = useState('EXFIL_DATA')
  const [freqKhz, setFreqKhz]     = useState(18.0)
  const [fmFreq, setFmFreq]       = useState(107.5)
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }

  return (
    <Panel color="#ff8800">
      <h3 style={{ color: '#ff8800', margin: '0 0 14px' }}>🔊 Canaux Acoustiques / Power-Line{loading && <Spinner />}</h3>
      <Grid>
        <Field label="Surface cible (laser)"><Sel value={surface} onChange={setSurface} opts={['window','monitor','picture_frame','whiteboard','coffee_mug']} /></Field>
        <Field label="Distance laser (m)"><Inp type="number" value={distAc} onChange={e => setDistAc(+e.target.value)} /></Field>
        <Field label="Durée (sec)"><Inp type="number" value={duration} onChange={e => setDuration(+e.target.value)} /></Field>
        <Field label="Données à exfiltrer"><Inp value={data} onChange={e => setData(e.target.value)} /></Field>
        <Field label="Fréquence ultrasonique (kHz)"><Inp type="number" value={freqKhz} onChange={e => setFreqKhz(+e.target.value)} /></Field>
        <Field label="Fréquence FM (MHz)"><Inp type="number" value={fmFreq} onChange={e => setFmFreq(+e.target.value)} /></Field>
      </Grid>
      <AuthCheck checked={auth} onChange={setAuth} />
      <Btns>
        <Btn onClick={() => apiFetch('/airgap/acoustic/techniques').then(setRes).catch(e => setRes({error: e.message}))}>📋 Techniques</Btn>
        <Btn onClick={() => call('/airgap/acoustic/laser-mic', { authorization_confirmed: auth, target_surface: surface, duration_sec: duration, distance_m: distAc })}>🔴 Laser Mic</Btn>
        <Btn onClick={() => call('/airgap/acoustic/mosquito', { authorization_confirmed: auth, mode: 'transmit', data, frequency_khz: freqKhz })}>🦟 MOSQUITO</Btn>
        <Btn onClick={() => call('/airgap/acoustic/fansmitter', { authorization_confirmed: auth, data, fan_min_rpm: 1000, fan_max_rpm: 3000 })}>🌀 FANSMITTER</Btn>
        <Btn onClick={() => call('/airgap/acoustic/airhopper', { authorization_confirmed: auth, data, fm_freq_mhz: fmFreq })}>📻 AirHopper FM</Btn>
        <Btn onClick={() => call('/airgap/acoustic/powerhammer', { authorization_confirmed: auth, data, circuit_type: 'in_line' })}>🔌 PowerHammer</Btn>
      </Btns>
      <ResultBox data={res} />
    </Panel>
  )
}

// ─── SIDE-CHANNEL ─────────────────────────────────────────────────────────────
function SideChannelPanel() {
  const [attack, setAttack]       = useState('cpa')
  const [algo, setAlgo]           = useState('AES-128')
  const [traces, setTraces]       = useState(1000)
  const [cacheAtk, setCacheAtk]   = useState('flush_reload')
  const [process, setProcess]     = useState('openssl')
  const [spectreVar, setSpectre]  = useState('spectre_v1')
  const [target, setTarget]       = useState('kernel')
  const [offset, setOffset]       = useState('0x1000')
  const [hhMethod, setHHMethod]   = useState('double_sided')
  const [targetUrl, setTargetUrl] = useState('https://target.example.com')
  const [samples, setSamples]     = useState(10000)
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }

  return (
    <Panel color="#ffcc00">
      <h3 style={{ color: '#ffcc00', margin: '0 0 14px' }}>⚡ Side-Channel — Power / Cache / Spectre{loading && <Spinner />}</h3>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#667', fontWeight: 700, marginBottom: 8 }}>— POWER ANALYSIS —</div>
        <Grid>
          <Field label="Attaque"><Sel value={attack} onChange={setAttack} opts={['spa','dpa','cpa']} /></Field>
          <Field label="Algorithme cible"><Sel value={algo} onChange={setAlgo} opts={['AES-128','AES-256','DES','RSA-1024','ECC-P256']} /></Field>
          <Field label="Nombre de traces"><Inp type="number" value={traces} onChange={e => setTraces(+e.target.value)} /></Field>
        </Grid>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#667', fontWeight: 700, marginBottom: 8 }}>— CACHE / SPECTRE —</div>
        <Grid>
          <Field label="Cache Attack"><Sel value={cacheAtk} onChange={setCacheAtk} opts={['flush_reload','prime_probe','spectre_v1','spectre_v2','meltdown']} /></Field>
          <Field label="Processus cible"><Inp value={process} onChange={e => setProcess(e.target.value)} /></Field>
          <Field label="Variante Spectre"><Sel value={spectreVar} onChange={setSpectre} opts={['spectre_v1','spectre_v2','meltdown','netspectre']} /></Field>
          <Field label="Mémoire cible"><Sel value={target} onChange={setTarget} opts={['kernel','hypervisor','browser','sgx','tee']} /></Field>
        </Grid>
      </div>

      <AuthCheck checked={auth} onChange={setAuth} />
      <Btns>
        <Btn onClick={() => apiFetch('/airgap/sidechannel/attacks').then(setRes).catch(e => setRes({error: e.message}))}>📋 Attacks</Btn>
        <Btn onClick={() => call('/airgap/sidechannel/power-analysis', { authorization_confirmed: auth, attack, target_algo: algo, num_traces: traces, hw_available: false })}>⚡ Power Analysis</Btn>
        <Btn onClick={() => call('/airgap/sidechannel/cache-attack', { authorization_confirmed: auth, attack: cacheAtk, target_process: process, duration_sec: 30 })}>💾 Cache Attack</Btn>
        <Btn onClick={() => call('/airgap/sidechannel/spectre', { authorization_confirmed: auth, variant: spectreVar, target, read_offset: parseInt(offset, 16) || 0x1000 })}>👻 Spectre</Btn>
        <Btn onClick={() => call('/airgap/sidechannel/rowhammer', { authorization_confirmed: auth, target: 'page_table', method: hhMethod })}>🔨 RowHammer</Btn>
        <Btn onClick={() => call('/airgap/sidechannel/timing', { authorization_confirmed: auth, target_url: targetUrl, oracle_type: 'rsa_decrypt', samples })}>⏱️ Timing Oracle</Btn>
      </Btns>
      <ResultBox data={res} />
    </Panel>
  )
}

// ─── THERMAL / OPTICAL ────────────────────────────────────────────────────────
function ThermalPanel() {
  const [elapsed, setElapsed]     = useState(30)
  const [kbType, setKbType]       = useState('membrane')
  const [data, setData]           = useState('PASSWORD')
  const [distCm, setDistCm]       = useState(30.0)
  const [camIp, setCamIp]         = useState('192.168.1.100')
  const [ledSrc, setLedSrc]       = useState('hdd_led')
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }

  return (
    <Panel color="#44ff88">
      <h3 style={{ color: '#44ff88', margin: '0 0 14px' }}>🌡️ Thermal + Optical Covert Channels{loading && <Spinner />}</h3>
      <Grid>
        <Field label="Délai depuis frappe (sec)"><Inp type="number" value={elapsed} onChange={e => setElapsed(+e.target.value)} /></Field>
        <Field label="Type clavier (FLIR)"><Sel value={kbType} onChange={setKbType} opts={['membrane','mechanical','laptop','chiclet']} /></Field>
        <Field label="Données à exfiltrer"><Inp value={data} onChange={e => setData(e.target.value)} /></Field>
        <Field label="Distance PC adjacent (cm)"><Inp type="number" value={distCm} onChange={e => setDistCm(+e.target.value)} /></Field>
        <Field label="IP caméra IR"><Inp value={camIp} onChange={e => setCamIp(e.target.value)} /></Field>
        <Field label="LED source"><Sel value={ledSrc} onChange={setLedSrc} opts={['hdd_led','power_led','network_led','keyboard_backlight','gpu_rgb']} /></Field>
      </Grid>
      <AuthCheck checked={auth} onChange={setAuth} />
      <Btns>
        <Btn onClick={() => apiFetch('/airgap/thermal/techniques').then(setRes).catch(e => setRes({error: e.message}))}>📋 Techniques</Btn>
        <Btn onClick={() => call('/airgap/thermal/flir-keyboard', { authorization_confirmed: auth, elapsed_sec: elapsed, keyboard_type: kbType })}>🌡️ FLIR Keyboard</Btn>
        <Btn onClick={() => call('/airgap/thermal/bitwhisper', { authorization_confirmed: auth, data, adjacent_distance_cm: distCm, mode: 'transmit' })}>🔥 BitWhisper</Btn>
        <Btn onClick={() => call('/airgap/thermal/led-exfil', { authorization_confirmed: auth, data_path: '/etc/shadow', led_source: ledSrc, modulation: 'OOK' })}>💡 LED Exfil</Btn>
        <Btn onClick={() => call('/airgap/thermal/airin-camera', { authorization_confirmed: auth, camera_ip: camIp, mode: 'exfil', data })}>📷 aIR-Jumper</Btn>
        <Btn onClick={() => call('/airgap/thermal/brightness-exfil', { authorization_confirmed: auth, data, brightness_min: 0, brightness_max: 100 })}>🔆 Brightness</Btn>
      </Btns>
      <ResultBox data={res} />
    </Panel>
  )
}

// ─── USB / BADUSB ─────────────────────────────────────────────────────────────
function USBPanel() {
  const [device, setDevice]       = useState('rubber_ducky')
  const [payloadId, setPayloadId] = useState('reverse_shell_ps')
  const [c2Ip, setC2Ip]           = useState('192.168.1.100')
  const [c2Port, setC2Port]       = useState(4444)
  const [targetOs, setTargetOs]   = useState('windows')
  const [sessionId, setSessionId] = useState('')
  const [chip, setChip]           = useState('STM32F4')
  const [iface, setIface]         = useState('SWD')
  const [jtagAtk, setJtagAtk]     = useState('readback_flash')
  const [wifiSsid, setWifiSsid]   = useState('FREE_WIFI')
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

  const call = async (path, body) => {
    setLoading(true)
    try {
      const r = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })
      setRes(r)
      if (r?.session_id) setSessionId(r.session_id)
    }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }

  return (
    <Panel color="#aa44ff">
      <h3 style={{ color: '#aa44ff', margin: '0 0 14px' }}>🔌 BadUSB — HID Injection + JTAG + O.MG{loading && <Spinner />}</h3>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#667', fontWeight: 700, marginBottom: 8 }}>— GÉNÉRATION PAYLOAD —</div>
        <Grid>
          <Field label="Dispositif"><Sel value={device} onChange={setDevice} opts={['rubber_ducky','bash_bunny','omg_cable','p4wnp1','lan_turtle','poisontap']} /></Field>
          <Field label="Payload"><Sel value={payloadId} onChange={setPayloadId} opts={['reverse_shell_ps','credential_harvest','persistence_run_key','mac_reverse_shell','linux_ssh_backdoor','wifi_pivot','exfil_shadow']} /></Field>
          <Field label="C2 IP"><Inp value={c2Ip} onChange={e => setC2Ip(e.target.value)} /></Field>
          <Field label="C2 Port"><Inp type="number" value={c2Port} onChange={e => setC2Port(+e.target.value)} /></Field>
          <Field label="OS Cible"><Sel value={targetOs} onChange={setTargetOs} opts={['windows','macos','linux']} /></Field>
          <Field label="Session ID"><Inp value={sessionId} onChange={e => setSessionId(e.target.value)} placeholder="auto-filled" /></Field>
        </Grid>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#667', fontWeight: 700, marginBottom: 8 }}>— JTAG/SWD & O.MG —</div>
        <Grid>
          <Field label="Chip cible (JTAG)"><Inp value={chip} onChange={e => setChip(e.target.value)} /></Field>
          <Field label="Interface"><Sel value={iface} onChange={setIface} opts={['SWD','JTAG','UART','I2C','SPI']} /></Field>
          <Field label="Attack JTAG"><Sel value={jtagAtk} onChange={setJtagAtk} opts={['readback_flash','readback_sram','bypass_rdp','inject_code','glitch_unlock']} /></Field>
          <Field label="WiFi SSID (O.MG)"><Inp value={wifiSsid} onChange={e => setWifiSsid(e.target.value)} /></Field>
        </Grid>
      </div>

      <AuthCheck checked={auth} onChange={setAuth} />
      <Btns>
        <Btn onClick={() => apiFetch('/airgap/usb/devices').then(setRes).catch(e => setRes({error: e.message}))}>📋 Devices</Btn>
        <Btn onClick={() => apiFetch('/airgap/usb/payloads').then(setRes).catch(e => setRes({error: e.message}))}>📦 Payloads</Btn>
        <Btn onClick={() => call('/airgap/usb/payload/generate', { authorization_confirmed: auth, device, payload_id: payloadId, c2_ip: c2Ip, c2_port: c2Port, target_os: targetOs })}>⚙️ Générer</Btn>
        <Btn onClick={() => call('/airgap/usb/deploy', { authorization_confirmed: auth, session_id: sessionId, target_description: `${targetOs} workstation` })}>🚀 Déployer</Btn>
        <Btn onClick={() => call('/airgap/usb/jtag-swd', { authorization_confirmed: auth, target_chip: chip, interface: iface, attack_type: jtagAtk })}>🔧 JTAG/SWD</Btn>
        <Btn onClick={() => call('/airgap/usb/omg-cable', { authorization_confirmed: auth, wifi_ssid: wifiSsid, c2_ip: c2Ip, geofence_enabled: false })}>🔗 O.MG Cable</Btn>
      </Btns>
      <ResultBox data={res} />
    </Panel>
  )
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function AirGapBloc4() {
  const [tab, setTab] = useState('em')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          🏔️ Air-Gap Exploitation — Bloc 4
          <span style={{ marginLeft: 12, fontSize: 12, color: '#ff4444', fontWeight: 700 }}>SIMULATION MODE</span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          TEMPEST · Van Eck · Laser Mic · MOSQUITO · Spectre/Meltdown · DPA/CPA · FLIR · BitWhisper · BadUSB · JTAG
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

      {tab === 'em'          && <EMPanel />}
      {tab === 'acoustic'    && <AcousticPanel />}
      {tab === 'sidechannel' && <SideChannelPanel />}
      {tab === 'thermal'     && <ThermalPanel />}
      {tab === 'usb'         && <USBPanel />}
    </div>
  )
}
