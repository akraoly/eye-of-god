/**
 * CameraScanView — Découverte de caméras réseau, snapshots, PTZ, CVEs
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const STATUS_COLOR = { online: '#4ade80', offline: '#ef4444', unknown: '#fbbf24' }

function VulnBadge({ count }) {
  if (!count) return null
  const color = count >= 3 ? '#ef4444' : count >= 1 ? '#fbbf24' : '#4ade80'
  return (
    <span style={{ background: color + '20', color, border: `1px solid ${color}50`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.6rem', fontWeight: 700 }}>
      {count} CVE{count > 1 ? 's' : ''}
    </span>
  )
}

function ManufBadge({ name }) {
  if (!name) return null
  return (
    <span style={{ background: 'var(--violet-glow)', color: 'var(--violet)',
      border: '1px solid var(--violet)', borderRadius: 4, padding: '1px 6px', fontSize: '0.6rem', fontWeight: 700 }}>
      {name}
    </span>
  )
}

// ── PTZ Control Pad ───────────────────────────────────────────────────────────
function PTZPanel({ cameraIp, onClose }) {
  const [loading, setLoading] = useState(false)

  const ptzCmd = async (dir) => {
    setLoading(true)
    try {
      await apiFetch('/cameras/ptz', {
        method: 'POST',
        body: JSON.stringify({ ip: cameraIp, direction: dir }),
      })
    } catch {}
    setLoading(false)
  }

  const BTN = ({ dir, label, style = {} }) => (
    <button onClick={() => ptzCmd(dir)} disabled={loading} style={{
      width: 44, height: 44, borderRadius: 8,
      background: '#ffffff10', border: '1px solid var(--border2)',
      color: 'var(--accent)', cursor: 'pointer', fontSize: '1.1rem',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      ...style,
    }}>{label}</button>
  )

  return (
    <div style={{ background: 'var(--glass2)', border: '1px solid var(--border2)', borderRadius: 12, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1 }}>CONTRÔLE PTZ — {cameraIp}</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer', fontSize: '1rem' }}>✕</button>
      </div>
      <div className="ptz-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 44px)', gap: 6, justifyContent: 'center', marginBottom: 12 }}>
        <div />
        <BTN dir="up" label="▲" />
        <div />
        <BTN dir="left" label="◀" />
        <BTN dir="home" label="⊙" />
        <BTN dir="right" label="▶" />
        <div />
        <BTN dir="down" label="▼" />
        <div />
      </div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
        <BTN dir="zoom_in" label="🔍+" />
        <BTN dir="zoom_out" label="🔍-" />
      </div>
    </div>
  )
}

// ── Snapshot Modal ────────────────────────────────────────────────────────────
function SnapshotModal({ url, ip, onClose }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#000c', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--glass)', border: '1px solid var(--border2)',
        borderRadius: 16, padding: 20, maxWidth: '90vw', maxHeight: '90vh',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: '0.85rem' }}>📷 {ip}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
        </div>
        <img src={url} alt={ip} style={{
          maxWidth: '80vw', maxHeight: '70vh', borderRadius: 8,
          border: '1px solid var(--border)', display: 'block',
        }} />
      </div>
    </div>
  )
}

// ── Camera Card ───────────────────────────────────────────────────────────────
function CameraCard({ cam, onSnapshot, onPTZ, onCreds, onDetails }) {
  const status = cam.status || 'unknown'
  return (
    <div style={{
      background: 'var(--glass)', border: `1px solid ${STATUS_COLOR[status]}30`,
      borderRadius: 12, padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)', fontFamily: 'monospace' }}>{cam.ip}</div>
          {cam.model && <div style={{ fontSize: '0.65rem', color: 'var(--text2)', marginTop: 2 }}>{cam.model}</div>}
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[status], display: 'inline-block' }} />
          <span style={{ fontSize: '0.6rem', color: STATUS_COLOR[status] }}>{status}</span>
        </div>
      </div>

      {/* Badges */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {cam.manufacturer && <ManufBadge name={cam.manufacturer} />}
        <VulnBadge count={cam.cve_count} />
        {cam.port && <span style={{ background: '#38bdf820', color: '#38bdf8', border: '1px solid #38bdf830', borderRadius: 4, padding: '1px 6px', fontSize: '0.6rem' }}>:{cam.port}</span>}
      </div>

      {/* Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <button onClick={() => onSnapshot(cam)} style={{
          padding: '5px 0', background: '#4ade8020', border: '1px solid #4ade8040',
          borderRadius: 6, color: '#4ade80', cursor: 'pointer', fontSize: '0.68rem', fontWeight: 600,
        }}>📸 Snapshot</button>
        <button onClick={() => onCreds(cam)} style={{
          padding: '5px 0', background: '#fbbf2420', border: '1px solid #fbbf2440',
          borderRadius: 6, color: '#fbbf24', cursor: 'pointer', fontSize: '0.68rem', fontWeight: 600,
        }}>🔑 Test Creds</button>
        <button onClick={() => onPTZ(cam)} style={{
          padding: '5px 0', background: '#a78bfa20', border: '1px solid #a78bfa40',
          borderRadius: 6, color: '#a78bfa', cursor: 'pointer', fontSize: '0.68rem', fontWeight: 600,
        }}>🕹 PTZ</button>
        <button onClick={() => onDetails(cam)} style={{
          padding: '5px 0', background: '#38bdf820', border: '1px solid #38bdf840',
          borderRadius: 6, color: '#38bdf8', cursor: 'pointer', fontSize: '0.68rem', fontWeight: 600,
        }}>ℹ Détails</button>
      </div>
    </div>
  )
}

// ── Detail Panel ──────────────────────────────────────────────────────────────
function DetailPanel({ cam, onClose }) {
  const [cveData, setCveData] = useState(null)
  const [cveLoading, setCveLoading] = useState(false)

  const checkCVE = async (brand) => {
    setCveLoading(true)
    try {
      const r = await apiFetch(`/cameras/cve/${brand}?ip=${cam.ip}`)
      setCveData(await r.json())
    } catch { setCveData({ error: 'Échec' }) }
    setCveLoading(false)
  }

  return (
    <div style={{ background: 'var(--glass)', border: '1px solid var(--border2)', borderRadius: 12, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ color: 'var(--accent)', fontWeight: 700 }}>📷 {cam.ip}</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>✕</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          ['IP', cam.ip], ['Modèle', cam.model], ['Fabricant', cam.manufacturer],
          ['Firmware', cam.firmware], ['Port', cam.port],
          ['RTSP URL', cam.rtsp_url], ['Username', cam.username], ['Password', cam.password],
        ].filter(([, v]) => v).map(([k, v]) => (
          <div key={k} style={{ display: 'flex', gap: 8, fontSize: '0.75rem' }}>
            <span style={{ color: 'var(--text3)', minWidth: 80 }}>{k}</span>
            <span style={{ color: 'var(--text)', fontFamily: k === 'RTSP URL' ? 'monospace' : 'inherit', wordBreak: 'break-all' }}>{v}</span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 8 }}>CHECK CVE</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {['hikvision', 'dahua'].map(b => (
            <button key={b} onClick={() => checkCVE(b)} disabled={cveLoading} style={{
              padding: '5px 14px', background: '#ef444420', border: '1px solid #ef444450',
              borderRadius: 6, color: '#ef4444', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600, textTransform: 'capitalize',
            }}>
              {cveLoading ? '⟳' : b}
            </button>
          ))}
        </div>
        {cveData && !cveData.error && (
          <div style={{ marginTop: 10, maxHeight: 120, overflowY: 'auto' }}>
            {(cveData.cves || []).map((c, i) => (
              <div key={i} style={{ fontSize: '0.68rem', color: '#ef4444', marginBottom: 4, fontFamily: 'monospace' }}>
                {c.id}: {c.description?.slice(0, 80)}…
              </div>
            ))}
            {cveData.cves?.length === 0 && <div style={{ fontSize: '0.7rem', color: '#4ade80' }}>Aucun CVE connu</div>}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Composant principal ───────────────────────────────────────────────────────
export default function CameraScanView() {
  const [subnet,       setSubnet]       = useState('192.168.1.0/24')
  const [scanning,     setScanning]     = useState(false)
  const [progress,     setProgress]     = useState(0)
  const [cameras,      setCameras]      = useState([])
  const [error,        setError]        = useState('')
  const [ptzCam,       setPtzCam]       = useState(null)
  const [detailCam,    setDetailCam]    = useState(null)
  const [snapshot,     setSnapshot]     = useState(null)
  const [credsResults, setCredsResults] = useState({})
  const [credsLoading, setCredsLoading] = useState({})
  const progressRef = useRef(null)

  // Démarrer le scan
  const startScan = async () => {
    if (!subnet.trim()) return
    setScanning(true)
    setProgress(0)
    setError('')
    setCameras([])
    progressRef.current = setInterval(() => {
      setProgress(prev => Math.min(prev + Math.random() * 8, 90))
    }, 400)
    try {
      const r = await apiFetch('/cameras/scan', {
        method: 'POST',
        body: JSON.stringify({ subnet: subnet.trim() }),
      })
      if (!r.ok) throw new Error('Échec du scan')
      const d = await r.json()
      setCameras(d.cameras || [])
      setProgress(100)
    } catch (e) { setError(e.message) }
    clearInterval(progressRef.current)
    setScanning(false)
  }

  // Snapshot
  const takeSnapshot = async (cam) => {
    try {
      const r = await apiFetch(`/cameras/snapshot`, {
        method: 'POST', body: JSON.stringify({ ip: cam.ip, port: cam.port }),
      })
      const d = await r.json()
      if (d.url || d.data) setSnapshot({ url: d.url || `data:image/jpeg;base64,${d.data}`, ip: cam.ip })
    } catch {}
  }

  // Test credentials
  const testCreds = async (cam) => {
    setCredsLoading(prev => ({ ...prev, [cam.ip]: true }))
    try {
      const r = await apiFetch('/cameras/test-creds', {
        method: 'POST', body: JSON.stringify({ ip: cam.ip, port: cam.port }),
      })
      const d = await r.json()
      setCredsResults(prev => ({ ...prev, [cam.ip]: d }))
    } catch {}
    setCredsLoading(prev => ({ ...prev, [cam.ip]: false }))
  }

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>📷</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            CAMERA SCAN
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Découverte · Snapshots · PTZ · CVE
          </div>
        </div>
        {cameras.length > 0 && (
          <span style={{ marginLeft: 'auto', background: '#4ade8020', color: '#4ade80', border: '1px solid #4ade8040', borderRadius: 8, padding: '4px 12px', fontSize: '0.75rem', fontWeight: 700 }}>
            {cameras.length} caméra(s) trouvée(s)
          </span>
        )}
      </div>

      {/* Scan bar */}
      <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={subnet} onChange={e => setSubnet(e.target.value)}
            placeholder="192.168.1.0/24"
            style={{
              flex: 1, padding: '9px 14px', background: '#000820',
              border: '1px solid var(--border2)', borderRadius: 8,
              color: 'var(--text)', fontSize: '0.85rem', fontFamily: 'monospace',
            }}
          />
          <button onClick={startScan} disabled={scanning} style={{
            padding: '9px 24px', background: scanning ? '#ffffff10' : 'var(--accent)',
            border: 'none', borderRadius: 8, color: scanning ? 'var(--text3)' : '#000',
            cursor: 'pointer', fontWeight: 800, fontSize: '0.82rem',
          }}>
            {scanning ? '⟳ Scan…' : '🔍 Scanner'}
          </button>
        </div>
        {scanning && (
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text3)', marginBottom: 4 }}>
              <span>Scan en cours…</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div style={{ height: 4, background: '#ffffff10', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${progress}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
          </div>
        )}
        {error && (
          <div style={{ marginTop: 10, color: '#ef4444', fontSize: '0.78rem' }}>⚠ {error}</div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: ptzCam || detailCam ? '1fr 340px' : '1fr', gap: 20 }}>
        {/* Camera gallery */}
        <div>
          {cameras.length === 0 && !scanning ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: '0.85rem' }}>
              Aucune caméra découverte — Lancez un scan
            </div>
          ) : (
            <div className="camera-grid" style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16,
            }}>
              {cameras.map((cam, i) => (
                <div key={i}>
                  <CameraCard
                    cam={cam}
                    onSnapshot={takeSnapshot}
                    onPTZ={c => { setPtzCam(c); setDetailCam(null) }}
                    onCreds={testCreds}
                    onDetails={c => { setDetailCam(c); setPtzCam(null) }}
                  />
                  {credsResults[cam.ip] && (
                    <div style={{
                      marginTop: 6, padding: '6px 10px', borderRadius: 6, fontSize: '0.68rem',
                      background: credsResults[cam.ip].success ? '#4ade8020' : '#ef444420',
                      color: credsResults[cam.ip].success ? '#4ade80' : '#ef4444',
                      border: `1px solid ${credsResults[cam.ip].success ? '#4ade8040' : '#ef444440'}`,
                    }}>
                      {credsResults[cam.ip].success
                        ? `✓ Creds OK: ${credsResults[cam.ip].username}:${credsResults[cam.ip].password}`
                        : '✗ Creds incorrects'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Side panel */}
        {ptzCam && <PTZPanel cameraIp={ptzCam.ip} onClose={() => setPtzCam(null)} />}
        {detailCam && <DetailPanel cam={detailCam} onClose={() => setDetailCam(null)} />}
      </div>

      {/* Snapshot modal */}
      {snapshot && <SnapshotModal url={snapshot.url} ip={snapshot.ip} onClose={() => setSnapshot(null)} />}
    </div>
  )
}
