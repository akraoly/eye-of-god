import { useState, useEffect } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'asat',   label: '🎯 ASAT' },
  { id: 'gps',    label: '🛰 GPS Warfare' },
  { id: 'satjam', label: '📡 Sat Jamming' },
  { id: 'ssa',    label: '🔭 SSA' },
  { id: 'leo',    label: '🌐 LEO Constellations' },
]

const WARN = '⚠️ USAGE LÉGAL UNIQUEMENT — Red team contractuel / simulation autorisée'

function StatusBadge({ v }) {
  const c = v === 'ACTIVE' || v === 'JAMMING' || v === 'PLANNED' ? '#00ff88'
    : v === 'STOPPED' || v === 'EXECUTED' ? '#888' : '#ffd700'
  return <span style={{ color: c, fontWeight: 700 }}>{v}</span>
}

function RiskBadge({ v }) {
  const c = v === 'RED' || v === 'CATASTROPHIC' || v === 'EXTREME' ? '#ff4444'
    : v === 'YELLOW' || v === 'HIGH' ? '#ffd700'
    : v === 'MODERATE' || v === 'MEDIUM' ? '#ff8800' : '#00ff88'
  return <span style={{ color: c, fontWeight: 700 }}>{v}</span>
}

// ── ASAT Tab ──────────────────────────────────────────────────────────────────
function AsatTab() {
  const [methods, setMethods] = useState(null)
  const [satellites, setSatellites] = useState([])
  const [missions, setMissions] = useState([])
  const [noradId, setNoradId] = useState(43013)
  const [method, setMethod] = useState('ke_interceptor')
  const [auth, setAuth] = useState(false)
  const [result, setResult] = useState(null)
  const [assess, setAssess] = useState(null)
  const [militaryOnly, setMilitaryOnly] = useState(false)

  useEffect(() => {
    apiFetch('/space/asat/methods').then(r => r.json()).then(setMethods)
    apiFetch('/space/asat/satellites?military_only=true').then(r => r.json()).then(d => setSatellites(d.satellites || []))
    apiFetch('/space/asat/missions').then(r => r.json()).then(d => setMissions(d.missions || []))
  }, [])

  const doAssess = async () => {
    const r = await apiFetch(`/space/asat/satellites/${noradId}/assess`)
    setAssess(await r.json())
  }

  const doPlan = async () => {
    const r = await apiFetch('/space/asat/plan', {
      method: 'POST',
      body: JSON.stringify({ norad_id: noradId, method, authorization_confirmed: auth }),
    })
    const d = await r.json()
    setResult(d)
    if (d.mission_id) {
      apiFetch('/space/asat/missions').then(r => r.json()).then(d => setMissions(d.missions || []))
    }
  }

  const doExecute = async (missionId) => {
    const r = await apiFetch('/space/asat/execute', {
      method: 'POST',
      body: JSON.stringify({ mission_id: missionId, authorization_confirmed: true }),
    })
    const d = await r.json()
    setResult(d)
    apiFetch('/space/asat/missions').then(r => r.json()).then(d => setMissions(d.missions || []))
  }

  return (
    <div className="bloc-section">
      <div className="grid2">
        <div>
          <h4 style={{ color: '#ff4444' }}>Satellites Cibles</h4>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            {satellites.map(s => (
              <div key={s.norad_id} className="card-row" style={{ cursor: 'pointer', borderColor: noradId === s.norad_id ? '#ff4444' : undefined }}
                onClick={() => setNoradId(s.norad_id)}>
                <span style={{ color: '#ffd700' }}>{s.norad_id}</span>
                <span style={{ color: '#00ccff', marginLeft: 8 }}>{s.name}</span>
                <span style={{ marginLeft: 8, color: '#888' }}>{s.orbit} {s.altitude_km}km</span>
                {s.military && <span style={{ color: '#ff4444', marginLeft: 8 }}>MIL</span>}
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 style={{ color: '#ff4444' }}>Planifier Interception</h4>
          <div className="field-row">
            <label>NORAD ID</label>
            <input className="eog-input" type="number" value={noradId} onChange={e => setNoradId(+e.target.value)} />
          </div>
          <div className="field-row">
            <label>Méthode</label>
            <select className="eog-input" value={method} onChange={e => setMethod(e.target.value)}>
              {methods && Object.keys(methods.asat_methods || {}).map(k => (
                <option key={k} value={k}>{k}</option>
              ))}
              {!methods && ['ke_interceptor','laser_dazzle','laser_blind','co_orbital','microwave_dew','cyberattack'].map(k => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0', color: '#ff8800' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
            authorization_confirmed
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn-action" onClick={doAssess}>Évaluer cible</button>
            <button className="btn-danger" onClick={doPlan} disabled={!auth}>Planifier</button>
          </div>
        </div>
      </div>

      {assess && (
        <div className="result-box" style={{ marginTop: 12 }}>
          <div><span className="label">Satellite :</span> {assess.satellite?.name} — {assess.satellite?.altitude_km}km</div>
          <div><span className="label">Méthodes viables :</span> {assess.viable_methods?.join(', ')}</div>
          <div><span className="label">Période orbitale :</span> {assess.orbital_period_min}min</div>
          <div><span className="label">Prochain passage :</span> ~{assess.next_pass_estimate_min}min</div>
        </div>
      )}

      {result && (
        <div className="result-box" style={{ marginTop: 12, borderColor: result.error ? '#ff4444' : '#ffd700' }}>
          {result.error ? <span style={{ color: '#ff4444' }}>⛔ {result.error}</span> : (
            <>
              <div><span className="label">Mission :</span> {result.mission_id}</div>
              <div><span className="label">Statut :</span> <StatusBadge v={result.status} /></div>
              <div><span className="label">PK :</span> {(result.pk * 100).toFixed(1)}%</div>
              <div><span className="label">TOF :</span> {result.tof_min}min</div>
              <div><span className="label">Débris générés :</span> <span style={{ color: result.debris_objects > 100 ? '#ff4444' : '#00ff88' }}>{result.debris_objects}</span></div>
              {result.kill_assessment && <div><span className="label">Assessment :</span> <span style={{ color: result.intercept_success ? '#00ff88' : '#ff4444' }}>{result.kill_assessment}</span></div>}
            </>
          )}
        </div>
      )}

      {missions.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ color: '#ffd700' }}>Missions planifiées</h4>
          {missions.map(m => (
            <div key={m.mission_id} className="card-row">
              <span style={{ color: '#00ccff' }}>{m.mission_id}</span>
              <span style={{ marginLeft: 8 }}>{m.target?.name}</span>
              <span style={{ marginLeft: 8, color: '#888' }}>{m.method}</span>
              <StatusBadge v={m.status} />
              {m.status === 'PLANNED' && (
                <button className="btn-danger" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11 }}
                  onClick={() => doExecute(m.mission_id)}>EXÉCUTER</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── GPS Warfare Tab ───────────────────────────────────────────────────────────
function GpsTab() {
  const [systems, setSystems] = useState({})
  const [scan, setScan] = useState(null)
  const [sessions, setSessions] = useState(null)
  const [detect, setDetect] = useState(null)
  const [auth, setAuth] = useState(false)
  const [result, setResult] = useState(null)
  const [target, setTarget] = useState('gps')
  const [technique, setTechnique] = useState('sophisticated_spoof')
  const [fakeLat, setFakeLat] = useState(55.75)
  const [fakeLon, setFakeLon] = useState(37.62)
  const [powerW, setPowerW] = useState(100)

  useEffect(() => {
    apiFetch('/space/gps/systems').then(r => r.json()).then(d => setSystems(d.systems || {}))
    apiFetch('/space/gps/sessions').then(r => r.json()).then(setSessions)
  }, [])

  const doScan = async () => {
    const r = await apiFetch('/space/gps/scan?lat=48.85&lon=2.35')
    setScan(await r.json())
  }
  const doDetect = async () => {
    const r = await apiFetch('/space/gps/anti-spoof')
    setDetect(await r.json())
  }
  const doSpoof = async () => {
    const r = await apiFetch('/space/gps/spoof', {
      method: 'POST',
      body: JSON.stringify({ target_system: target, technique, fake_lat: fakeLat, fake_lon: fakeLon, authorization_confirmed: auth }),
    })
    setResult(await r.json())
  }
  const doJam = async () => {
    const r = await apiFetch('/space/gps/jam', {
      method: 'POST',
      body: JSON.stringify({ target_system: target, power_w: powerW, jamming_type: 'noise_jammer', authorization_confirmed: auth }),
    })
    setResult(await r.json())
  }

  return (
    <div className="bloc-section">
      <div className="grid2">
        <div>
          <h4 style={{ color: '#00ccff' }}>Systèmes GNSS</h4>
          {Object.entries(systems).map(([k, v]) => (
            <div key={k} className="card-row" style={{ cursor: 'pointer', borderColor: target === k ? '#00ccff' : undefined }}
              onClick={() => setTarget(k)}>
              <span style={{ color: '#ffd700', textTransform: 'uppercase' }}>{k}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{v.nation}</span>
              <span style={{ color: '#00ff88', marginLeft: 8 }}>{v.satellites} sats</span>
              <span style={{ color: '#aaa', marginLeft: 8 }}>{v.freq_l1_mhz || v.freq_b1_mhz || v.freq_e1_mhz} MHz</span>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button className="btn-action" onClick={doScan}>Scanner env.</button>
            <button className="btn-action" onClick={doDetect}>Anti-Spoof detect</button>
          </div>
        </div>
        <div>
          <h4 style={{ color: '#00ccff' }}>Opération GPS</h4>
          <div className="field-row">
            <label>Cible GNSS</label>
            <select className="eog-input" value={target} onChange={e => setTarget(e.target.value)}>
              {Object.keys(systems).map(k => <option key={k} value={k}>{k.toUpperCase()}</option>)}
            </select>
          </div>
          <div className="field-row">
            <label>Technique Spoofing</label>
            <select className="eog-input" value={technique} onChange={e => setTechnique(e.target.value)}>
              {['meaconing','simplistic_spoof','sophisticated_spoof','relay_attack','time_attack'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <label>Fausse position (lat/lon)</label>
            <input className="eog-input" style={{ width: 80 }} type="number" value={fakeLat} onChange={e => setFakeLat(+e.target.value)} />
            <input className="eog-input" style={{ width: 80, marginLeft: 4 }} type="number" value={fakeLon} onChange={e => setFakeLon(+e.target.value)} />
          </div>
          <div className="field-row">
            <label>Puissance Jamming (W)</label>
            <input className="eog-input" type="number" value={powerW} onChange={e => setPowerW(+e.target.value)} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0', color: '#ff8800' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
            authorization_confirmed
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-danger" onClick={doSpoof} disabled={!auth}>Spoof Position</button>
            <button className="btn-danger" onClick={doJam} disabled={!auth}>Jam GNSS</button>
          </div>
        </div>
      </div>

      {scan && (
        <div className="result-box" style={{ marginTop: 12 }}>
          <div style={{ color: '#ffd700', marginBottom: 6 }}>Scan environnement GNSS</div>
          {scan.gnss_signals?.map(s => (
            <div key={s.system} className="card-row">
              <span style={{ color: '#00ccff', width: 80, display: 'inline-block' }}>{s.system.toUpperCase()}</span>
              <span style={{ color: '#00ff88' }}>{s.sats_visible} sats</span>
              <span style={{ color: '#888', marginLeft: 8 }}>SNR {s.snr_db}dB</span>
              <span style={{ color: '#aaa', marginLeft: 8 }}>{s.position_accuracy_m}m acc.</span>
              <span style={{ marginLeft: 8, color: s.fix_quality === '3D' ? '#00ff88' : '#ff4444' }}>{s.fix_quality}</span>
            </div>
          ))}
          {scan.spoofing_indicators && <div style={{ color: '#ff4444', marginTop: 4 }}>⚠️ Indicateurs de spoofing détectés</div>}
        </div>
      )}

      {detect && (
        <div className="result-box" style={{ marginTop: 12, borderColor: detect.spoofing_detected ? '#ff4444' : '#00ff88' }}>
          <div><span className="label">Spoofing détecté :</span> <span style={{ color: detect.spoofing_detected ? '#ff4444' : '#00ff88' }}>{detect.spoofing_detected ? 'OUI' : 'NON'}</span></div>
          <div><span className="label">Confiance :</span> {detect.confidence_pct}%</div>
          <div><span className="label">Indicateurs :</span> {detect.indicators?.join(', ') || 'Aucun'}</div>
          <div><span className="label">Recommandation :</span> {detect.recommendation}</div>
        </div>
      )}

      {result && (
        <div className="result-box" style={{ marginTop: 12, borderColor: result.error ? '#ff4444' : '#00ccff' }}>
          {result.error ? <span style={{ color: '#ff4444' }}>⛔ {result.error}</span> : (
            <>
              <div><span className="label">Session :</span> {result.session_id}</div>
              <div><span className="label">Statut :</span> <StatusBadge v={result.status} /></div>
              {result.position_error_injected_m && <div><span className="label">Erreur injectée :</span> {result.position_error_injected_m}m</div>}
              {result.effective_range_km && <div><span className="label">Portée effective :</span> {result.effective_range_km}km</div>}
              <div><span className="label">Risque détection :</span> <RiskBadge v={result.detection_risk} /></div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Sat Jamming Tab ───────────────────────────────────────────────────────────
function SatJamTab() {
  const [sats, setSats] = useState([])
  const [ops, setOps] = useState([])
  const [satId, setSatId] = useState('WGS-9')
  const [mode, setMode] = useState('uplink_jam')
  const [power, setPower] = useState(10)
  const [freqGhz, setFreqGhz] = useState(30.0)
  const [auth, setAuth] = useState(false)
  const [result, setResult] = useState(null)
  const [analysis, setAnalysis] = useState(null)

  useEffect(() => {
    apiFetch('/space/satjam/satellites').then(r => r.json()).then(d => setSats(d.satellites || []))
    apiFetch('/space/satjam/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }, [])

  const doAnalyze = async () => {
    const r = await apiFetch(`/space/satjam/satellites/${encodeURIComponent(satId)}`)
    setAnalysis(await r.json())
  }
  const doJam = async () => {
    const r = await apiFetch('/space/satjam/jam', {
      method: 'POST',
      body: JSON.stringify({ sat_id: satId, mode, power_kw: power, authorization_confirmed: auth }),
    })
    const d = await r.json()
    setResult(d)
    if (d.op_id) apiFetch('/space/satjam/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }
  const doHijack = async () => {
    const r = await apiFetch('/space/satjam/hijack', {
      method: 'POST',
      body: JSON.stringify({ sat_id: satId, target_freq_ghz: freqGhz, authorization_confirmed: auth }),
    })
    const d = await r.json()
    setResult(d)
  }
  const doStop = async (opId) => {
    await apiFetch(`/space/satjam/operations/${opId}`, { method: 'DELETE' })
    apiFetch('/space/satjam/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }

  return (
    <div className="bloc-section">
      <div className="grid2">
        <div>
          <h4 style={{ color: '#ffd700' }}>Satellites SATCOM</h4>
          <div style={{ maxHeight: 250, overflowY: 'auto' }}>
            {sats.map(s => (
              <div key={s.sat_id} className="card-row" style={{ cursor: 'pointer', borderColor: satId === s.sat_id ? '#ffd700' : undefined }}
                onClick={() => setSatId(s.sat_id)}>
                <span style={{ color: '#ffd700' }}>{s.sat_id}</span>
                <span style={{ color: '#888', marginLeft: 8 }}>{s.band}-band</span>
                <span style={{ color: '#aaa', marginLeft: 8 }}>{s.coverage}</span>
                {s.military && <span style={{ color: '#ff4444', marginLeft: 8 }}>MIL</span>}
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 style={{ color: '#ffd700' }}>Paramètres Jamming</h4>
          <div className="field-row">
            <label>Satellite</label>
            <input className="eog-input" value={satId} onChange={e => setSatId(e.target.value)} />
          </div>
          <div className="field-row">
            <label>Mode</label>
            <select className="eog-input" value={mode} onChange={e => setMode(e.target.value)}>
              {['uplink_jam','downlink_jam','crosslink_jam','transponder_hijack','lobe_jamming','swept_noise'].map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <label>Puissance (kW)</label>
            <input className="eog-input" type="number" value={power} onChange={e => setPower(+e.target.value)} />
          </div>
          <div className="field-row">
            <label>Fréq. hijack (GHz)</label>
            <input className="eog-input" type="number" step="0.1" value={freqGhz} onChange={e => setFreqGhz(+e.target.value)} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0', color: '#ff8800' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
            authorization_confirmed
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn-action" onClick={doAnalyze}>Analyser</button>
            <button className="btn-danger" onClick={doJam} disabled={!auth}>Jammer</button>
            <button className="btn-danger" onClick={doHijack} disabled={!auth}>Hijack</button>
          </div>
        </div>
      </div>

      {analysis && (
        <div className="result-box" style={{ marginTop: 12 }}>
          <div><span className="label">Difficulté :</span> <RiskBadge v={analysis.jamming_difficulty} /></div>
          <div><span className="label">Mode recommandé :</span> {analysis.recommended_mode}</div>
          <div><span className="label">Puissance estimée :</span> {analysis.estimated_power_kw}kW</div>
          <div><span className="label">LPI/LPD :</span> {analysis.lpi_lpd_protected ? '✅ Protégé' : '❌ Non protégé'}</div>
        </div>
      )}

      {result && (
        <div className="result-box" style={{ marginTop: 12, borderColor: result.error ? '#ff4444' : '#ffd700' }}>
          {result.error ? <span style={{ color: '#ff4444' }}>⛔ {result.error}</span> : (
            <>
              <div><span className="label">Op :</span> {result.op_id}</div>
              <div><span className="label">JSR :</span> {result.jammer_to_signal_ratio_db}dB</div>
              {result.affected_area_km2 && <div><span className="label">Zone affectée :</span> {result.affected_area_km2?.toLocaleString()} km²</div>}
              {result.takeover_time_s && <div><span className="label">Takeover :</span> {result.takeover_time_s}s</div>}
            </>
          )}
        </div>
      )}

      {ops.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h4 style={{ color: '#ffd700' }}>Opérations actives</h4>
          {ops.map(o => (
            <div key={o.op_id} className="card-row">
              <span style={{ color: '#ffd700' }}>{o.op_id}</span>
              <span style={{ marginLeft: 8 }}>{o.satellite}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{o.mode}</span>
              <StatusBadge v={o.status} />
              {o.status === 'JAMMING' && (
                <button className="btn-action" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11 }} onClick={() => doStop(o.op_id)}>Stop</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── SSA Tab ───────────────────────────────────────────────────────────────────
function SsaTab() {
  const [catalog, setCatalog] = useState(null)
  const [shell, setShell] = useState('LEO_low')
  const [objects, setObjects] = useState([])
  const [norad, setNorad] = useState(25544)
  const [track, setTrack] = useState(null)
  const [conj, setConj] = useState(null)
  const [kessler, setKessler] = useState(null)
  const [altKm, setAltKm] = useState(800)

  useEffect(() => {
    apiFetch('/space/ssa/catalog').then(r => r.json()).then(setCatalog)
  }, [])

  const doScan = async () => {
    const r = await apiFetch(`/space/ssa/scan/${shell}?count=15`)
    const d = await r.json()
    setObjects(d.objects_detected || [])
  }
  const doTrack = async () => {
    const r = await apiFetch(`/space/ssa/objects/${norad}`)
    const d = await r.json()
    setTrack(d.object)
  }
  const doConj = async () => {
    const r = await apiFetch(`/space/ssa/objects/${norad}/conjunction`)
    setConj(await r.json())
  }
  const doKessler = async () => {
    const r = await apiFetch(`/space/ssa/kessler?altitude_km=${altKm}`)
    setKessler(await r.json())
  }

  return (
    <div className="bloc-section">
      <div className="grid2">
        <div>
          <h4 style={{ color: '#00ff88' }}>Statistiques Catalogue</h4>
          {catalog && (
            <div>
              <div style={{ color: '#ffd700', fontSize: 22, fontWeight: 700 }}>{catalog.total_tracked_objects?.toLocaleString()}</div>
              <div style={{ color: '#888', fontSize: 12 }}>objets trackés</div>
              <div style={{ marginTop: 8 }}>
                {catalog.shells && Object.entries(catalog.shells).map(([k, v]) => (
                  <div key={k} className="card-row" style={{ cursor: 'pointer', borderColor: shell === k ? '#00ff88' : undefined }} onClick={() => setShell(k)}>
                    <span style={{ color: '#00ccff', width: 100, display: 'inline-block' }}>{k}</span>
                    <span style={{ color: '#00ff88' }}>{v.object_count?.toLocaleString()}</span>
                    <span style={{ color: '#888', marginLeft: 8 }}>{v.alt_range[0]}-{v.alt_range[1]}km</span>
                  </div>
                ))}
              </div>
              <button className="btn-action" style={{ marginTop: 8 }} onClick={doScan}>Scanner {shell}</button>
            </div>
          )}
        </div>
        <div>
          <h4 style={{ color: '#00ff88' }}>Tracking & Analyse</h4>
          <div className="field-row">
            <label>NORAD ID</label>
            <input className="eog-input" type="number" value={norad} onChange={e => setNorad(+e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '8px 0' }}>
            <button className="btn-action" onClick={doTrack}>Track</button>
            <button className="btn-action" onClick={doConj}>Conjonction</button>
          </div>
          <div className="field-row">
            <label>Altitude Kessler (km)</label>
            <input className="eog-input" type="number" value={altKm} onChange={e => setAltKm(+e.target.value)} />
          </div>
          <button className="btn-action" onClick={doKessler}>Analyse Kessler</button>
        </div>
      </div>

      {objects.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h4 style={{ color: '#00ff88' }}>Objets détectés — {shell}</h4>
          <div style={{ maxHeight: 180, overflowY: 'auto' }}>
            {objects.map(o => (
              <div key={o.norad_id} className="card-row" style={{ cursor: 'pointer' }} onClick={() => setNorad(o.norad_id)}>
                <span style={{ color: '#ffd700' }}>{o.norad_id}</span>
                <span style={{ color: '#888', marginLeft: 8 }}>{o.type}</span>
                <span style={{ color: '#aaa', marginLeft: 8 }}>{o.altitude_km}km</span>
                <span style={{ color: '#555', marginLeft: 8 }}>{o.nation}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {track && (
        <div className="result-box" style={{ marginTop: 12 }}>
          <div><span className="label">Objet :</span> {track.name} ({track.type})</div>
          <div><span className="label">Altitude :</span> {track.altitude_km}km — {track.orbit}</div>
          <div><span className="label">Vitesse :</span> {track.velocity_ms?.toLocaleString()}m/s</div>
          <div><span className="label">Période :</span> {track.orbital_period_min}min</div>
          <div><span className="label">RCS :</span> {track.rcs_m2}m²</div>
          <div><span className="label">Qualité track :</span> {track.track_quality}</div>
        </div>
      )}

      {conj && (
        <div className="result-box" style={{ marginTop: 12, borderColor: conj.maneuver_recommended ? '#ff4444' : '#00ff88' }}>
          <div style={{ color: '#ffd700', marginBottom: 4 }}>Analyse de conjonction — {conj.look_ahead_hours}h</div>
          {conj.conjunctions?.length === 0 && <div style={{ color: '#00ff88' }}>Aucune conjonction détectée</div>}
          {conj.conjunctions?.map(c => (
            <div key={c.event_id} className="card-row">
              <RiskBadge v={c.risk} />
              <span style={{ marginLeft: 8 }}>{c.secondary_object}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{c.miss_distance_m}m miss</span>
              <span style={{ color: '#555', marginLeft: 8 }}>Pc={c.pc.toExponential(2)}</span>
            </div>
          ))}
          {conj.maneuver_recommended && <div style={{ color: '#ff4444', marginTop: 4 }}>⚠️ Manœuvre recommandée</div>}
        </div>
      )}

      {kessler && (
        <div className="result-box" style={{ marginTop: 12, borderColor: kessler.kessler_risk === 'CRITICAL' ? '#ff4444' : '#ffd700' }}>
          <div><span className="label">Risque Kessler :</span> <RiskBadge v={kessler.kessler_risk} /></div>
          <div><span className="label">Densité objets :</span> {kessler.object_density_per_km3?.toExponential(4)}/km³</div>
          <div><span className="label">Cascade :</span> {kessler.fragmentation_cascade_threshold ? '⚠️ RISQUE' : '✅ Sûr'}</div>
        </div>
      )}
    </div>
  )
}

// ── LEO Constellations Tab ────────────────────────────────────────────────────
function LeoTab() {
  const [constellations, setConstellations] = useState({})
  const [ops, setOps] = useState([])
  const [selected, setSelected] = useState('starlink')
  const [analysis, setAnalysis] = useState(null)
  const [impact, setImpact] = useState(null)
  const [region, setRegion] = useState('EUROPE')
  const [attackType, setAttackType] = useState('terminal_jamming')
  const [gsMethod, setGsMethod] = useState('cyber_intrusion')
  const [auth, setAuth] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    apiFetch('/space/leo/constellations').then(r => r.json()).then(d => setConstellations(d.constellations || {}))
    apiFetch('/space/leo/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }, [])

  const doAnalyze = async () => {
    const r = await apiFetch(`/space/leo/constellations/${selected}`)
    setAnalysis(await r.json())
  }
  const doImpact = async () => {
    const r = await apiFetch(`/space/leo/constellations/${selected}/impact?attack_type=${attackType}`)
    setImpact(await r.json())
  }
  const doTerminal = async () => {
    const r = await apiFetch('/space/leo/terminal-attack', {
      method: 'POST',
      body: JSON.stringify({ constellation: selected, target_region: region, attack_type: attackType, authorization_confirmed: auth }),
    })
    const d = await r.json()
    setResult(d)
    if (d.op_id) apiFetch('/space/leo/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }
  const doGs = async () => {
    const r = await apiFetch('/space/leo/ground-station', {
      method: 'POST',
      body: JSON.stringify({ constellation: selected, station_id: `GS-${selected.toUpperCase()}-01`, method: gsMethod, authorization_confirmed: auth }),
    })
    setResult(await r.json())
  }
  const doCrosslink = async () => {
    const r = await apiFetch('/space/leo/crosslink-jam', {
      method: 'POST',
      body: JSON.stringify({ constellation: selected, authorization_confirmed: auth }),
    })
    setResult(await r.json())
  }
  const doStop = async (opId) => {
    await apiFetch(`/space/leo/operations/${opId}`, { method: 'DELETE' })
    apiFetch('/space/leo/operations').then(r => r.json()).then(d => setOps(d.operations || []))
  }

  const c = constellations[selected] || {}

  return (
    <div className="bloc-section">
      <div className="grid2">
        <div>
          <h4 style={{ color: '#ff8800' }}>Constellations LEO</h4>
          {Object.entries(constellations).map(([k, v]) => (
            <div key={k} className="card-row" style={{ cursor: 'pointer', borderColor: selected === k ? '#ff8800' : undefined }}
              onClick={() => setSelected(k)}>
              <span style={{ color: '#ffd700', textTransform: 'capitalize' }}>{k}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{v.operator}</span>
              <span style={{ color: '#00ff88', marginLeft: 8 }}>{v.active_sats?.toLocaleString()} sats</span>
              {v.military_contract && <span style={{ color: '#ff4444', marginLeft: 8 }}>MIL</span>}
            </div>
          ))}
        </div>
        <div>
          <h4 style={{ color: '#ff8800' }}>Attaque constellation</h4>
          {c.total_sats && (
            <div className="result-box" style={{ marginBottom: 8, padding: '6px 10px' }}>
              <div><span className="label">Sats actifs :</span> {c.active_sats?.toLocaleString()}</div>
              <div><span className="label">Altitude :</span> {c.altitude_km}km</div>
              <div><span className="label">Terminaux :</span> {c.terminal_count_est?.toLocaleString()}</div>
            </div>
          )}
          <div className="field-row">
            <label>Région cible</label>
            <input className="eog-input" value={region} onChange={e => setRegion(e.target.value)} />
          </div>
          <div className="field-row">
            <label>Type d'attaque</label>
            <select className="eog-input" value={attackType} onChange={e => setAttackType(e.target.value)}>
              {['terminal_jamming','ground_station_attack','crosslink_disruption','uplink_spoofing','constellation_blinding','terminal_firmware_hack'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <label>Méthode GS</label>
            <select className="eog-input" value={gsMethod} onChange={e => setGsMethod(e.target.value)}>
              {['cyber_intrusion','supply_chain','physical_access','rf_injection'].map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0', color: '#ff8800' }}>
            <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
            authorization_confirmed
          </label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button className="btn-action" onClick={doAnalyze}>Analyser</button>
            <button className="btn-action" onClick={doImpact}>Impact</button>
            <button className="btn-danger" onClick={doTerminal} disabled={!auth}>Terminal</button>
            <button className="btn-danger" onClick={doGs} disabled={!auth}>Ground Station</button>
            <button className="btn-danger" onClick={doCrosslink} disabled={!auth}>Crosslink Jam</button>
          </div>
        </div>
      </div>

      {analysis && (
        <div className="result-box" style={{ marginTop: 12 }}>
          <div><span className="label">Vulnérabilités :</span> {analysis.vulnerabilities?.join(' | ')}</div>
          <div><span className="label">Vecteur recommandé :</span> {analysis.recommended_vector}</div>
          <div><span className="label">Score vulnérabilité :</span> {analysis.vulnerability_score}/5</div>
        </div>
      )}

      {impact && (
        <div className="result-box" style={{ marginTop: 12, borderColor: impact.strategic_value === 'TIER_1' ? '#ff4444' : '#ffd700' }}>
          <div><span className="label">Impact militaire :</span> <RiskBadge v={impact.military_impact} /></div>
          <div><span className="label">Impact civil :</span> <RiskBadge v={impact.civilian_impact} /></div>
          <div><span className="label">Impact économique :</span> ${impact.economic_impact_musd?.toLocaleString()}M</div>
          <div><span className="label">Terminaux à risque :</span> {impact.terminals_at_risk?.toLocaleString()}</div>
          <div><span className="label">Valeur stratégique :</span> {impact.strategic_value}</div>
        </div>
      )}

      {result && (
        <div className="result-box" style={{ marginTop: 12, borderColor: result.error ? '#ff4444' : '#ff8800' }}>
          {result.error ? <span style={{ color: '#ff4444' }}>⛔ {result.error}</span> : (
            <>
              <div><span className="label">Op :</span> {result.op_id}</div>
              {result.terminals_affected && <div><span className="label">Terminaux affectés :</span> {result.terminals_affected?.toLocaleString()}</div>}
              {result.coverage_denial_pct && <div><span className="label">Déni couverture :</span> {result.coverage_denial_pct}%</div>}
              {result.outage_duration_hours && <div><span className="label">Durée panne :</span> {result.outage_duration_hours}h</div>}
              {result.network_partition_risk !== undefined && <div><span className="label">Partition réseau :</span> {result.network_partition_risk ? '⚠️ OUI' : 'Non'}</div>}
              <div><span className="label">Détection :</span> <RiskBadge v={result.detection_risk} /></div>
            </>
          )}
        </div>
      )}

      {ops.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h4 style={{ color: '#ff8800' }}>Opérations actives</h4>
          {ops.map(o => (
            <div key={o.op_id} className="card-row">
              <span style={{ color: '#ff8800' }}>{o.op_id}</span>
              <span style={{ marginLeft: 8 }}>{o.constellation}</span>
              <span style={{ color: '#888', marginLeft: 8 }}>{o.attack_type}</span>
              <StatusBadge v={o.status} />
              {o.status === 'ACTIVE' && (
                <button className="btn-action" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11 }} onClick={() => doStop(o.op_id)}>Stop</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main View ─────────────────────────────────────────────────────────────────
export default function SpaceWarfareView() {
  const [tab, setTab] = useState('asat')

  return (
    <div className="view-container">
      <div className="view-header">
        <h2 className="view-title">🚀 Guerre Spatiale & Orbital — Bloc 14</h2>
        <p className="view-sub">ASAT · GPS Warfare · Sat Jamming · SSA · LEO Constellations</p>
      </div>
      <div className="warn-banner">{WARN}</div>
      <div className="tab-bar">
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="tab-content">
        {tab === 'asat'   && <AsatTab />}
        {tab === 'gps'    && <GpsTab />}
        {tab === 'satjam' && <SatJamTab />}
        {tab === 'ssa'    && <SsaTab />}
        {tab === 'leo'    && <LeoTab />}
      </div>
    </div>
  )
}
