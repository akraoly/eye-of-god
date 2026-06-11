import React, { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

const ENC_COLOR = {
  OPN:  '#ff4444',
  WEP:  '#ff8800',
  WPA:  '#ffcc00',
  WPA2: '#44aaff',
  WPA3: '#44ff88',
}

const SIGNAL_BAR = (s) => {
  if (s >= -50) return { bars: 4, color: '#44ff88' }
  if (s >= -65) return { bars: 3, color: '#88ff44' }
  if (s >= -75) return { bars: 2, color: '#ffcc00' }
  return { bars: 1, color: '#ff8800' }
}

function SignalBars({ signal }) {
  const { bars, color } = SIGNAL_BAR(signal)
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'flex-end' }}>
      {[1, 2, 3, 4].map(i => (
        <span key={i} style={{
          width: 4, height: 4 + i * 3,
          background: i <= bars ? color : '#333',
          display: 'inline-block', borderRadius: 1,
        }} />
      ))}
    </span>
  )
}

export default function WifiDashboard() {
  const [interfaces, setInterfaces] = useState([])
  const [networks,   setNetworks]   = useState([])
  const [clients,    setClients]    = useState([])
  const [scans,      setScans]      = useState([])
  const [selected,   setSelected]   = useState(null)
  const [fingerprint,setFingerprint]= useState(null)
  const [scanning,   setScanning]   = useState(false)
  const [iface,      setIface]      = useState('wlan0')
  const [duration,   setDuration]   = useState(30)
  const [monStatus,  setMonStatus]  = useState(null)
  const [tab,        setTab]        = useState('networks')
  const [log,        setLog]        = useState([])

  const addLog = (msg, type = 'info') =>
    setLog(prev => [{ time: new Date().toLocaleTimeString(), msg, type }, ...prev].slice(0, 50))

  useEffect(() => {
    loadInterfaces()
    loadNetworks()
    loadClients()
    loadScans()
  }, [])

  async function loadInterfaces() {
    try {
      const r = await apiFetch('/wifi/interfaces')
      const d = await r.json()
      setInterfaces(d.interfaces || [])
      if (d.interfaces?.length) setIface(d.interfaces[0].name)
    } catch {}
  }

  async function loadNetworks() {
    try {
      const r = await apiFetch('/wifi/networks?limit=100')
      const d = await r.json()
      setNetworks(d.networks || [])
    } catch {}
  }

  async function loadClients() {
    try {
      const r = await apiFetch('/wifi/clients')
      const d = await r.json()
      setClients(d.clients || [])
    } catch {}
  }

  async function loadScans() {
    try {
      const r = await apiFetch('/wifi/scans')
      const d = await r.json()
      setScans(d.scans || [])
    } catch {}
  }

  async function startScan() {
    setScanning(true)
    addLog(`Scan démarré sur ${iface} (${duration}s)…`, 'info')
    try {
      const r = await apiFetch('/wifi/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: iface, duration }),
      })
      const d = await r.json()
      addLog(`Scan terminé : ${d.networks?.length || 0} réseaux, ${d.clients?.length || 0} clients`, 'success')
      await loadNetworks()
      await loadClients()
      await loadScans()
    } catch (e) {
      addLog(`Erreur scan : ${e.message}`, 'error')
    } finally {
      setScanning(false)
    }
  }

  async function toggleMonitor() {
    const endpoint = monStatus ? '/wifi/monitor/stop' : '/wifi/monitor/start'
    try {
      const r = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: iface }),
      })
      const d = await r.json()
      setMonStatus(monStatus ? null : d.monitor_interface)
      addLog(monStatus ? 'Monitor mode désactivé' : `Monitor mode activé : ${d.monitor_interface}`, 'success')
    } catch (e) {
      addLog(`Erreur monitor : ${e.message}`, 'error')
    }
  }

  async function selectNetwork(net) {
    setSelected(net)
    setFingerprint(null)
    try {
      const r = await apiFetch(`/wifi/network/${net.bssid}`)
      const d = await r.json()
      setFingerprint(d.fingerprint)
    } catch {}
  }

  const allSimulated = networks.length > 0 && networks.every(n => n.simulated)
  const hasReal = networks.some(n => !n.simulated)

  return (
    <div style={s.root}>
      {/* Bannière simulation — affiché quand aucun matériel WiFi réel */}
      {(allSimulated || (networks.length === 0 && !scanning)) && (
        <div style={{
          background: '#1a0d00', borderBottom: '1px solid #ff880044',
          padding: '6px 16px', fontSize: 11, color: '#ff8800',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>⚠️</span>
          <span>
            <strong>Aucun matériel WiFi réel détecté</strong> — les réseaux affichés sont simulés (badge SIM).
            Pour scanner de vrais réseaux : branchez un adaptateur USB WiFi et activez le USB passthrough dans VirtualBox.
          </span>
        </div>
      )}
      {hasReal && (
        <div style={{
          background: '#001a00', borderBottom: '1px solid #44ff8844',
          padding: '6px 16px', fontSize: 11, color: '#44ff88',
        }}>
          ✅ Scan réel — {networks.filter(n => !n.simulated).length} réseau(x) détecté(s) en live
        </div>
      )}

      {/* Header */}
      <div style={s.header}>
        <span style={s.title}>📶 WiFi Scanner</span>
        <div style={s.controls}>
          <select value={iface} onChange={e => setIface(e.target.value)} style={s.select}>
            {interfaces.length > 0
              ? interfaces.map(i => <option key={i.name} value={i.name}>{i.name} ({i.type})</option>)
              : <option value="wlan0">wlan0</option>
            }
          </select>
          <input
            type="number" min={10} max={120} value={duration}
            onChange={e => setDuration(+e.target.value)}
            style={{ ...s.select, width: 70 }}
          />
          <span style={{ color: '#666', fontSize: 12 }}>s</span>
          <button
            onClick={toggleMonitor}
            style={{ ...s.btn, background: monStatus ? '#ff4444' : '#444' }}
          >
            {monStatus ? `MON: ${monStatus}` : 'Monitor OFF'}
          </button>
          <button onClick={startScan} disabled={scanning} style={s.btnPrimary}>
            {scanning ? '⏳ Scan…' : '🔍 Scan'}
          </button>
        </div>
      </div>

      <div style={s.body}>
        {/* Panel gauche — liste réseaux */}
        <div style={s.left}>
          <div style={s.tabs}>
            {['networks', 'clients', 'scans', 'log'].map(t => (
              <button key={t} onClick={() => setTab(t)}
                style={{ ...s.tabBtn, ...(tab === t ? s.tabActive : {}) }}>
                {t === 'networks' ? `Réseaux (${networks.length})` :
                 t === 'clients'  ? `Clients (${clients.length})` :
                 t === 'scans'    ? `Scans (${scans.length})` : 'Log'}
              </button>
            ))}
          </div>

          <div style={s.list}>
            {tab === 'networks' && networks.map(n => (
              <div key={n.wifi_id || n.bssid}
                onClick={() => selectNetwork(n)}
                style={{ ...s.netRow, ...(selected?.bssid === n.bssid ? s.netRowActive : {}) }}>
                <div style={s.netLeft}>
                  <SignalBars signal={n.signal} />
                  <span style={s.ssid}>{n.ssid || <em style={{ color: '#666' }}>Hidden</em>}</span>
                  {n.wps_enabled && <span style={s.wpsTag}>WPS</span>}
                  {n.simulated && <span style={s.simTag}>SIM</span>}
                </div>
                <div style={s.netRight}>
                  <span style={{ ...s.enc, background: ENC_COLOR[n.encryption] || '#666' }}>{n.encryption}</span>
                  <span style={s.ch}>ch{n.channel}</span>
                  <span style={s.signal}>{n.signal} dBm</span>
                </div>
              </div>
            ))}

            {tab === 'clients' && clients.map((c, i) => (
              <div key={i} style={s.netRow}>
                <div style={s.netLeft}>
                  <span style={{ fontSize: 10, color: '#888', fontFamily: 'monospace' }}>{c.mac}</span>
                  {c.vendor && <span style={s.vendorTag}>{c.vendor}</span>}
                </div>
                <div style={s.netRight}>
                  <span style={s.signal}>{c.signal} dBm</span>
                  {c.bssid && <span style={{ fontSize: 10, color: '#666' }}>→ {c.bssid?.slice(0,8)}</span>}
                </div>
              </div>
            ))}

            {tab === 'scans' && scans.map(sc => (
              <div key={sc.scan_id} style={{ ...s.netRow, cursor: 'default' }}>
                <div>
                  <div style={{ fontSize: 12, color: '#ccc' }}>{sc.interface} — {sc.duration}s</div>
                  <div style={{ fontSize: 10, color: '#666' }}>{sc.started_at?.slice(0,19)}</div>
                </div>
                <div style={s.netRight}>
                  <span style={{ color: '#44ff88', fontSize: 11 }}>
                    {sc.networks_found} réseaux / {sc.clients_found} clients
                  </span>
                </div>
              </div>
            ))}

            {tab === 'log' && log.map((l, i) => (
              <div key={i} style={{ padding: '4px 8px', borderBottom: '1px solid #1a1a1a', fontSize: 11 }}>
                <span style={{ color: '#555' }}>{l.time} </span>
                <span style={{ color: l.type === 'error' ? '#ff4444' : l.type === 'success' ? '#44ff88' : '#ccc' }}>
                  {l.msg}
                </span>
              </div>
            ))}

            {((tab === 'networks' && networks.length === 0) ||
              (tab === 'clients'  && clients.length === 0)) && !scanning && (
              <div style={s.empty}>Lance un scan pour découvrir les réseaux</div>
            )}
          </div>
        </div>

        {/* Panel droit — détails AP sélectionné */}
        <div style={s.right}>
          {selected ? (
            <div style={s.detail}>
              <div style={s.detailHeader}>
                <span style={s.detailSSID}>{selected.ssid || 'Hidden Network'}</span>
                <span style={{ ...s.enc, background: ENC_COLOR[selected.encryption] || '#666', fontSize: 13 }}>
                  {selected.encryption}
                </span>
              </div>

              <div style={s.infoGrid}>
                {[
                  ['BSSID', selected.bssid],
                  ['Canal', `${selected.channel} (${selected.frequency || '?'} GHz)`],
                  ['Signal', `${selected.signal} dBm`],
                  ['Auth', selected.auth || 'PSK'],
                  ['Chiffrement', selected.cipher || '?'],
                  ['Vendor', selected.vendor || 'Unknown'],
                  ['WPS', selected.wps_enabled ? '✅ Activé' : '❌ Désactivé'],
                  ['Clients', (selected.clients || []).length],
                  ['Beacons', selected.beacon_count || 0],
                  ['Simulé', selected.simulated ? 'Oui' : 'Non'],
                ].map(([k, v]) => (
                  <div key={k} style={s.infoRow}>
                    <span style={s.infoKey}>{k}</span>
                    <span style={s.infoVal}>{v}</span>
                  </div>
                ))}
              </div>

              {fingerprint && (
                <div style={s.fpSection}>
                  <div style={s.sectionTitle}>🔍 Fingerprint</div>
                  <div style={s.infoGrid}>
                    {[
                      ['Modèle', fingerprint.model],
                      ['Firmware', fingerprint.firmware],
                    ].map(([k, v]) => (
                      <div key={k} style={s.infoRow}>
                        <span style={s.infoKey}>{k}</span>
                        <span style={s.infoVal}>{v}</span>
                      </div>
                    ))}
                  </div>
                  {fingerprint.default_creds?.length > 0 && (
                    <>
                      <div style={{ fontSize: 11, color: '#ff8800', margin: '8px 0 4px' }}>Creds par défaut :</div>
                      {fingerprint.default_creds.map((c, i) => (
                        <div key={i} style={{ fontSize: 11, fontFamily: 'monospace', color: '#ccc', padding: '2px 0' }}>
                          {c.user} / {c.pass || '(vide)'}
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}

              <div style={s.actionRow}>
                <button
                  style={s.actionBtn}
                  onClick={() => window.dispatchEvent(new CustomEvent('wifi-attack', { detail: selected }))}
                >
                  ⚔️ Attaquer
                </button>
              </div>
            </div>
          ) : (
            <div style={s.placeholder}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📶</div>
              <div style={{ color: '#555' }}>Sélectionne un réseau</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const s = {
  root:      { display: 'flex', flexDirection: 'column', height: '100%', background: '#0d0d0d', color: '#ccc', fontFamily: 'monospace' },
  header:    { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid #222', background: '#111' },
  title:     { fontSize: 16, fontWeight: 700, color: '#44aaff' },
  controls:  { display: 'flex', gap: 8, alignItems: 'center' },
  select:    { background: '#1a1a1a', border: '1px solid #333', color: '#ccc', padding: '4px 8px', borderRadius: 4, fontSize: 12 },
  btn:       { padding: '5px 12px', borderRadius: 4, border: 'none', cursor: 'pointer', color: '#ccc', fontSize: 12 },
  btnPrimary:{ padding: '5px 14px', borderRadius: 4, border: 'none', cursor: 'pointer', background: '#44aaff', color: '#000', fontWeight: 700, fontSize: 12 },
  body:      { display: 'flex', flex: 1, overflow: 'hidden' },
  left:      { width: '50%', borderRight: '1px solid #222', display: 'flex', flexDirection: 'column' },
  tabs:      { display: 'flex', borderBottom: '1px solid #222' },
  tabBtn:    { flex: 1, padding: '6px 4px', background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 11 },
  tabActive: { color: '#44aaff', borderBottom: '2px solid #44aaff' },
  list:      { flex: 1, overflowY: 'auto' },
  netRow:    { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 12px', borderBottom: '1px solid #1a1a1a', cursor: 'pointer', transition: 'background .15s' },
  netRowActive:{ background: '#1a2233' },
  netLeft:   { display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 },
  netRight:  { display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 },
  ssid:      { fontSize: 12, color: '#ddd', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 },
  enc:       { fontSize: 9, padding: '1px 5px', borderRadius: 3, color: '#000', fontWeight: 700 },
  ch:        { fontSize: 10, color: '#666' },
  signal:    { fontSize: 10, color: '#888' },
  wpsTag:    { fontSize: 9, padding: '1px 4px', background: '#ff880033', color: '#ff8800', borderRadius: 3 },
  simTag:    { fontSize: 9, padding: '1px 4px', background: '#66448833', color: '#9966cc', borderRadius: 3 },
  vendorTag: { fontSize: 10, color: '#888' },
  empty:     { padding: 24, color: '#444', textAlign: 'center', fontSize: 12 },
  right:         { flex: 1, overflow: 'auto' },
  detail:        { padding: 16 },
  detailHeader:  { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  detailSSID:    { fontSize: 16, fontWeight: 700, color: '#44aaff' },
  infoGrid:      { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 },
  infoRow:       { display: 'flex', gap: 8, padding: '3px 0' },
  infoKey:       { fontSize: 11, color: '#666', minWidth: 80 },
  infoVal:       { fontSize: 11, color: '#ccc', fontFamily: 'monospace' },
  fpSection:     { marginTop: 16, padding: 10, background: '#111', borderRadius: 6 },
  sectionTitle:  { fontSize: 12, color: '#ff8800', marginBottom: 8, fontWeight: 700 },
  actionRow:     { marginTop: 16, display: 'flex', gap: 8 },
  actionBtn:     { padding: '7px 16px', background: '#1a2233', border: '1px solid #44aaff', color: '#44aaff', borderRadius: 4, cursor: 'pointer', fontSize: 12 },
  placeholder:   { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#555' },
}
