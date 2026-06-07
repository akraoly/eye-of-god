/**
 * BLEDashboard — BLE Scanner module for L'Œil de Dieu
 * Tabs: Devices · Trackers · Logs
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../../utils/auth'

// ── Helpers ────────────────────────────────────────────────────────────────────

function relTime(iso) {
  if (!iso) return '—'
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function maskMac(mac) {
  if (!mac) return '—'
  const parts = mac.split(':')
  return parts.map((p, i) => (i >= 3 ? '**' : p)).join(':')
}

function rssiToBars(rssi) {
  if (rssi >= -55) return 4
  if (rssi >= -65) return 3
  if (rssi >= -75) return 2
  return 1
}

function RSSIBars({ rssi }) {
  const bars = rssiToBars(rssi)
  const color = bars >= 3 ? '#4ade80' : bars === 2 ? '#fbbf24' : '#f87171'
  return (
    <span title={`${rssi} dBm`} style={{ display: 'inline-flex', alignItems: 'flex-end', gap: 2, height: 14 }}>
      {[1, 2, 3, 4].map(b => (
        <span key={b} style={{
          width: 3,
          height: 3 + b * 2,
          background: b <= bars ? color : '#334155',
          borderRadius: 1,
        }} />
      ))}
    </span>
  )
}

const TYPE_ICONS = {
  phone: '📱', headphone: '🎧', smartwatch: '⌚', tracker: '🏷',
  laptop: '💻', unknown: '📡',
}

function TypeIcon({ type }) {
  return <span title={type}>{TYPE_ICONS[type] || '📡'}</span>
}

function Badge({ label, color = '#60a5fa' }) {
  return (
    <span style={{
      background: color + '20', color, border: `1px solid ${color}50`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.6rem', fontWeight: 700,
    }}>{label}</span>
  )
}

// ── CSV Export ─────────────────────────────────────────────────────────────────

function exportCSV(devices) {
  const header = ['MAC', 'Name', 'RSSI', 'Manufacturer', 'Type', 'Tracker', 'Vulns', 'Last Seen']
  const rows = devices.map(d => [
    d.mac_address, d.name || '', d.rssi, d.manufacturer || '',
    d.device_type, d.is_tracker ? 'yes' : 'no',
    (d.vulns || []).length, d.last_seen || '',
  ])
  const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `ble_devices_${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Dropdown menu ──────────────────────────────────────────────────────────────

function DeviceMenu({ device, onClose, onAction }) {
  const actions = ['Fingerprint', 'Vuln Scan', 'Track', 'Locate']
  return (
    <div style={{
      position: 'absolute', right: 0, top: 28, zIndex: 100,
      background: '#0d1f3c', border: '1px solid #1a3a5c',
      borderRadius: 8, minWidth: 150, boxShadow: '0 8px 24px #00000080',
    }}>
      {actions.map(a => (
        <button key={a} onClick={() => { onAction(device, a); onClose() }} style={{
          display: 'block', width: '100%', padding: '8px 16px', background: 'none',
          border: 'none', color: '#e0e8f0', cursor: 'pointer', textAlign: 'left',
          fontSize: '0.85rem',
        }}
          onMouseEnter={e => e.currentTarget.style.background = '#1a3a5c'}
          onMouseLeave={e => e.currentTarget.style.background = 'none'}
        >{a}</button>
      ))}
    </div>
  )
}

// ── Device Card ────────────────────────────────────────────────────────────────

function DeviceCard({ device, onAction }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <div style={{
      background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 10,
      padding: '12px 14px', position: 'relative',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <TypeIcon type={device.device_type} />
        <span style={{ fontWeight: 700, color: '#e0e8f0', fontSize: '0.9rem', flex: 1 }}>
          {device.name || maskMac(device.mac_address)}
        </span>
        <RSSIBars rssi={device.rssi || -90} />
        <span style={{ color: '#6b8aaa', fontSize: '0.75rem' }}>{device.rssi} dBm</span>

        <div ref={menuRef} style={{ position: 'relative' }}>
          <button onClick={() => setMenuOpen(o => !o)} style={{
            background: 'none', border: '1px solid #1a3a5c', borderRadius: 6,
            color: '#6b8aaa', cursor: 'pointer', padding: '2px 8px', fontSize: '1rem',
          }}>⋮</button>
          {menuOpen && <DeviceMenu device={device} onClose={() => setMenuOpen(false)} onAction={onAction} />}
        </div>
      </div>

      <div style={{ color: '#6b8aaa', fontSize: '0.72rem', fontFamily: 'monospace', marginBottom: 6 }}>
        {maskMac(device.mac_address)}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
        {device.manufacturer && <Badge label={device.manufacturer} color="#a78bfa" />}
        {(device.vulns || []).length > 0 && (
          <Badge label={`⚠ ${device.vulns.length} VULN${device.vulns.length > 1 ? 'S' : ''}`} color="#f87171" />
        )}
        {(device.gatt_services || []).length > 0 && (
          <Badge label="GATT" color="#34d399" />
        )}
        {device.simulated && <Badge label="SIM" color="#fbbf24" />}
        <span style={{ marginLeft: 'auto', color: '#3a5a7a', fontSize: '0.68rem' }}>
          {relTime(device.last_seen)}
        </span>
      </div>
    </div>
  )
}

// ── GATT Write Modal ───────────────────────────────────────────────────────────

function GATTWriteModal({ device, onClose }) {
  const [services, setServices] = useState(device.gatt_services || [])
  const [selectedService, setSelectedService] = useState(services[0]?.uuid || '')
  const [charUuid, setCharUuid] = useState('')
  const [hexData, setHexData] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!charUuid.trim() || !hexData.trim()) return
    setLoading(true)
    try {
      const res = await apiFetch(`/ble/devices/${device.mac_address}/gatt/write`, {
        method: 'POST',
        body: JSON.stringify({ service_uuid: selectedService, char_uuid: charUuid, data: hexData }),
      })
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setResult({ success: false, error: err.message })
    }
    setLoading(false)
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#00000090', zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 12,
        padding: 24, minWidth: 360, maxWidth: 480,
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ color: '#00d4ff', fontWeight: 700 }}>GATT Write — {maskMac(device.mac_address)}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b8aaa', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
        </div>

        <label style={labelStyle}>Service UUID</label>
        {services.length > 0 ? (
          <select value={selectedService} onChange={e => setSelectedService(e.target.value)} style={inputStyle}>
            {services.map(s => <option key={s.uuid} value={s.uuid}>{s.name || s.uuid}</option>)}
          </select>
        ) : (
          <input value={selectedService} onChange={e => setSelectedService(e.target.value)}
            placeholder="00001800-0000-1000-8000-00805f9b34fb" style={inputStyle} />
        )}

        <label style={labelStyle}>Characteristic UUID</label>
        <input value={charUuid} onChange={e => setCharUuid(e.target.value)}
          placeholder="00002a00-0000-1000-8000-00805f9b34fb" style={inputStyle} />

        <label style={labelStyle}>Hex Data</label>
        <input value={hexData} onChange={e => setHexData(e.target.value)}
          placeholder="0102ff" style={inputStyle} />

        <button onClick={submit} disabled={loading} style={{
          marginTop: 12, width: '100%', padding: '10px', background: loading ? '#1a3a5c' : '#00d4ff20',
          border: '1px solid #00d4ff', borderRadius: 8, color: '#00d4ff',
          cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700,
        }}>
          {loading ? 'Writing…' : 'Write Characteristic'}
        </button>

        {result && (
          <div style={{
            marginTop: 12, padding: 10, borderRadius: 8,
            background: result.success ? '#4ade8020' : '#f8717120',
            border: `1px solid ${result.success ? '#4ade80' : '#f87171'}`,
            color: result.success ? '#4ade80' : '#f87171', fontSize: '0.8rem',
          }}>
            {result.success ? 'Write successful' : `Error: ${result.error || result.stderr}`}
            {result.value && <div style={{ marginTop: 4 }}>Value: {result.value}</div>}
          </div>
        )}
      </div>
    </div>
  )
}

const labelStyle = { display: 'block', color: '#6b8aaa', fontSize: '0.75rem', marginTop: 10, marginBottom: 4 }
const inputStyle = {
  width: '100%', padding: '8px 10px', background: '#050a14',
  border: '1px solid #1a3a5c', borderRadius: 8, color: '#e0e8f0',
  fontSize: '0.8rem', boxSizing: 'border-box',
}

// ── Action result toast ────────────────────────────────────────────────────────

function ActionResult({ data, onClose }) {
  if (!data) return null
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 300,
      background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 10,
      padding: 16, maxWidth: 380, boxShadow: '0 8px 32px #00000080',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ color: '#00d4ff', fontWeight: 700, fontSize: '0.85rem' }}>{data.title}</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b8aaa', cursor: 'pointer' }}>✕</button>
      </div>
      <pre style={{ color: '#e0e8f0', fontSize: '0.75rem', margin: 0, whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>
        {JSON.stringify(data.payload, null, 2)}
      </pre>
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function BLEDashboard() {
  const [tab, setTab] = useState('devices')
  const [devices, setDevices] = useState([])
  const [trackers, setTrackers] = useState([])
  const [logs, setLogs] = useState([])
  const [scanning, setScanning] = useState(false)
  const [duration, setDuration] = useState(10)
  const [simulation, setSimulation] = useState(false)
  const [gattModal, setGATTModal] = useState(null)
  const [actionResult, setActionResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const loadDevices = useCallback(async () => {
    try {
      const res = await apiFetch('/ble/devices')
      const data = await res.json()
      setDevices(data.devices || [])
    } catch {}
  }, [])

  const loadTrackers = useCallback(async () => {
    try {
      const res = await apiFetch('/ble/trackers')
      const data = await res.json()
      setTrackers(data.trackers || [])
    } catch {}
  }, [])

  const loadLogs = useCallback(async () => {
    try {
      const res = await apiFetch('/ble/logs?limit=100')
      const data = await res.json()
      setLogs(data.logs || [])
    } catch {}
  }, [])

  useEffect(() => {
    loadDevices()
    loadTrackers()
    loadLogs()
  }, [loadDevices, loadTrackers, loadLogs])

  const doScan = async () => {
    setScanning(true)
    setError('')
    try {
      const res = await apiFetch(`/ble/scan?duration=${duration}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setDevices(data.devices || [])
      setSimulation(!!data.simulation)
      loadTrackers()
      loadLogs()
    } catch (err) {
      setError(err.message)
    }
    setScanning(false)
  }

  const handleAction = async (device, action) => {
    const mac = device.mac_address
    try {
      if (action === 'Fingerprint') {
        const res = await apiFetch(`/ble/devices/${mac}/fingerprint`, { method: 'POST' })
        const data = await res.json()
        setActionResult({ title: `Fingerprint — ${mac}`, payload: data })
        loadDevices()
      } else if (action === 'Vuln Scan') {
        const res = await apiFetch(`/ble/devices/${mac}/vuln-scan`, { method: 'POST' })
        const data = await res.json()
        setActionResult({ title: `Vuln Scan — ${mac}`, payload: data })
        loadDevices()
      } else if (action === 'Track') {
        setActionResult({ title: `Tracking ${mac}…`, payload: { status: 'running' } })
        const res = await apiFetch(`/ble/devices/${mac}/track`, { method: 'POST' })
        const data = await res.json()
        setActionResult({ title: `Track — ${mac}`, payload: data })
      } else if (action === 'Locate') {
        setActionResult({ title: `Locating ${mac}…`, payload: { status: 'running' } })
        const res = await apiFetch(`/ble/trackers/locate/${mac}`, { method: 'POST' })
        const data = await res.json()
        setActionResult({ title: `Locate — ${mac}`, payload: data })
      } else if (action === 'GATT Write') {
        setGATTModal(device)
      }
    } catch (err) {
      setActionResult({ title: `Error — ${action}`, payload: { error: err.message } })
    }
  }

  const TABS = [
    { id: 'devices', label: `Devices (${devices.length})` },
    { id: 'trackers', label: `Trackers (${trackers.length})` },
    { id: 'logs', label: `Logs (${logs.length})` },
  ]

  return (
    <div style={{ background: '#050a14', minHeight: '100%', color: '#e0e8f0', fontFamily: 'monospace' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '16px 20px',
        borderBottom: '1px solid #1a3a5c',
      }}>
        <span style={{ fontSize: '1.3rem' }}>📡</span>
        <h2 style={{ margin: 0, color: '#00d4ff', fontWeight: 800, fontSize: '1.1rem', letterSpacing: 2 }}>
          BLE SCANNER
        </h2>
        {simulation && (
          <span style={{
            background: '#fbbf2420', color: '#fbbf24', border: '1px solid #fbbf2450',
            borderRadius: 6, padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700,
          }}>SIMULATION MODE</span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={() => exportCSV(devices)}
            disabled={devices.length === 0}
            style={{
              background: '#0a1628', border: '1px solid #1a3a5c', borderRadius: 8,
              color: '#6b8aaa', cursor: 'pointer', padding: '6px 14px', fontSize: '0.78rem',
            }}
          >Export CSV</button>
        </div>
      </div>

      {/* Scan bar */}
      <div style={{
        padding: '12px 20px', borderBottom: '1px solid #1a3a5c',
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <span style={{ color: '#6b8aaa', fontSize: '0.8rem' }}>Duration:</span>
        {[5, 10, 30, 60].map(d => (
          <button key={d} onClick={() => setDuration(d)} style={{
            background: duration === d ? '#00d4ff20' : '#0a1628',
            border: `1px solid ${duration === d ? '#00d4ff' : '#1a3a5c'}`,
            borderRadius: 8, color: duration === d ? '#00d4ff' : '#6b8aaa',
            padding: '4px 14px', cursor: 'pointer', fontSize: '0.8rem',
          }}>{d}s</button>
        ))}
        <button onClick={doScan} disabled={scanning} style={{
          background: scanning ? '#1a3a5c' : '#00d4ff20', border: '1px solid #00d4ff',
          borderRadius: 8, color: '#00d4ff', padding: '6px 20px',
          cursor: scanning ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.85rem',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          {scanning && <span style={{
            width: 10, height: 10, borderRadius: '50%', background: '#00d4ff',
            animation: 'pulse 1s infinite',
          }} />}
          {scanning ? `Scanning ${duration}s…` : '⚡ SCAN'}
        </button>
        {error && <span style={{ color: '#f87171', fontSize: '0.8rem' }}>⚠ {error}</span>}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1a3a5c', padding: '0 20px' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: 'none', border: 'none', borderBottom: tab === t.id ? '2px solid #00d4ff' : '2px solid transparent',
            color: tab === t.id ? '#00d4ff' : '#6b8aaa', padding: '10px 16px',
            cursor: 'pointer', fontWeight: tab === t.id ? 700 : 400, fontSize: '0.85rem',
          }}>{t.label}</button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: 20 }}>
        {/* Devices Tab */}
        {tab === 'devices' && (
          <div>
            {devices.length === 0 && !scanning && (
              <div style={{ textAlign: 'center', color: '#3a5a7a', padding: '40px 0' }}>
                No devices found — click SCAN to discover nearby BLE devices
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {devices.map(dev => (
                <DeviceCard
                  key={dev.mac_address}
                  device={dev}
                  onAction={handleAction}
                />
              ))}
            </div>
          </div>
        )}

        {/* Trackers Tab */}
        {tab === 'trackers' && (
          <div>
            {trackers.length === 0 && (
              <div style={{ textAlign: 'center', color: '#3a5a7a', padding: '40px 0' }}>
                No trackers detected. Run a scan to find AirTags, Tiles, or SmartTags.
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {trackers.map(dev => (
                <div key={dev.mac_address} style={{
                  background: '#0a1628', border: '1px solid #f8717140', borderRadius: 10,
                  padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12,
                }}>
                  <span style={{ fontSize: '1.4rem' }}>🏷</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, color: '#e0e8f0' }}>{dev.tracker_type || 'Unknown Tracker'}</div>
                    <div style={{ color: '#6b8aaa', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                      {maskMac(dev.mac_address)}
                    </div>
                    <div style={{ color: '#6b8aaa', fontSize: '0.72rem', marginTop: 2 }}>
                      RSSI: {dev.rssi} dBm · {relTime(dev.last_seen)}
                    </div>
                  </div>
                  <RSSIBars rssi={dev.rssi || -90} />
                  <button onClick={() => handleAction(dev, 'Locate')} style={{
                    background: '#f8717120', border: '1px solid #f87171',
                    borderRadius: 8, color: '#f87171', padding: '6px 14px',
                    cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700,
                  }}>Find</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {tab === 'logs' && (
          <div>
            {logs.length === 0 && (
              <div style={{ textAlign: 'center', color: '#3a5a7a', padding: '40px 0' }}>
                No logs yet.
              </div>
            )}
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1a3a5c', color: '#6b8aaa' }}>
                  {['Action', 'MAC', 'Timestamp', 'Status'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 10px', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map(lg => (
                  <tr key={lg.id} style={{ borderBottom: '1px solid #1a3a5c20' }}>
                    <td style={{ padding: '6px 10px', color: '#00d4ff' }}>{lg.action}</td>
                    <td style={{ padding: '6px 10px', color: '#6b8aaa', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                      {maskMac(lg.mac_address)}
                    </td>
                    <td style={{ padding: '6px 10px', color: '#3a5a7a', fontSize: '0.72rem' }}>
                      {relTime(lg.timestamp)}
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <Badge
                        label={lg.success ? 'OK' : 'ERR'}
                        color={lg.success ? '#4ade80' : '#f87171'}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* GATT Write Modal */}
      {gattModal && <GATTWriteModal device={gattModal} onClose={() => setGATTModal(null)} />}

      {/* Action result panel */}
      <ActionResult data={actionResult} onClose={() => setActionResult(null)} />

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}
