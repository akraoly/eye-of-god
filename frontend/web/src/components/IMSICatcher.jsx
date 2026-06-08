import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

export default function IMSICatcher() {
  const [tab, setTab] = useState('hardware')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [hardware, setHardware] = useState(null)
  const [sessions, setSessions] = useState([])
  const [activeBTS, setActiveBTS] = useState(null)
  const [phones, setPhones] = useState([])
  const [selectedPhone, setSelectedPhone] = useState(null)
  const [capturedSMS, setCapturedSMS] = useState([])
  const [injectMsg, setInjectMsg] = useState('')
  const [spoofFrom, setSpoofFrom] = useState('')
  const [band, setBand] = useState('900')
  const [mcc, setMcc] = useState('208')
  const [mnc, setMnc] = useState('01')
  const pollRef = useRef(null)

  useEffect(() => {
    checkHW(); loadSessions()
  }, [])

  useEffect(() => {
    if (activeBTS) {
      pollRef.current = setInterval(pollPhones, 5000)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [activeBTS])

  const checkHW = async () => { const r = await apiFetch('/imsi/hardware'); setHardware(r) }
  const loadSessions = async () => { const r = await apiFetch('/imsi/sessions'); if (Array.isArray(r)) setSessions(r) }
  const pollPhones = async () => {
    if (!activeBTS) return
    const r = await apiFetch(`/imsi/phones/${activeBTS}`)
    if (Array.isArray(r)) setPhones(r)
  }

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const startBTS = () => act(async () => {
    const r = await apiFetch('/imsi/bts/start', { method: 'POST', body: { band, operator_mcc: mcc, operator_mnc: mnc, authorization_confirmed: auth } })
    setResult(r)
    if (r.bts_id) { setActiveBTS(r.bts_id); loadSessions(); setTab('capture') }
  })

  const stopBTS = () => act(async () => {
    if (!activeBTS) return
    const r = await apiFetch('/imsi/bts/stop', { method: 'POST', body: { bts_id: activeBTS, authorization_confirmed: auth } })
    setResult(r); setActiveBTS(null); setPhones([]); loadSessions()
  })

  const captureSMS = () => act(async () => {
    if (!activeBTS || !selectedPhone) return
    const r = await apiFetch('/imsi/sms/capture', { method: 'POST', body: { bts_id: activeBTS, target_imsi: selectedPhone.imsi, duration: 60, authorization_confirmed: auth } })
    if (Array.isArray(r)) setCapturedSMS(r)
    setResult(r)
  })

  const injectSMS = () => act(async () => {
    if (!activeBTS || !selectedPhone) return
    const r = await apiFetch('/imsi/sms/inject', { method: 'POST', body: { bts_id: activeBTS, target_imsi: selectedPhone.imsi, message: injectMsg, spoof_from: spoofFrom || null, authorization_confirmed: auth } })
    setResult(r)
  })

  const locatePhone = () => act(async () => {
    if (!activeBTS || !selectedPhone) return
    const r = await apiFetch('/imsi/locate', { method: 'POST', body: { bts_id: activeBTS, target_imsi: selectedPhone.imsi, authorization_confirmed: auth } })
    setResult(r)
  })

  const detectStingray = () => act(async () => {
    const r = await apiFetch('/imsi/stingray/detect', { method: 'POST', body: { authorization_confirmed: auth } })
    setResult(r)
  })

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>📡 IMSI Catcher — Fake BTS GSM</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>YateBTS/OpenBTS · HackRF · Capture IMSI/TMSI · SMS intercept</p>
      <div style={{ background: '#1a0a0a', border: '1px solid #5d2e2e', borderRadius: 4, padding: '6px 12px', marginBottom: 16, fontSize: 12, color: '#ff7070' }}>
        ⚠ ILLÉGAL sans autorisation. Uniquement en laboratoire blindé Faraday pour audits légaux.
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Opération en laboratoire blindé, autorisation légale confirmée</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {['hardware', 'config', 'capture', 'sms', 'defense'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
      </div>

      {tab === 'hardware' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Hardware SDR</h4>
            {hardware ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'SDR Hardware', value: hardware.sdr_hardware, ok: hardware.hardware_ready },
                  { label: 'Logiciel BTS', value: hardware.bts_software, ok: hardware.bts_software },
                  { label: 'Antenne GSM', value: hardware.gsm_antenna, ok: true },
                  { label: 'Bandes supportées', value: (hardware.bands_supported || []).join(', '), ok: hardware.bands_supported?.length > 0 },
                ].map(item => (
                  <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #1a1a1a' }}>
                    <span style={{ fontSize: 12, color: '#888' }}>{item.label}</span>
                    <span style={{ fontSize: 12, color: item.ok ? '#7fff7f' : '#ff7070' }}>{item.value || 'N/D'}</span>
                  </div>
                ))}
                {hardware.simulation && <span style={{ fontSize: 11, color: '#ffa500', marginTop: 8 }}>MODE SIMULATION</span>}
              </div>
            ) : <p style={{ color: '#555', fontSize: 13 }}>Vérification en cours...</p>}
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Sessions Actives ({sessions.length})</h4>
            {sessions.map(s => (
              <div key={s.bts_id} style={{ background: '#0d0d0d', border: '1px solid #2d5a2d', borderRadius: 4, padding: 10, marginBottom: 8 }}>
                <div style={{ color: '#7fff7f', fontSize: 13, fontWeight: 600 }}>{s.bts_id}</div>
                <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{s.band} · MCC{s.mcc}/MNC{s.mnc} · {s.phones_connected} téléphones</div>
              </div>
            ))}
            {sessions.length === 0 && <p style={{ color: '#555', fontSize: 13 }}>Aucune session BTS active.</p>}
          </div>
        </div>
      )}

      {tab === 'config' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 500 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Configuration BTS</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 12, color: '#aaa' }}>Bande GSM</label>
            <select value={band} onChange={e => setBand(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }}>
              <option value="900">GSM 900 MHz</option>
              <option value="1800">DCS 1800 MHz</option>
            </select>
            <label style={{ fontSize: 12, color: '#aaa' }}>MCC (Mobile Country Code)</label>
            <input value={mcc} onChange={e => setMcc(e.target.value)} placeholder="208 (France)" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <label style={{ fontSize: 12, color: '#aaa' }}>MNC (Mobile Network Code)</label>
            <input value={mnc} onChange={e => setMnc(e.target.value)} placeholder="01 (Orange)" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button onClick={startBTS} disabled={loading || !auth || activeBTS} style={{ flex: 1, padding: '10px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>📡 Activer Fake BTS</button>
              <button onClick={stopBTS} disabled={loading || !activeBTS} style={{ flex: 1, padding: '10px 0', background: '#1a1a1a', color: '#888', border: '1px solid #333', borderRadius: 4, cursor: 'pointer' }}>■ Stopper</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'capture' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Téléphones Capturés ({phones.length})</h4>
            {phones.map((p, i) => (
              <div key={i} onClick={() => setSelectedPhone(p)} style={{ background: selectedPhone?.imsi === p.imsi ? '#1e2a1e' : '#0d0d0d', border: `1px solid ${selectedPhone?.imsi === p.imsi ? '#4caf50' : '#222'}`, borderRadius: 4, padding: 10, marginBottom: 6, cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#7fff7f', fontSize: 12, fontWeight: 600 }}>{p.imsi}</span>
                  <span style={{ fontSize: 11, color: '#ffa500' }}>{p.signal_strength_dbm} dBm</span>
                </div>
                <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{p.manufacturer} · TMSI: {p.tmsi} {p.msisdn && `· ${p.msisdn}`}</div>
              </div>
            ))}
            {phones.length === 0 && <p style={{ color: '#555', fontSize: 13 }}>En attente de connexions... {activeBTS ? `(BTS: ${activeBTS.slice(0, 12)})` : '(BTS inactive)'}</p>}
            {activeBTS && <button onClick={pollPhones} style={{ width: '100%', marginTop: 8, padding: '6px 0', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>↻ Rafraîchir</button>}
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Actions sur cible{selectedPhone && `: ${selectedPhone.imsi.slice(0, 10)}...`}</h4>
            {selectedPhone ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button onClick={captureSMS} disabled={loading || !auth} style={{ padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>📨 Capturer SMS (60s)</button>
                <button onClick={locatePhone} disabled={loading || !auth} style={{ padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>📍 Triangulation position</button>
                <button onClick={() => act(async () => { const r = await apiFetch('/imsi/calls/metadata', { method: 'POST', body: { bts_id: activeBTS, target_imsi: selectedPhone.imsi, duration: 120, authorization_confirmed: auth } }); setResult(r) })} disabled={loading || !auth} style={{ padding: '8px 0', background: '#2a1e2a', color: '#d0a0ff', border: '1px solid #5a3a5a', borderRadius: 4, cursor: 'pointer' }}>📞 Métadonnées Appels</button>
              </div>
            ) : <p style={{ color: '#555', fontSize: 13 }}>Sélectionner un téléphone.</p>}
          </div>
        </div>
      )}

      {tab === 'sms' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>SMS Interceptés ({capturedSMS.length})</h4>
            {capturedSMS.map((s, i) => (
              <div key={i} style={{ background: '#0d0d0d', border: '1px solid #333', borderRadius: 4, padding: 10, marginBottom: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 11, color: '#888' }}>{s.from} → {s.to}</span>
                  <span style={{ fontSize: 10, color: s.type === 'MT' ? '#7fc4ff' : '#7fff7f', background: '#1a1a1a', padding: '1px 5px', borderRadius: 2 }}>{s.type}</span>
                </div>
                <div style={{ fontSize: 12, color: '#fff' }}>{s.body}</div>
              </div>
            ))}
            {capturedSMS.length === 0 && <p style={{ color: '#555', fontSize: 13 }}>Aucun SMS capturé. Sélectionner une cible dans Capture →</p>}
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Injection SMS</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Cible: {selectedPhone?.imsi || 'Sélectionner dans Capture'}</label>
              <label style={{ fontSize: 12, color: '#aaa' }}>Expéditeur spoofé</label>
              <input value={spoofFrom} onChange={e => setSpoofFrom(e.target.value)} placeholder="BANQUE-FR / +33144556677" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Message</label>
              <textarea value={injectMsg} onChange={e => setInjectMsg(e.target.value)} rows={4} placeholder="Votre code OTP: 123456..." style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'vertical' }} />
              <button onClick={injectSMS} disabled={loading || !auth || !selectedPhone || !injectMsg} style={{ padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>💉 Injecter SMS</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'defense' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 600 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Détection StingRay</h4>
          <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>Analyse du spectre radio pour détecter les fausses antennes (IMSI Catchers) environnantes.</p>
          <button onClick={detectStingray} disabled={loading || !auth} style={{ padding: '10px 24px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>🔍 Scanner l'environnement</button>
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
