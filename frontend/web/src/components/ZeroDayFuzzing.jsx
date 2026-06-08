import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

export default function ZeroDayFuzzing() {
  const [tab, setTab] = useState('firmware')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [jobs, setJobs] = useState({})
  const [activeJob, setActiveJob] = useState(null)
  const pollRef = useRef(null)

  // Firmware state
  const [vendor, setVendor] = useState('tp-link')
  const [model, setModel] = useState('TL-WR841N')
  const [fwPath, setFwPath] = useState('')
  const [extractedPath, setExtractedPath] = useState('')
  const [binaries, setBinaries] = useState([])
  const [selectedBinary, setSelectedBinary] = useState(null)
  const [fuzzTimeout, setFuzzTimeout] = useState(3600)

  useEffect(() => {
    if (activeJob) {
      pollRef.current = setInterval(() => pollJob(activeJob), 3000)
    }
    return () => clearInterval(pollRef.current)
  }, [activeJob])

  const pollJob = async (taskId) => {
    const r = await apiFetch(`/zeroday/fuzz/status/${taskId}`)
    if (!r.error) {
      setJobs(prev => ({ ...prev, [taskId]: r }))
      if (r.status !== 'running') {
        clearInterval(pollRef.current)
        setActiveJob(null)
      }
    }
  }

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const downloadFW = () => act(async () => {
    const r = await apiFetch('/zeroday/firmware/download', { method: 'POST', body: { vendor, model, authorization_confirmed: auth } })
    setResult(r); if (r.firmware_path || r.target_id) setFwPath(r.firmware_path || '')
  })

  const extractFW = () => act(async () => {
    const r = await apiFetch('/zeroday/firmware/extract', { method: 'POST', body: { firmware_path: fwPath, authorization_confirmed: auth } })
    setResult(r); if (r.extracted_path) setExtractedPath(r.extracted_path)
  })

  const identifyBins = () => act(async () => {
    const r = await apiFetch('/zeroday/firmware/identify', { method: 'POST', body: { firmware_path: extractedPath, authorization_confirmed: auth } })
    if (Array.isArray(r)) setBinaries(r)
    setResult(r)
  })

  const startFuzz = () => act(async () => {
    if (!selectedBinary) return
    const r = await apiFetch('/zeroday/fuzz/start', { method: 'POST', body: { binary_path: selectedBinary.path, timeout: fuzzTimeout, authorization_confirmed: auth } })
    setResult(r)
    if (r.task_id) { setActiveJob(r.task_id); setJobs(prev => ({ ...prev, [r.task_id]: r })) }
  })

  const stopFuzz = () => act(async () => {
    if (!activeJob) return
    const r = await apiFetch(`/zeroday/fuzz/stop/${activeJob}`, { method: 'POST', body: { authorization_confirmed: auth } })
    setResult(r); setActiveJob(null)
  })

  const checkDefenses = () => act(async () => {
    if (!selectedBinary) return
    const r = await apiFetch('/zeroday/defenses', { method: 'POST', body: { binary_path: selectedBinary.path, authorization_confirmed: auth } })
    setResult(r)
  })

  const genPoC = (crash) => act(async () => {
    if (!selectedBinary || !crash) return
    const r = await apiFetch('/zeroday/poc/generate', { method: 'POST', body: { crash_file: crash.file, binary_path: selectedBinary.path, authorization_confirmed: auth } })
    setResult(r)
  })

  const searchCVE = () => act(async () => {
    const r = await apiFetch('/zeroday/cve/search', { method: 'POST', body: { vendor, model, binary_name: selectedBinary?.name || 'httpd', version: '1.0.0', authorization_confirmed: auth } })
    setResult(r)
  })

  const currentJob = activeJob ? jobs[activeJob] : Object.values(jobs).slice(-1)[0]

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>🔬 Zero-Day Fuzzing — IoT Firmware</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>AFL++ · binwalk · GDB triage · PoC génération</p>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Pentest autorisé confirmé</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['firmware', 'fuzz', 'crashes', 'analysis'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
      </div>

      {tab === 'firmware' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Acquisition Firmware</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Vendor</label>
              <select value={vendor} onChange={e => setVendor(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }}>
                {['tp-link', 'netgear', 'd-link', 'hikvision', 'dahua'].map(v => <option key={v} value={v}>{v}</option>)}
              </select>
              <label style={{ fontSize: 12, color: '#aaa' }}>Modèle</label>
              <input value={model} onChange={e => setModel(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={downloadFW} disabled={loading || !auth} style={{ marginTop: 8, padding: '8px 0', background: '#ff6b35', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Télécharger Firmware</button>
            </div>
          </div>

          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Extraction & Analyse</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Chemin firmware</label>
              <input value={fwPath} onChange={e => setFwPath(e.target.value)} placeholder="./data/firmware/..." style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={extractFW} disabled={loading || !auth || !fwPath} style={{ padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>🔓 Extraire (binwalk)</button>
              <input value={extractedPath} onChange={e => setExtractedPath(e.target.value)} placeholder="Chemin extrait..." style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={identifyBins} disabled={loading || !auth || !extractedPath} style={{ padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>🔍 Identifier Binaires</button>
            </div>
          </div>

          {binaries.length > 0 && (
            <div style={{ gridColumn: '1/-1', background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Binaires ({binaries.length})</h4>
              <div style={{ display: 'grid', gap: 6 }}>
                {binaries.map((b, i) => (
                  <div key={i} onClick={() => setSelectedBinary(b)} style={{ padding: '10px 12px', background: selectedBinary?.name === b.name ? '#1e2a1e' : '#0d0d0d', border: `1px solid ${selectedBinary?.name === b.name ? '#4caf50' : '#222'}`, borderRadius: 4, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#7fff7f', fontWeight: 600 }}>{b.name}</span>
                    <span style={{ fontSize: 11, color: '#888' }}>{b.arch} · {b.endian}-endian · {b.size_kb}KB</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {b.canary && <span style={{ fontSize: 10, background: '#1e3a1e', color: '#7fff7f', padding: '2px 6px', borderRadius: 3 }}>CANARY</span>}
                      {b.nx && <span style={{ fontSize: 10, background: '#1e2a3e', color: '#7fc4ff', padding: '2px 6px', borderRadius: 3 }}>NX</span>}
                      {b.pie && <span style={{ fontSize: 10, background: '#3e1e2a', color: '#ffb7d5', padding: '2px 6px', borderRadius: 3 }}>PIE</span>}
                      {!b.canary && !b.nx && <span style={{ fontSize: 10, background: '#3e1e1e', color: '#ff7070', padding: '2px 6px', borderRadius: 3 }}>⚠ UNPROTECTED</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'fuzz' && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Config AFL++</h4>
              <label style={{ fontSize: 12, color: '#aaa' }}>Binaire cible</label>
              <input value={selectedBinary?.path || ''} onChange={e => setSelectedBinary({ path: e.target.value, name: e.target.value.split('/').pop() })} placeholder="Sélectionner dans Firmware →" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, marginBottom: 8, boxSizing: 'border-box' }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Durée max (secondes)</label>
              <input type="number" value={fuzzTimeout} onChange={e => setFuzzTimeout(Number(e.target.value))} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, boxSizing: 'border-box' }} />
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={startFuzz} disabled={loading || !auth || !selectedBinary || activeJob} style={{ flex: 1, padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>▶ Start Fuzz</button>
                <button onClick={stopFuzz} disabled={!activeJob} style={{ flex: 1, padding: '8px 0', background: '#1a1a1a', color: '#888', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>■ Stop</button>
              </div>
              <button onClick={checkDefenses} disabled={loading || !auth || !selectedBinary} style={{ width: '100%', marginTop: 8, padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>🛡 Analyser Défenses</button>
              <button onClick={searchCVE} disabled={loading || !auth} style={{ width: '100%', marginTop: 8, padding: '8px 0', background: '#1e1e3a', color: '#b0b0ff', border: '1px solid #3a3a6e', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>🔎 CVE Search</button>
            </div>
          </div>

          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Statut Fuzzing {activeJob && <span style={{ fontSize: 11, color: '#4fc3f7' }}>⟳ Live</span>}</h4>
            {currentJob ? (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
                  {[
                    { label: 'Coverage', value: `${currentJob.coverage_percent || 0}%`, color: '#7fff7f' },
                    { label: 'Paths', value: (currentJob.execution_paths || 0).toLocaleString(), color: '#7fc4ff' },
                    { label: 'Crashs', value: currentJob.crash_count || 0, color: '#ff7070' },
                    { label: 'Speed', value: `${currentJob.exec_speed || 0}/s`, color: '#ffb84d' },
                  ].map(m => (
                    <div key={m.label} style={{ background: '#0d0d0d', border: '1px solid #222', borderRadius: 4, padding: 12, textAlign: 'center' }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: m.color }}>{m.value}</div>
                      <div style={{ fontSize: 11, color: '#888' }}>{m.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{ background: '#0d0d0d', border: '1px solid #222', borderRadius: 4, padding: 8, marginBottom: 8 }}>
                  <div style={{ height: 8, background: '#1a1a1a', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${currentJob.coverage_percent || 0}%`, background: 'linear-gradient(90deg, #ff6b35, #ffa500)', borderRadius: 4, transition: 'width 0.5s' }} />
                  </div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                    <span>Statut: <span style={{ color: currentJob.status === 'running' ? '#7fff7f' : '#ff7070' }}>{currentJob.status}</span></span>
                    <span>Task: {currentJob.task_id?.slice(0, 12)}</span>
                  </div>
                </div>
                {(currentJob.crashes || []).map((c, i) => (
                  <div key={i} style={{ background: '#1e0d0d', border: '1px solid #5d2e2e', borderRadius: 4, padding: 10, marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#ff7070', fontSize: 12, fontWeight: 600 }}>{c.crash_type}</span>
                    <span style={{ fontSize: 11, color: '#888' }}>{c.signal} @ {c.address}</span>
                    <span style={{ fontSize: 10, color: c.exploitable ? '#ff7070' : '#888', background: c.exploitable ? '#3e1e1e' : '#1a1a1a', padding: '2px 6px', borderRadius: 3 }}>{c.exploitable ? '💀 EXPLOITABLE' : 'DOS'}</span>
                    <span style={{ fontSize: 11, color: '#ffa500' }}>CVSS {c.cvss_base}</span>
                    <button onClick={() => genPoC(c)} disabled={!auth} style={{ fontSize: 11, padding: '3px 8px', background: '#3e1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 3, cursor: 'pointer' }}>PoC</button>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: '#555', fontSize: 13 }}>Aucun job actif. Sélectionner un binaire et démarrer AFL++.</p>
            )}
          </div>
        </div>
      )}

      {tab === 'crashes' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Triage des Crashs</h4>
          {currentJob?.crashes?.length > 0 ? currentJob.crashes.map((c, i) => (
            <div key={i} style={{ background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16, marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ color: '#ff7070', fontWeight: 700, fontSize: 14 }}>#{i + 1} — {c.crash_type}</span>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3, background: c.severity === 'CRITICAL' ? '#5d1e1e' : '#3e2a1e', color: c.severity === 'CRITICAL' ? '#ff4444' : '#ffa500' }}>{c.severity}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, fontSize: 12 }}>
                <span style={{ color: '#aaa' }}>Signal: <b style={{ color: '#fff' }}>{c.signal}</b></span>
                <span style={{ color: '#aaa' }}>Adresse: <b style={{ color: '#7fc4ff' }}>{c.address}</b></span>
                <span style={{ color: '#aaa' }}>CVSS: <b style={{ color: '#ffa500' }}>{c.cvss_base}</b></span>
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                <button onClick={() => genPoC(c)} disabled={!auth} style={{ padding: '6px 14px', background: '#3e1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>🎯 Générer PoC</button>
              </div>
            </div>
          )) : <p style={{ color: '#555', fontSize: 13 }}>Démarrez un fuzzing pour voir les crashs.</p>}
        </div>
      )}

      {tab === 'analysis' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Analyse CVE / Rapport</h4>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
            <button onClick={searchCVE} disabled={loading || !auth} style={{ padding: '8px 16px', background: '#1e1e3a', color: '#b0b0ff', border: '1px solid #3a3a6e', borderRadius: 4, cursor: 'pointer' }}>🔎 Recherche CVE</button>
            {activeJob && <button onClick={() => act(async () => { const r = await apiFetch('/zeroday/report', { method: 'POST', body: { campaign_id: activeJob, authorization_confirmed: auth } }); setResult(r) })} disabled={loading || !auth} style={{ padding: '8px 16px', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>📄 Rapport</button>}
          </div>
        </div>
      )}

      {(loading || result) && (
        <div style={{ marginTop: 16, background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 400 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
