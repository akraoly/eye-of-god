import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'kernel',   label: '🧬 Kernel',   color: '#ff4444' },
  { id: 'browser',  label: '🌐 Browser',  color: '#ff8800' },
  { id: 'mobile',   label: '📱 Mobile',   color: '#ffcc00' },
  { id: 'protocol', label: '🔌 Protocole',color: '#44ccff' },
  { id: 'pipeline', label: '⚙️ Pipeline', color: '#aa44ff' },
]

const SEVERITY_COLOR = { CRITICAL: '#ff2222', HIGH: '#ff8800', MEDIUM: '#ffcc00', LOW: '#44ff88' }

function Badge({ text, color }) {
  return (
    <span style={{
      background: color + '22', color, border: `1px solid ${color}55`,
      borderRadius: 4, padding: '1px 7px', fontSize: 11, fontWeight: 700,
    }}>{text}</span>
  )
}

function ResultBox({ data }) {
  if (!data) return null
  return (
    <pre style={{
      background: '#0a0f1a', color: '#7affb2', border: '1px solid #1a3a1a',
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 280, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function Spinner() {
  return <span style={{ color: '#44ccff', marginLeft: 8 }}>⏳</span>
}

// ─── KERNEL FUZZER ────────────────────────────────────────────────────────────
function KernelPanel() {
  const [target, setTarget]     = useState('linux')
  const [subsystem, setSub]     = useState('net/tcp')
  const [duration, setDuration] = useState(60)
  const [workers, setWorkers]   = useState(4)
  const [auth, setAuth]         = useState(false)
  const [jobId, setJobId]       = useState('')
  const [crashId, setCrashId]   = useState('')
  const [res, setRes]           = useState(null)
  const [loading, setLoading]   = useState(false)

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

  const SUBSYSTEMS = {
    linux: ['net/tcp','net/udp','fs/ext4','fs/btrfs','mm/slab','drivers/usb','security/bpf','ipc/shm'],
    windows: ['win32k.sys','ntfs.sys','tcpip.sys','dxgkrnl.sys'],
    macos: ['xnu/bsd','xnu/mach','iokit/usb'],
    ebpf: ['bpf/verifier','bpf/jit'],
    driver: ['pci','usb','net'],
  }

  return (
    <div className="bloc3-panel">
      <h3 style={{ color: '#ff4444', marginBottom: 12 }}>🧬 Kernel Fuzzer — Syzkaller / kAFL</h3>
      <div className="bloc3-grid2">
        <div>
          <label>Target OS</label>
          <select value={target} onChange={e => { setTarget(e.target.value); setSub('') }}>
            {['linux','windows','macos','ebpf','driver'].map(t => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label>Subsystem</label>
          <select value={subsystem} onChange={e => setSub(e.target.value)}>
            {(SUBSYSTEMS[target] || []).map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label>Durée (min)</label>
          <input type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={5} max={1440} />
        </div>
        <div>
          <label>Workers</label>
          <input type="number" value={workers} onChange={e => setWorkers(+e.target.value)} min={1} max={32} />
        </div>
      </div>
      <label className="auth-check">
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        &nbsp;authorization_confirmed — Pentest autorisé
      </label>
      <div className="bloc3-btns">
        <button onClick={() => call('/zeroday/kernel/start', { authorization_confirmed: auth, target, subsystem, duration_min: duration, workers })}>
          ▶ Start{loading && <Spinner />}
        </button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) call(`/zeroday/kernel/stop/${id}`, { authorization_confirmed: auth }) }}>■ Stop</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/kernel/status/${id}`) }}>📊 Status</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/kernel/crashes/${id}`) }}>💥 Crashes</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/kernel/coverage/${id}`) }}>📈 Coverage</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input placeholder="job_id" value={jobId} onChange={e => setJobId(e.target.value)} style={{ flex: 1 }} />
        <input placeholder="crash_id" value={crashId} onChange={e => setCrashId(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { if(crashId && (res?.job_id || jobId)) call('/zeroday/kernel/triage', { authorization_confirmed: auth, crash_id: crashId, job_id: res?.job_id || jobId }) }}>
          🔬 Triage
        </button>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── BROWSER FUZZER ───────────────────────────────────────────────────────────
function BrowserPanel() {
  const [browser, setBrowser]   = useState('chrome')
  const [module, setModule]     = useState('dom')
  const [fuzzer, setFuzzer]     = useState('domato')
  const [duration, setDuration] = useState(120)
  const [workers, setWorkers]   = useState(2)
  const [auth, setAuth]         = useState(false)
  const [jobId, setJobId]       = useState('')
  const [crashId, setCrashId]   = useState('')
  const [res, setRes]           = useState(null)
  const [loading, setLoading]   = useState(false)

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

  return (
    <div className="bloc3-panel">
      <h3 style={{ color: '#ff8800', marginBottom: 12 }}>🌐 Browser Fuzzer — Domato / Fuzzilli</h3>
      <div className="bloc3-grid2">
        <div>
          <label>Browser</label>
          <select value={browser} onChange={e => setBrowser(e.target.value)}>
            {['chrome','firefox','safari','edge'].map(b => <option key={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label>Module</label>
          <select value={module} onChange={e => setModule(e.target.value)}>
            {['dom','js_engine','webgl','webaudio','webrtc','wasm','css'].map(m => <option key={m}>{m}</option>)}
          </select>
        </div>
        <div>
          <label>Fuzzer</label>
          <select value={fuzzer} onChange={e => setFuzzer(e.target.value)}>
            {['domato','jsfunfuzz','fuzzilli','libfuzzer'].map(f => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div>
          <label>Durée (min)</label>
          <input type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={10} max={1440} />
        </div>
      </div>
      <label className="auth-check">
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        &nbsp;authorization_confirmed
      </label>
      <div className="bloc3-btns">
        <button onClick={() => call('/zeroday/browser/start', { authorization_confirmed: auth, browser, module, fuzzer, duration_min: duration, workers })}>
          ▶ Start{loading && <Spinner />}
        </button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) call(`/zeroday/browser/stop/${id}`, { authorization_confirmed: auth }) }}>■ Stop</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/browser/status/${id}`) }}>📊 Status</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/browser/crashes/${id}`) }}>💥 Crashes</button>
        <button onClick={() => get(`/zeroday/browser/cves/${browser}`)}>📋 CVEs</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input placeholder="job_id" value={jobId} onChange={e => setJobId(e.target.value)} style={{ flex: 1 }} />
        <input placeholder="crash_id" value={crashId} onChange={e => setCrashId(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/browser/triage', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>🔬 Triage</button>
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/browser/poc/generate', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>🧪 PoC</button>
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/browser/exploit/generate', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>💀 Exploit</button>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── MOBILE FUZZER ────────────────────────────────────────────────────────────
function MobilePanel() {
  const [target, setTarget]     = useState('ios_iokit')
  const [duration, setDuration] = useState(60)
  const [iters, setIters]       = useState(1000000)
  const [auth, setAuth]         = useState(false)
  const [jobId, setJobId]       = useState('')
  const [crashId, setCrashId]   = useState('')
  const [res, setRes]           = useState(null)
  const [loading, setLoading]   = useState(false)

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

  const TARGETS = ['ios_iokit','ios_xpc','ios_webkit','ios_mediacodec','android_binder','android_media','android_opengl','baseband_at','baseband_nas']

  return (
    <div className="bloc3-panel">
      <h3 style={{ color: '#ffcc00', marginBottom: 12 }}>📱 Mobile Fuzzer — IOKit / Binder / Baseband</h3>
      <div className="bloc3-grid2">
        <div>
          <label>Target</label>
          <select value={target} onChange={e => setTarget(e.target.value)}>
            {TARGETS.map(t => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label>Durée (min)</label>
          <input type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={10} />
        </div>
        <div>
          <label>Itérations</label>
          <input type="number" value={iters} onChange={e => setIters(+e.target.value)} min={10000} />
        </div>
      </div>
      <label className="auth-check">
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        &nbsp;authorization_confirmed
      </label>
      <div className="bloc3-btns">
        <button onClick={() => get('/zeroday/mobile/fuzz/targets')}>📋 Targets</button>
        <button onClick={() => call('/zeroday/mobile/fuzz/start', { authorization_confirmed: auth, target, duration_min: duration, iterations: iters })}>
          ▶ Start{loading && <Spinner />}
        </button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) call(`/zeroday/mobile/fuzz/stop/${id}`, { authorization_confirmed: auth }) }}>■ Stop</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/mobile/fuzz/crashes/${id}`) }}>💥 Crashes</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input placeholder="job_id" value={jobId} onChange={e => setJobId(e.target.value)} style={{ flex: 1 }} />
        <input placeholder="crash_id" value={crashId} onChange={e => setCrashId(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/mobile/fuzz/triage', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>🔬 Triage</button>
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/mobile/fuzz/poc/generate', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>🧪 PoC</button>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── PROTOCOL FUZZER ─────────────────────────────────────────────────────────
function ProtocolPanel() {
  const [targetIp, setTargetIp] = useState('127.0.0.1')
  const [protocol, setProtocol] = useState('http2')
  const [port, setPort]         = useState(0)
  const [duration, setDuration] = useState(30)
  const [mode, setMode]         = useState('mutation')
  const [field, setField]       = useState('length')
  const [auth, setAuth]         = useState(false)
  const [jobId, setJobId]       = useState('')
  const [crashId, setCrashId]   = useState('')
  const [res, setRes]           = useState(null)
  const [loading, setLoading]   = useState(false)

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

  const PROTOCOLS = ['dns','http2','quic','tls13','smb','ssh','wifi_80211','bluetooth_l2cap','mqtt','modbus','dnp3']

  return (
    <div className="bloc3-panel">
      <h3 style={{ color: '#44ccff', marginBottom: 12 }}>🔌 Protocol Fuzzer — boofuzz / Scapy</h3>
      <div className="bloc3-grid2">
        <div>
          <label>Target IP</label>
          <input value={targetIp} onChange={e => setTargetIp(e.target.value)} placeholder="192.168.1.1" />
        </div>
        <div>
          <label>Protocole</label>
          <select value={protocol} onChange={e => setProtocol(e.target.value)}>
            {PROTOCOLS.map(p => <option key={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label>Port (0 = auto)</label>
          <input type="number" value={port} onChange={e => setPort(+e.target.value)} min={0} max={65535} />
        </div>
        <div>
          <label>Mode</label>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            {['mutation','generation','replay','smart'].map(m => <option key={m}>{m}</option>)}
          </select>
        </div>
        <div>
          <label>Durée (min)</label>
          <input type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={5} />
        </div>
        <div>
          <label>Field (paquet)</label>
          <input value={field} onChange={e => setField(e.target.value)} placeholder="length" />
        </div>
      </div>
      <label className="auth-check">
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        &nbsp;authorization_confirmed
      </label>
      <div className="bloc3-btns">
        <button onClick={() => get('/zeroday/protocol/list')}>📋 Protocoles</button>
        <button onClick={() => call('/zeroday/protocol/start', { authorization_confirmed: auth, target_ip: targetIp, protocol, port, duration_min: duration, mode })}>
          ▶ Start{loading && <Spinner />}
        </button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) call(`/zeroday/protocol/stop/${id}`, { authorization_confirmed: auth }) }}>■ Stop</button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/protocol/crashes/${id}`) }}>💥 Crashes</button>
        <button onClick={() => call('/zeroday/protocol/malformed-packet', { authorization_confirmed: auth, protocol, field })}>🔧 Paquet malformé</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input placeholder="job_id" value={jobId} onChange={e => setJobId(e.target.value)} style={{ flex: 1 }} />
        <input placeholder="crash_id" value={crashId} onChange={e => setCrashId(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { const jid = res?.job_id || jobId; if(crashId && jid) call('/zeroday/protocol/triage', { authorization_confirmed: auth, crash_id: crashId, job_id: jid }) }}>🔬 Triage</button>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── EXPLOIT PIPELINE ────────────────────────────────────────────────────────
function PipelinePanel() {
  const [crashId, setCrashId]     = useState('')
  const [crashType, setCrashType] = useState('UAF')
  const [platform, setPlatform]   = useState('linux_x64')
  const [binary, setBinary]       = useState('/usr/bin/target')
  const [exploitId, setExploitId] = useState('')
  const [targetIp, setTargetIp]   = useState('127.0.0.1')
  const [c2Ip, setC2Ip]           = useState('127.0.0.1')
  const [c2Port, setC2Port]       = useState(4444)
  const [c2Fw, setC2Fw]           = useState('metasploit')
  const [jobId, setJobId]         = useState('')
  const [auth, setAuth]           = useState(false)
  const [res, setRes]             = useState(null)
  const [loading, setLoading]     = useState(false)

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

  const CRASH_TYPES = ['UAF','OOB_WRITE','OOB_READ','STACK_OVERFLOW','DOUBLE_FREE','RACE_CONDITION','TYPE_CONFUSION','FORMAT_STRING']
  const PLATFORMS   = ['linux_x64','linux_arm64','windows_x64','windows_x86','macos_x64','android_arm64','ios_arm64']

  return (
    <div className="bloc3-panel">
      <h3 style={{ color: '#aa44ff', marginBottom: 12 }}>⚙️ Exploit Pipeline — ROP + pwntools + C2</h3>

      <div style={{ marginBottom: 12 }}>
        <h4 style={{ color: '#aa44ff88', fontSize: 12, marginBottom: 8 }}>ÉTAPE 1 — Crash → Exploit</h4>
        <div className="bloc3-grid2">
          <div>
            <label>Crash ID</label>
            <input value={crashId} onChange={e => setCrashId(e.target.value)} placeholder="uuid du crash" />
          </div>
          <div>
            <label>Crash Type</label>
            <select value={crashType} onChange={e => setCrashType(e.target.value)}>
              {CRASH_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label>Plateforme</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)}>
              {PLATFORMS.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label>Binaire cible</label>
            <input value={binary} onChange={e => setBinary(e.target.value)} placeholder="/usr/bin/target" />
          </div>
        </div>
      </div>

      <label className="auth-check">
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        &nbsp;authorization_confirmed — Pentest autorisé
      </label>

      <div className="bloc3-btns">
        <button onClick={() => call('/zeroday/pipeline/run', { authorization_confirmed: auth, crash_id: crashId, crash_type: crashType, platform, target_binary: binary })}>
          🚀 Run Pipeline{loading && <Spinner />}
        </button>
        <button onClick={() => { const id = res?.job_id || jobId; if(id) get(`/zeroday/pipeline/status/${id}`) }}>📊 Status</button>
        <button onClick={() => get('/zeroday/pipeline/exploits')}>📦 DB Exploits</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <h4 style={{ color: '#aa44ff88', fontSize: 12, marginBottom: 8 }}>ÉTAPE 2 — Test & Deploy</h4>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <input placeholder="exploit_id" value={exploitId} onChange={e => setExploitId(e.target.value)} style={{ flex: 1, minWidth: 180 }} />
          <input placeholder="target IP" value={targetIp} onChange={e => setTargetIp(e.target.value)} style={{ flex: 1, minWidth: 120 }} />
          <input placeholder="C2 IP" value={c2Ip} onChange={e => setC2Ip(e.target.value)} style={{ flex: 1, minWidth: 120 }} />
          <input type="number" placeholder="C2 Port" value={c2Port} onChange={e => setC2Port(+e.target.value)} style={{ width: 90 }} />
          <select value={c2Fw} onChange={e => setC2Fw(e.target.value)}>
            {['metasploit','cobalt_strike','sliver'].map(f => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div className="bloc3-btns">
          <button onClick={() => call(`/zeroday/pipeline/sandbox-test`, { authorization_confirmed: auth, exploit_id: exploitId || res?.exploit_id })}>
            🔒 Sandbox Test
          </button>
          <button onClick={() => { const eid = exploitId || res?.exploit_id; if(eid) call(`/zeroday/pipeline/exploit/deploy/${eid}`, { authorization_confirmed: auth, target_ip: targetIp, c2_ip: c2Ip, c2_port: c2Port }) }}>
            🎯 Deploy
          </button>
          <button onClick={() => { const eid = exploitId || res?.exploit_id; if(eid) call(`/zeroday/pipeline/c2/add/${eid}`, { authorization_confirmed: auth, c2_framework: c2Fw }) }}>
            📡 Add to C2
          </button>
        </div>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ─── MAIN COMPONENT ──────────────────────────────────────────────────────────
export default function ZeroDayBloc3() {
  const [tab, setTab] = useState('kernel')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          🔬 Zero-Day Industriel — Bloc 3
          <span style={{ marginLeft: 12, fontSize: 12, color: '#ff4444', fontWeight: 700 }}>
            SIMULATION MODE
          </span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          Kernel Fuzzer (Syzkaller) · Browser Fuzzer (Domato/Fuzzilli) · Mobile Fuzzer · Protocol Fuzzer · Exploit Pipeline
        </p>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              border: `1px solid ${tab === t.id ? t.color : '#1a2a3a'}`,
              background: tab === t.id ? t.color + '22' : '#0a1520',
              color: tab === t.id ? t.color : '#667',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: tab === t.id ? 700 : 400,
              transition: 'all 0.15s',
            }}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'kernel'   && <KernelPanel />}
      {tab === 'browser'  && <BrowserPanel />}
      {tab === 'mobile'   && <MobilePanel />}
      {tab === 'protocol' && <ProtocolPanel />}
      {tab === 'pipeline' && <PipelinePanel />}

      <style>{`
        .bloc3-panel {
          background: #0a1520;
          border: 1px solid #1a2a3a;
          border-radius: 12px;
          padding: 20px;
        }
        .bloc3-panel h3 { margin-top: 0; font-size: 15px; }
        .bloc3-panel label { display: block; font-size: 11px; color: #667; margin-bottom: 4px; }
        .bloc3-panel input, .bloc3-panel select {
          width: 100%; background: #060b14; border: 1px solid #1a2a3a;
          color: #ccc; padding: 6px 10px; border-radius: 6px; font-size: 12px;
          box-sizing: border-box;
        }
        .bloc3-grid2 {
          display: grid; grid-template-columns: 1fr 1fr;
          gap: 12px; margin-bottom: 12px;
        }
        .bloc3-btns { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
        .bloc3-btns button {
          background: #1a2a3a; border: 1px solid #2a3a4a;
          color: #aaccff; padding: 7px 14px; border-radius: 6px;
          cursor: pointer; font-size: 12px; font-weight: 600;
        }
        .bloc3-btns button:hover { background: #2a3a4a; border-color: #4a6a8a; }
        .auth-check {
          display: flex !important; align-items: center;
          color: #ff4444 !important; font-size: 12px !important;
          margin-bottom: 10px; cursor: pointer;
        }
      `}</style>
    </div>
  )
}
