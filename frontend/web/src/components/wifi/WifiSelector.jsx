import React, { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

function SignalBars({ bars, active }) {
  const color = active ? '#44ff88' : bars >= 3 ? '#44aaff' : bars === 2 ? '#ffcc00' : '#ff8800'
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'flex-end' }}>
      {[1, 2, 3, 4].map(i => (
        <span key={i} style={{
          width: 4, height: 4 + i * 3,
          background: i <= bars ? color : '#2a2a2a',
          display: 'inline-block', borderRadius: 1,
          transition: 'background .3s',
        }} />
      ))}
    </span>
  )
}

function NoHwBanner({ type, error }) {
  const isBt = type === 'bluetooth'
  return (
    <div style={{
      padding: '12px 14px', background: '#1a0f00',
      border: '1px solid #ff880033', borderRadius: 8, marginBottom: 8,
    }}>
      <div style={{ color: '#ff8800', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
        ⚠️ Aucun {isBt ? 'adaptateur Bluetooth' : 'adaptateur WiFi'} détecté
      </div>
      <div style={{ color: '#886644', fontSize: 11, lineHeight: 1.7 }}>
        {error || `Cette machine est une VM sans ${isBt ? 'Bluetooth' : 'WiFi'} physique.`}<br />
        {isBt ? (
          <>→ Branchez un dongle USB Bluetooth<br />
          → Activez USB Passthrough dans VirtualBox :<br />
          &nbsp;&nbsp;<code style={{ color: '#aaa' }}>Machine → Settings → USB → Add filter → [votre dongle]</code></>
        ) : (
          <>→ Branchez un adaptateur WiFi USB (ex: <strong style={{ color: '#ccc' }}>Alfa AWUS036ACH</strong>)<br />
          → Activez USB Passthrough VirtualBox<br />
          → Ou exécutez L'Œil de Dieu directement sur un laptop avec WiFi</>
        )}
      </div>
    </div>
  )
}

export default function WifiSelector() {
  const [tab,          setTab]          = useState('wifi')
  const [networks,     setNetworks]     = useState([])
  const [status,       setStatus]       = useState(null)
  const [serverIps,    setServerIps]    = useState([])
  const [hasWifiHw,    setHasWifiHw]    = useState(null)
  const [wifiError,    setWifiError]    = useState(null)
  const [demoMode,     setDemoMode]     = useState(false)
  const [btDemoMode,   setBtDemoMode]   = useState(false)
  const [hasBtHw,      setHasBtHw]      = useState(null)
  const [btDevices,    setBtDevices]    = useState([])
  const [btError,      setBtError]      = useState(null)
  const [scanning,     setScanning]     = useState(false)
  const [btScanning,   setBtScanning]   = useState(false)
  const [connecting,   setConnecting]   = useState(false)
  const [loading,      setLoading]      = useState(false)
  const [modal,        setModal]        = useState(null)
  const [password,     setPassword]     = useState('')
  const [showPwd,      setShowPwd]      = useState(false)
  const [toast,        setToast]        = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 4000)
  }

  const loadStatus = useCallback(async () => {
    try {
      const r = await apiFetch('/wifi/system-status')
      const d = await r.json()
      setStatus(d)
      if (d.server_ips) setServerIps(d.server_ips)
      if (d.has_wifi_hw !== undefined) setHasWifiHw(d.has_wifi_hw)
    } catch {}
  }, [])

  const loadServerIps = useCallback(async () => {
    try {
      const r = await apiFetch('/wifi/server-ips')
      const d = await r.json()
      setServerIps(d.ips || [])
    } catch {}
  }, [])

  const scanWifi = useCallback(async () => {
    setScanning(true)
    setWifiError(null)
    try {
      const r = await apiFetch('/wifi/available')
      const d = await r.json()
      setNetworks(d.networks || [])
      if (d.has_wifi_hw !== undefined) setHasWifiHw(d.has_wifi_hw)
      setDemoMode(!!d.demo)
      if (d.error && !d.demo) setWifiError(d.error)
    } catch (e) {
      setWifiError('Erreur scan : ' + e.message)
    } finally {
      setScanning(false)
    }
  }, [])

  const checkBluetooth = useCallback(async () => {
    try {
      const r = await apiFetch('/wifi/bluetooth/status')
      const d = await r.json()
      setHasBtHw(d.has_bluetooth_hw)
    } catch {}
  }, [])

  const scanBluetooth = useCallback(async () => {
    setBtScanning(true)
    setBtError(null)
    setBtDevices([])
    try {
      const r = await apiFetch('/wifi/bluetooth/scan', { method: 'POST' })
      const d = await r.json()
      setHasBtHw(d.has_bluetooth_hw)
      setBtDemoMode(!!d.demo)
      if (d.error && !d.demo) setBtError(d.error)
      setBtDevices(d.devices || [])
      if (d.devices?.length > 0) showToast(`${d.devices.length} appareil(s) Bluetooth trouvé(s)`, true)
    } catch (e) {
      setBtError('Erreur scan BT : ' + e.message)
    } finally {
      setBtScanning(false)
    }
  }, [])

  useEffect(() => {
    loadStatus()
    loadServerIps()
    scanWifi()
    checkBluetooth()
  }, [])

  function openModal(net) {
    if (net.active) return
    setModal({ ssid: net.ssid, secured: net.secured })
    setPassword('')
    setShowPwd(false)
  }

  async function connect() {
    if (!modal) return
    setConnecting(true)
    try {
      const r = await apiFetch('/wifi/system-connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ssid: modal.ssid, password }),
      })
      const d = await r.json()
      if (d.status === 'connected') {
        showToast(`✅ Connecté à ${modal.ssid}${d.local_ip ? ' — IP: ' + d.local_ip : ''}`, true)
        setModal(null)
        await loadStatus()
        await scanWifi()
        await loadServerIps()
      } else {
        showToast(d.error || 'Connexion échouée', false)
      }
    } catch (e) {
      showToast('Erreur : ' + e.message, false)
    } finally {
      setConnecting(false)
    }
  }

  async function disconnect() {
    setLoading(true)
    try {
      const r = await apiFetch('/wifi/system-disconnect', { method: 'POST' })
      const d = await r.json()
      if (d.status === 'disconnected') {
        showToast('Déconnecté du WiFi', true)
        await loadStatus()
        await scanWifi()
        await loadServerIps()
      } else {
        showToast(d.error || 'Erreur déconnexion', false)
      }
    } catch (e) {
      showToast('Erreur : ' + e.message, false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={S.root}>
      {/* Toast */}
      {toast && (
        <div style={{ ...S.toast, background: toast.ok ? '#001800' : '#1a0000', borderColor: toast.ok ? '#44ff8877' : '#ff444477', color: toast.ok ? '#44ff88' : '#ff6666' }}>
          {toast.msg}
        </div>
      )}

      {/* Bannière MODE DÉMO */}
      {demoMode && (
        <div style={{ padding: '10px 14px', background: '#1a1000', border: '1px solid #f59e0b44', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 18 }}>🔮</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b', marginBottom: 2 }}>MODE DÉMO — Réseaux simulés</div>
            <div style={{ fontSize: 10, color: '#926a1a', lineHeight: 1.5 }}>
              Pas d'adaptateur WiFi USB détecté. Les réseaux ci-dessous sont simulés pour la démonstration.<br />
              Pour un scan réel → branchez un <strong style={{ color: '#ccc' }}>dongle USB WiFi</strong> et activez USB Passthrough dans VirtualBox.
            </div>
          </div>
          <span style={{ fontSize: 10, padding: '3px 8px', background: '#f59e0b22', color: '#f59e0b', borderRadius: 5, fontWeight: 700, whiteSpace: 'nowrap' }}>DÉMO</span>
        </div>
      )}

      {/* Connexion WiFi actuelle + IPs serveur */}
      <div style={S.card}>
        <div style={S.cardTitle}>📶 Connexion WiFi</div>
        {status?.connected ? (
          <div style={S.currentRow}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ color: '#44ff88', fontWeight: 700, fontSize: 15 }}>{status.ssid}</span>
                <span style={S.badge}>Connecté</span>
              </div>
              <div style={{ color: '#666', fontSize: 11, display: 'flex', gap: 12 }}>
                {status.local_ip && <span>IP : <span style={{ color: '#44aaff' }}>{status.local_ip}</span></span>}
                {status.gateway  && <span>GW : {status.gateway}</span>}
                {status.device   && <span>Interface : {status.device}</span>}
              </div>
            </div>
            <button onClick={disconnect} disabled={loading} style={S.btnDanger}>
              {loading ? '…' : 'Déconnecter'}
            </button>
          </div>
        ) : (
          <div style={{ color: '#555', fontSize: 12 }}>
            {hasWifiHw === false ? '⚠️ Aucun adaptateur WiFi physique' : 'Non connecté au WiFi'}
          </div>
        )}
      </div>

      {/* IPs serveur */}
      <div style={S.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={S.cardTitle}>🖥️ IPs du serveur</div>
          <button onClick={loadServerIps} style={S.btnSmall}>🔄</button>
        </div>
        <div style={{ fontSize: 11, color: '#555', marginBottom: 8 }}>
          Si l'app ne répond plus après un changement de réseau, ouvre cette URL :
        </div>
        {serverIps.map((item, i) => (
          <div key={i} style={S.ipRow}>
            <span style={{ color: '#555', fontSize: 11, minWidth: 40 }}>{item.iface}</span>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontFamily: 'monospace', color: '#44aaff', fontSize: 13 }}>{item.ip}</span>
                <a href={item.url_frontend} target="_blank" rel="noreferrer" style={{ color: '#44aaff', fontSize: 11 }}>App :3001 ↗</a>
                <a href={item.url_backend + '/docs'} target="_blank" rel="noreferrer" style={{ color: '#555', fontSize: 11 }}>API :8001 ↗</a>
              </div>
              <div style={{ color: '#444', fontSize: 10, marginTop: 2 }}>
                Mobile Expo : <span style={{ fontFamily: 'monospace' }}>{item.url_backend}</span>
              </div>
            </div>
            <button onClick={() => { navigator.clipboard?.writeText(item.url_frontend); showToast('URL copiée !', true) }} style={S.btnSmall}>📋</button>
          </div>
        ))}
      </div>

      {/* Onglets WiFi / Bluetooth */}
      <div style={{ display: 'flex', gap: 2, marginBottom: -1 }}>
        {[['wifi', '📶 WiFi'], ['bluetooth', '🔵 Bluetooth']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: '8px 20px', background: tab === id ? '#111' : 'transparent',
            border: `1px solid ${tab === id ? '#2a2a2a' : 'transparent'}`,
            borderBottom: tab === id ? '1px solid #111' : '1px solid #2a2a2a',
            color: tab === id ? '#ddd' : '#555',
            borderRadius: '8px 8px 0 0', cursor: 'pointer', fontSize: 12, fontWeight: tab === id ? 700 : 400,
          }}>{label}</button>
        ))}
      </div>

      {/* Panel WiFi */}
      {tab === 'wifi' && (
        <div style={{ ...S.card, borderRadius: '0 8px 8px 8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={S.cardTitle}>Réseaux à proximité</div>
            <button onClick={scanWifi} disabled={scanning} style={S.btnSmall}>
              {scanning ? '⏳ Scan…' : '🔄 Scanner'}
            </button>
          </div>

          {hasWifiHw === false && !demoMode && <NoHwBanner type="wifi" error={wifiError} />}

          {scanning ? (
            <div style={S.scanAnim}>
              <div style={S.pulse} />
              <span style={{ color: '#555', fontSize: 12, marginTop: 14 }}>Scan WiFi en cours…</span>
            </div>
          ) : networks.length === 0 ? (
            <div style={{ color: '#444', fontSize: 12, textAlign: 'center', padding: '20px 0' }}>
              {hasWifiHw ? 'Aucun réseau — clique Scanner' : 'Adaptateur WiFi requis pour scanner'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {networks.map((net, i) => (
                <div key={net.bssid || i}
                  onClick={() => !net.active && openModal(net)}
                  style={{
                    ...S.netRow,
                    background: net.active ? '#001a0a' : 'transparent',
                    borderColor: net.active ? '#44ff8833' : '#1e1e1e',
                    cursor: net.active ? 'default' : 'pointer',
                  }}>
                  <div style={S.netLeft}>
                    <SignalBars bars={net.bars} active={net.active} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{
                          color: net.active ? '#44ff88' : '#e0e0e0', fontSize: 13,
                          fontWeight: net.active ? 700 : 400,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200,
                        }}>
                          {net.ssid || <em style={{ color: '#444' }}>Réseau caché</em>}
                        </span>
                        {net.active && <span style={S.badge}>Connecté</span>}
                      </div>
                      <div style={{ color: '#444', fontSize: 10, marginTop: 1 }}>
                        {net.bssid} {net.channel && `· ch${net.channel}`} {net.freq && `· ${net.freq}`}
                      </div>
                    </div>
                  </div>
                  <div style={S.netRight}>
                    <span style={{ fontSize: 11 }}>{net.secured ? '🔒' : '🔓'}</span>
                    <span style={{ fontSize: 10, color: '#555', minWidth: 36, textAlign: 'right' }}>{net.signal}%</span>
                    <span style={{
                      fontSize: 9, padding: '1px 5px', borderRadius: 3, minWidth: 36, textAlign: 'center',
                      background: net.security === 'WPA3' ? '#44ff8822' : net.security === 'WPA2' ? '#44aaff22' : '#ff880022',
                      color: net.security === 'WPA3' ? '#44ff88' : net.security === 'WPA2' ? '#44aaff' : '#ff8800',
                    }}>{net.security}</span>
                    {!net.active && <span style={{ color: '#44aaff', fontSize: 12 }}>›</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Panel Bluetooth */}
      {tab === 'bluetooth' && (
        <div style={{ ...S.card, borderRadius: '0 8px 8px 8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={S.cardTitle}>Appareils Bluetooth à proximité</div>
            <button onClick={scanBluetooth} disabled={btScanning} style={S.btnSmall}>
              {btScanning ? '⏳ Scan…' : '🔄 Scanner (~8s)'}
            </button>
          </div>

          {hasBtHw === false && !btDemoMode && <NoHwBanner type="bluetooth" error={btError} />}
          {btDemoMode && (
            <div style={{ padding: '8px 12px', background: '#1a1000', border: '1px solid #f59e0b33', borderRadius: 6, marginBottom: 8, fontSize: 11, color: '#926a1a' }}>
              🔮 <strong style={{ color: '#f59e0b' }}>MODE DÉMO</strong> — Appareils Bluetooth simulés · Branchez un dongle USB BT pour un scan réel
            </div>
          )}

          {btScanning ? (
            <div style={S.scanAnim}>
              <div style={{ ...S.pulse, borderColor: '#aa44ff44' }} />
              <span style={{ color: '#555', fontSize: 12, marginTop: 14 }}>Scan Bluetooth en cours (~8 secondes)…</span>
            </div>
          ) : btDevices.length === 0 ? (
            <div style={{ color: '#444', fontSize: 12, textAlign: 'center', padding: '20px 0' }}>
              {hasBtHw ? 'Aucun appareil — clique Scanner' : 'Adaptateur Bluetooth requis'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {btDevices.map((dev, i) => (
                <div key={dev.address || i} style={{ ...S.netRow, borderColor: '#1e1e1e', cursor: 'default' }}>
                  <div style={S.netLeft}>
                    <span style={{ fontSize: 20 }}>🔵</span>
                    <div>
                      <div style={{ color: '#e0e0e0', fontSize: 13 }}>{dev.name}</div>
                      <div style={{ color: '#444', fontSize: 10, fontFamily: 'monospace' }}>{dev.address}</div>
                    </div>
                  </div>
                  <span style={{ fontSize: 9, padding: '1px 7px', background: '#44aaff22', color: '#44aaff', borderRadius: 3 }}>
                    {dev.type || 'BT'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal connexion WiFi */}
      {modal && (
        <div style={S.overlay} onClick={() => !connecting && setModal(null)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: 11, color: '#555', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>Se connecter à</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#44aaff', marginBottom: 20 }}>📶 {modal.ssid}</div>

            {modal.secured ? (
              <>
                <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 6 }}>Mot de passe WiFi</label>
                <div style={{ position: 'relative', marginBottom: 20 }}>
                  <input
                    autoFocus
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && !connecting && connect()}
                    placeholder="••••••••"
                    style={S.input}
                  />
                  <button onClick={() => setShowPwd(p => !p)} style={S.eyeBtn}>{showPwd ? '🙈' : '👁️'}</button>
                </div>
              </>
            ) : (
              <div style={{ color: '#ffcc00', fontSize: 12, marginBottom: 20, padding: '8px 12px', background: '#1a1200', borderRadius: 6 }}>
                🔓 Réseau ouvert — aucun mot de passe requis
              </div>
            )}

            {connecting && <div style={{ color: '#44aaff', fontSize: 12, marginBottom: 12, textAlign: 'center' }}>⏳ Connexion… (jusqu'à 30s)</div>}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setModal(null)} disabled={connecting} style={S.btnCancel}>Annuler</button>
              <button onClick={connect} disabled={connecting} style={{ ...S.btnPrimary, opacity: connecting ? .6 : 1 }}>
                {connecting ? '⏳ Connexion…' : '🔗 Se connecter'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const S = {
  root: {
    display: 'flex', flexDirection: 'column', height: '100%',
    background: '#0a0a0a', color: '#ccc',
    fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",monospace',
    overflowY: 'auto', padding: 16, gap: 12, position: 'relative',
  },
  toast: {
    position: 'fixed', top: 16, right: 16, zIndex: 9999,
    padding: '10px 18px', borderRadius: 8, border: '1px solid',
    fontSize: 13, fontWeight: 600, boxShadow: '0 4px 20px #0008',
    animation: 'fadeIn .2s', maxWidth: 340,
  },
  card: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 10, padding: '14px 16px' },
  cardTitle: { fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10, fontWeight: 600 },
  badge: { fontSize: 9, padding: '1px 6px', background: '#44ff8822', color: '#44ff88', borderRadius: 6 },
  currentRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  ipRow: {
    display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 10px',
    background: '#0d0d0d', borderRadius: 6, border: '1px solid #1a1a1a', marginBottom: 4,
  },
  netRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '9px 12px', borderRadius: 8, border: '1px solid', transition: 'background .15s',
  },
  netLeft:  { display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 },
  netRight: { display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 },
  scanAnim: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '28px 0' },
  pulse: {
    width: 38, height: 38, borderRadius: '50%',
    border: '3px solid #44aaff44', animation: 'pulse 1.5s infinite',
  },
  btnDanger: {
    padding: '6px 14px', background: 'transparent', border: '1px solid #ff444433',
    color: '#ff6666', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600, flexShrink: 0,
  },
  btnSmall: {
    padding: '4px 10px', background: '#1a1a1a', border: '1px solid #2a2a2a',
    color: '#888', borderRadius: 5, cursor: 'pointer', fontSize: 11,
  },
  overlay: {
    position: 'fixed', inset: 0, background: '#000c', zIndex: 500,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  modalBox: {
    background: '#141414', border: '1px solid #2a2a2a', borderRadius: 14,
    padding: 28, width: 340, boxShadow: '0 24px 60px #000d',
  },
  input: {
    width: '100%', boxSizing: 'border-box',
    background: '#0d0d0d', border: '1px solid #2a2a2a', color: '#fff',
    padding: '11px 42px 11px 14px', borderRadius: 8, fontSize: 14, outline: 'none',
  },
  eyeBtn: {
    position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
    background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, padding: 0,
  },
  btnCancel: {
    padding: '9px 18px', background: 'transparent', border: '1px solid #2a2a2a',
    color: '#666', borderRadius: 8, cursor: 'pointer', fontSize: 13,
  },
  btnPrimary: {
    padding: '9px 20px', background: '#44aaff', border: 'none',
    color: '#000', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 700,
  },
}
