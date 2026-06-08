import { useState } from 'react'
import { apiFetch } from '../utils/auth'

export default function GPSSpoofing() {
  const [tab, setTab] = useState('hardware')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [hardware, setHardware] = useState(null)
  const [transmitting, setTransmitting] = useState(false)
  const [signalFile, setSignalFile] = useState('')

  // Signal params
  const [lat, setLat] = useState('48.8566')
  const [lon, setLon] = useState('2.3522')
  const [alt, setAlt] = useState('50')
  const [duration, setDuration] = useState('60')
  const [gain, setGain] = useState('40')

  // Waypoints
  const [waypoints, setWaypoints] = useState([
    { lat: 48.8566, lon: 2.3522, alt: 100 },
    { lat: 48.8600, lon: 2.3600, alt: 150 },
    { lat: 48.8650, lon: 2.3700, alt: 200 },
  ])
  const [speed, setSpeed] = useState('50')

  // Drone spoof
  const [droneIp, setDroneIp] = useState('192.168.1.1')
  const [droneLat, setDroneLat] = useState('48.9000')
  const [droneLon, setDroneLon] = useState('2.4000')

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const checkHW = () => act(async () => { const r = await apiFetch('/gps/hardware'); setHardware(r); setResult(r) })

  const generateSignal = () => act(async () => {
    const r = await apiFetch('/gps/signal/generate', { method: 'POST', body: { target_lat: parseFloat(lat), target_lon: parseFloat(lon), altitude: parseFloat(alt), duration: parseInt(duration), authorization_confirmed: auth } })
    setResult(r); if (r.signal_file) setSignalFile(r.signal_file)
  })

  const generateWaypoints = () => act(async () => {
    const r = await apiFetch('/gps/signal/waypoints', { method: 'POST', body: { waypoints, speed_kmh: parseInt(speed), authorization_confirmed: auth } })
    setResult(r); if (r.signal_file) setSignalFile(r.signal_file)
  })

  const startTransmit = () => act(async () => {
    const r = await apiFetch('/gps/transmit/start', { method: 'POST', body: { signal_file: signalFile, frequency: 1575420000.0, gain: parseInt(gain), duration: parseInt(duration), authorization_confirmed: auth } })
    setResult(r); if (r.transmitting) setTransmitting(true)
  })

  const stopTransmit = () => act(async () => {
    const r = await apiFetch('/gps/transmit/stop', { method: 'POST', body: { authorization_confirmed: auth } })
    setResult(r); setTransmitting(false)
  })

  const spoofDrone = () => act(async () => {
    const r = await apiFetch('/gps/drone/spoof', { method: 'POST', body: { target_drone_ip: droneIp, fake_lat: parseFloat(droneLat), fake_lon: parseFloat(droneLon), authorization_confirmed: auth } })
    setResult(r)
  })

  const jamGPS = () => act(async () => {
    const r = await apiFetch('/gps/jam', { method: 'POST', body: { frequency: 1575420000.0, duration: 10, authorization_confirmed: auth } })
    setResult(r)
  })

  const addWaypoint = () => setWaypoints(prev => [...prev, { lat: 48.8600, lon: 2.3600, alt: 100 }])
  const removeWaypoint = (i) => setWaypoints(prev => prev.filter((_, idx) => idx !== i))
  const updateWP = (i, field, val) => setWaypoints(prev => prev.map((w, idx) => idx === i ? { ...w, [field]: parseFloat(val) || 0 } : w))

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>🛰 GPS Spoofing</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>HackRF + gps-sdr-sim · Signal L1 1575.42 MHz · Waypoints · Drone spoof</p>
      <div style={{ background: '#1a0a0a', border: '1px solid #5d2e2e', borderRadius: 4, padding: '6px 12px', marginBottom: 16, fontSize: 12, color: '#ff7070' }}>
        ⚠ ILLÉGAL sans cage de Faraday et autorisation. Perturber le GPS est un délit grave.
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Laboratoire blindé, autorisation légale confirmée</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {['hardware', 'signal', 'waypoints', 'drone', 'jam'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
        {transmitting && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff4444', animation: 'pulse 1s infinite' }} />
            <span style={{ fontSize: 12, color: '#ff4444' }}>TRANSMISSION EN COURS</span>
            <button onClick={stopTransmit} style={{ padding: '4px 12px', background: '#3e1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>■ Stop</button>
          </div>
        )}
      </div>

      {tab === 'hardware' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Hardware SDR</h4>
            <button onClick={checkHW} disabled={loading} style={{ padding: '8px 16px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', marginBottom: 16 }}>Vérifier Hardware</button>
            {hardware && (
              <div>
                {[
                  { label: 'Hardware', value: hardware.sdr_hardware, ok: hardware.hardware_ready },
                  { label: 'gps-sdr-sim', value: hardware.tools?.gps_sdr_sim ? '✅ Installé' : '❌ Manquant', ok: hardware.tools?.gps_sdr_sim },
                  { label: 'hackrf_transfer', value: hardware.tools?.hackrf_transfer ? '✅ Installé' : '❌ Manquant', ok: hardware.tools?.hackrf_transfer },
                  { label: 'Blindage actif', value: hardware.shielding_active ? 'OUI' : 'NON', ok: hardware.shielding_active },
                ].map(item => (
                  <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #1a1a1a' }}>
                    <span style={{ fontSize: 12, color: '#888' }}>{item.label}</span>
                    <span style={{ fontSize: 12, color: item.ok ? '#7fff7f' : '#ff7070' }}>{item.value}</span>
                  </div>
                ))}
                {hardware.simulation && <div style={{ marginTop: 8, fontSize: 11, color: '#ffa500' }}>MODE SIMULATION</div>}
              </div>
            )}
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Fréquences GPS</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              {[
                { band: 'GPS L1', freq: '1575.42 MHz', use: 'Signal principal (civile)' },
                { band: 'GPS L2', freq: '1227.60 MHz', use: 'Signal militaire' },
                { band: 'GPS L5', freq: '1176.45 MHz', use: 'Haute précision' },
                { band: 'GLONASS L1', freq: '1602 MHz', use: 'Système russe' },
              ].map(f => (
                <div key={f.band} style={{ background: '#0d0d0d', border: '1px solid #222', borderRadius: 4, padding: 8 }}>
                  <span style={{ color: '#7fc4ff', fontWeight: 600 }}>{f.band}</span>
                  <span style={{ color: '#888', marginLeft: 12 }}>{f.freq}</span>
                  <span style={{ color: '#555', marginLeft: 12 }}>{f.use}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'signal' && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Générer Signal GPS</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { label: 'Latitude', val: lat, set: setLat },
                { label: 'Longitude', val: lon, set: setLon },
                { label: 'Altitude (m)', val: alt, set: setAlt },
                { label: 'Durée (s)', val: duration, set: setDuration },
                { label: 'Gain TX (dB)', val: gain, set: setGain },
              ].map(f => (
                <div key={f.label}>
                  <label style={{ fontSize: 11, color: '#888' }}>{f.label}</label>
                  <input value={f.val} onChange={e => f.set(e.target.value)} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 8px', borderRadius: 4, marginTop: 2, boxSizing: 'border-box' }} />
                </div>
              ))}
              <button onClick={generateSignal} disabled={loading || !auth} style={{ marginTop: 8, padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>📡 Générer Fichier Signal</button>
              <input value={signalFile} onChange={e => setSignalFile(e.target.value)} placeholder="Fichier signal généré..." style={{ background: '#1a1a1a', color: '#888', border: '1px solid #333', padding: '5px 8px', borderRadius: 4, fontSize: 11 }} />
              <button onClick={startTransmit} disabled={loading || !auth || !signalFile || transmitting} style={{ padding: '8px 0', background: transmitting ? '#1a1a1a' : '#2d1e1e', color: transmitting ? '#555' : '#ff7070', border: `1px solid ${transmitting ? '#333' : '#5d2e2e'}`, borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>▶ Transmettre (HackRF)</button>
            </div>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Coordonnées cible</h4>
            <div style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 12, fontFamily: 'monospace', fontSize: 13 }}>
              <div style={{ color: '#888', marginBottom: 8 }}>Position à simuler:</div>
              <div style={{ color: '#7fff7f' }}>LAT: {lat}°</div>
              <div style={{ color: '#7fff7f' }}>LON: {lon}°</div>
              <div style={{ color: '#7fff7f' }}>ALT: {alt}m</div>
              <div style={{ color: '#888', marginTop: 12 }}>Exemples de lieux:</div>
              {[
                { name: 'Paris — Tour Eiffel', lat: '48.858844', lon: '2.294351' },
                { name: 'Washington DC — Pentagon', lat: '38.871389', lon: '-77.055833' },
                { name: 'Moscou — Kremlin', lat: '55.751244', lon: '37.618423' },
                { name: 'Pékin — Interdit', lat: '39.916344', lon: '116.397155' },
              ].map(loc => (
                <div key={loc.name} onClick={() => { setLat(loc.lat); setLon(loc.lon) }} style={{ cursor: 'pointer', padding: '4px 0', color: '#4fc3f7', fontSize: 12 }}>→ {loc.name}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'waypoints' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Waypoints (trajectoire GPS)</h4>
            {waypoints.map((wp, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                <span style={{ color: '#888', fontSize: 12, width: 20 }}>#{i + 1}</span>
                <input value={wp.lat} onChange={e => updateWP(i, 'lat', e.target.value)} placeholder="Lat" style={{ flex: 1, background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 6px', borderRadius: 4, fontSize: 12 }} />
                <input value={wp.lon} onChange={e => updateWP(i, 'lon', e.target.value)} placeholder="Lon" style={{ flex: 1, background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 6px', borderRadius: 4, fontSize: 12 }} />
                <input value={wp.alt} onChange={e => updateWP(i, 'alt', e.target.value)} placeholder="Alt" style={{ width: 60, background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 6px', borderRadius: 4, fontSize: 12 }} />
                <button onClick={() => removeWaypoint(i)} style={{ padding: '4px 8px', background: '#2d1e1e', color: '#ff7070', border: 'none', borderRadius: 3, cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <button onClick={addWaypoint} style={{ padding: '6px 12px', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', marginRight: 8, fontSize: 12 }}>+ Waypoint</button>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Paramètres Trajet</h4>
            <label style={{ fontSize: 12, color: '#aaa' }}>Vitesse (km/h)</label>
            <input value={speed} onChange={e => setSpeed(e.target.value)} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, marginBottom: 12, boxSizing: 'border-box' }} />
            <button onClick={generateWaypoints} disabled={loading || !auth || waypoints.length < 2} style={{ width: '100%', padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', marginBottom: 8 }}>📡 Générer Trajectoire</button>
            {signalFile && <button onClick={startTransmit} disabled={loading || !auth || transmitting} style={{ width: '100%', padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>▶ Transmettre</button>}
          </div>
        </div>
      )}

      {tab === 'drone' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 600 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Drone GPS Spoofing (DJI / Parrot)</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 12, color: '#aaa' }}>IP du drone (réseau Wi-Fi)</label>
            <input value={droneIp} onChange={e => setDroneIp(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <label style={{ fontSize: 12, color: '#aaa' }}>Fausse position (Latitude)</label>
            <input value={droneLat} onChange={e => setDroneLat(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <label style={{ fontSize: 12, color: '#aaa' }}>Fausse position (Longitude)</label>
            <input value={droneLon} onChange={e => setDroneLon(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <button onClick={spoofDrone} disabled={loading || !auth} style={{ marginTop: 8, padding: '10px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>🚁 Dévier GPS Drone</button>
          </div>
        </div>
      )}

      {tab === 'jam' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 500 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>GPS Jamming (LABORATOIRE UNIQUEMENT)</h4>
          <div style={{ background: '#1a0a0a', border: '1px solid #5d2e2e', borderRadius: 4, padding: 10, marginBottom: 16, fontSize: 12, color: '#ff7070' }}>
            ⚠ Le brouillage GPS est un crime. Uniquement en environnement Faraday isolé.
          </div>
          <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>Transmet du bruit sur 1575.42 MHz pendant 10 secondes. Affecte tous les récepteurs GPS dans la zone non blindée.</p>
          <button onClick={jamGPS} disabled={loading || !auth} style={{ padding: '10px 24px', background: '#3e1e1e', color: '#ff4444', border: '2px solid #7d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 14 }}>⚡ BROUILLER GPS (10s)</button>
        </div>
      )}

      {(loading || result) && (
        <div style={{ marginTop: 16, background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 350 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
