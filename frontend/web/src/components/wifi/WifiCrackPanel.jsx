import React, { useState, useEffect } from 'react'
import { apiFetch } from '../../utils/auth'

const TABS = ['Handshake', 'PMKID', 'WPS', 'Evil Twin', 'Connect', 'Post-Exploit', 'Automation', 'Agent']

export default function WifiCrackPanel() {
  const [tab,       setTab]       = useState('Handshake')
  const [networks,  setNetworks]  = useState([])
  const [handshakes,setHandshakes]= useState([])
  const [jobs,      setJobs]      = useState([])
  const [conns,     setConns]     = useState([])
  const [result,    setResult]    = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [log,       setLog]       = useState([])

  // Forms
  const [hsForm,   setHsForm]   = useState({ interface: 'wlan0', bssid: '', ssid: '', channel: 6, timeout: 60 })
  const [pmForm,   setPmForm]   = useState({ interface: 'wlan0', bssid: '', ssid: '' })
  const [wpsForm,  setWpsForm]  = useState({ interface: 'wlan0', bssid: '', channel: 6 })
  const [etForm,   setEtForm]   = useState({ interface: 'wlan0', ssid: '', bssid_victim: '', channel: 6 })
  const [crackForm,setCrackForm]= useState({ bssid: '', ssid: '', hs_id: '', wordlist: '' })
  const [connForm, setConnForm] = useState({ ssid: '', passphrase: '', interface: 'wlan0' })
  const [postForm, setPostForm] = useState({ gateway: '', ip: '' })
  const [autoForm, setAutoForm] = useState({ interface: 'wlan0', target_bssid: '', scan_duration: 30 })
  const [agentMsg, setAgentMsg] = useState('')
  const [agentHistory, setAgentHistory] = useState([])

  const addLog = (msg, type = 'info') =>
    setLog(prev => [{ time: new Date().toLocaleTimeString(), msg, type }, ...prev].slice(0, 100))

  useEffect(() => {
    loadNetworks(); loadHandshakes(); loadJobs(); loadConns()
    // Ecouter les events de WifiDashboard (sélection d'un réseau)
    const handler = e => {
      const net = e.detail
      if (net) {
        setHsForm(f  => ({ ...f,  bssid: net.bssid, ssid: net.ssid || '', channel: net.channel || 6 }))
        setWpsForm(f => ({ ...f,  bssid: net.bssid, channel: net.channel || 6 }))
        setEtForm(f  => ({ ...f,  ssid: net.ssid || '', bssid_victim: net.bssid, channel: net.channel || 6 }))
        setCrackForm(f => ({ ...f, bssid: net.bssid, ssid: net.ssid || '' }))
        addLog(`Cible importée depuis le scanner : ${net.ssid || net.bssid}`, 'info')
      }
    }
    window.addEventListener('wifi-attack', handler)
    return () => window.removeEventListener('wifi-attack', handler)
  }, [])

  async function loadNetworks() {
    try { const r = await apiFetch('/wifi/networks?limit=100'); const d = await r.json(); setNetworks(d.networks || []) } catch {}
  }
  async function loadHandshakes() {
    try { const r = await apiFetch('/wifi/handshakes'); const d = await r.json(); setHandshakes(d.handshakes || []) } catch {}
  }
  async function loadJobs() {
    try { const r = await apiFetch('/wifi/crack/jobs'); const d = await r.json(); setJobs(d.jobs || []) } catch {}
  }
  async function loadConns() {
    try { const r = await apiFetch('/wifi/connections'); const d = await r.json(); setConns(d.connections || []) } catch {}
  }

  async function post(path, body) {
    setLoading(true); setResult(null)
    try {
      const r = await apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const d = await r.json()
      setResult(d)
      if (d.status === 'cracked') addLog(`✅ CRACKÉ : ${d.ssid || body.ssid} → ${d.passphrase}`, 'success')
      else if (d.status === 'captured') addLog(`📦 Capturé : ${d.ssid || body.ssid}`, 'success')
      else if (d.status === 'connected') addLog(`🔗 Connecté : ${body.ssid}`, 'success')
      else if (d.status === 'error') addLog(`❌ Erreur : ${d.error}`, 'error')
      else addLog(`Réponse : ${d.status || JSON.stringify(d).slice(0, 80)}`, 'info')
      await loadHandshakes(); await loadJobs(); await loadConns()
      return d
    } catch (e) {
      addLog(`Erreur : ${e.message}`, 'error')
    } finally { setLoading(false) }
  }

  async function sendAgent() {
    if (!agentMsg.trim()) return
    const msg = agentMsg; setAgentMsg('')
    setAgentHistory(h => [...h, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const r = await apiFetch('/wifi/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: agentHistory }),
      })
      const d = await r.json()
      setAgentHistory(h => [...h, { role: 'assistant', content: d.response }])
    } catch (e) {
      setAgentHistory(h => [...h, { role: 'assistant', content: `Erreur : ${e.message}` }])
    } finally { setLoading(false) }
  }

  const inputStyle = { background: '#111', border: '1px solid #333', color: '#ccc', padding: '6px 10px', borderRadius: 4, fontSize: 12, width: '100%', boxSizing: 'border-box' }
  const labelStyle = { fontSize: 11, color: '#666', marginBottom: 3, display: 'block' }
  const fieldStyle = { marginBottom: 10 }
  const BtnRun = ({ onClick, label = 'Lancer', color = '#44aaff' }) => (
    <button onClick={onClick} disabled={loading} style={{ padding: '8px 20px', background: loading ? '#333' : color, border: 'none', borderRadius: 4, color: loading ? '#666' : '#000', fontWeight: 700, cursor: 'pointer', fontSize: 12 }}>
      {loading ? '⏳…' : label}
    </button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0d0d0d', color: '#ccc', fontFamily: 'monospace' }}>
      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #222', overflow: 'auto', flexShrink: 0 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 14px', background: 'none', border: 'none',
            color: tab === t ? '#44aaff' : '#666', cursor: 'pointer', fontSize: 11,
            borderBottom: tab === t ? '2px solid #44aaff' : 'none', whiteSpace: 'nowrap',
          }}>{t}</button>
        ))}
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Panel principal */}
        <div style={{ flex: 1, padding: 16, overflowY: 'auto' }}>

          {/* ── Handshake ── */}
          {tab === 'Handshake' && (
            <div>
              <div style={fTitle}>⚡ Capture Handshake 4-way</div>
              <p style={fDesc}>Envoie des frames deauth pour forcer la reconnexion et capturer le handshake WPA2.</p>
              <NetworkSelect networks={networks} onSelect={n => setHsForm(f => ({ ...f, bssid: n.bssid, ssid: n.ssid || '', channel: n.channel || 6 }))} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
                {[['Interface', 'interface'], ['BSSID', 'bssid'], ['SSID', 'ssid'], ['Canal', 'channel'], ['Timeout (s)', 'timeout']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}>
                    <label style={labelStyle}>{l}</label>
                    <input style={inputStyle} value={hsForm[k]} onChange={e => setHsForm(f => ({ ...f, [k]: e.target.value }))} />
                  </div>
                ))}
              </div>
              <BtnRun label="🎯 Capturer Handshake" onClick={() => post('/api/wifi/crack/handshake', hsForm)} />
              {handshakes.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={sectionTitle}>Handshakes capturés</div>
                  {handshakes.slice(0, 10).map(h => (
                    <div key={h.hs_id} style={rowStyle}>
                      <span style={{ color: '#ddd' }}>{h.ssid}</span>
                      <span style={{ color: '#666', fontSize: 11 }}>{h.bssid}</span>
                      <span style={{ color: h.passphrase ? '#44ff88' : '#888', fontSize: 11 }}>
                        {h.passphrase || h.status}
                      </span>
                      <button style={smallBtn} onClick={() => { setCrackForm(f => ({ ...f, bssid: h.bssid, ssid: h.ssid, hs_id: h.hs_id })); setTab('Handshake') }}>
                        Craquer
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── PMKID ── */}
          {tab === 'PMKID' && (
            <div>
              <div style={fTitle}>🔑 Capture PMKID</div>
              <p style={fDesc}>Capture le PMKID sans client connecté — plus rapide et plus discret que le handshake.</p>
              <NetworkSelect networks={networks} onSelect={n => setPmForm(f => ({ ...f, bssid: n.bssid, ssid: n.ssid || '' }))} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
                {[['Interface', 'interface'], ['BSSID', 'bssid'], ['SSID', 'ssid']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} value={pmForm[k]} onChange={e => setPmForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                ))}
              </div>
              <BtnRun label="📡 Capturer PMKID" onClick={() => post('/api/wifi/crack/pmkid', pmForm)} />
              <div style={{ marginTop: 16 }}>
                <div style={sectionTitle}>Lancer le cracking sur le PMKID</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {[['BSSID', 'bssid'], ['SSID', 'ssid'], ['Wordlist', 'wordlist']].map(([l, k]) => (
                    <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} value={crackForm[k]} onChange={e => setCrackForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                  ))}
                </div>
                <BtnRun label="🔨 Hashcat" color="#ff8800" onClick={() => post('/api/wifi/crack/start', crackForm)} />
              </div>
            </div>
          )}

          {/* ── WPS ── */}
          {tab === 'WPS' && (
            <div>
              <div style={fTitle}>📌 WPS Pixie Dust Attack</div>
              <p style={fDesc}>Exploite la vulnérabilité WPS Pixie Dust pour obtenir le PIN puis la passphrase.</p>
              <NetworkSelect networks={networks.filter(n => n.wps_enabled)} onSelect={n => setWpsForm(f => ({ ...f, bssid: n.bssid, channel: n.channel || 6 }))} label="Réseaux WPS détectés" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
                {[['Interface', 'interface'], ['BSSID', 'bssid'], ['Canal', 'channel']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} value={wpsForm[k]} onChange={e => setWpsForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                ))}
              </div>
              <BtnRun label="💥 Pixie Dust" color="#ff4444" onClick={() => post('/api/wifi/wps/attack', wpsForm)} />
              {jobs.filter(j => j.method === 'wps_pixiedust').length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={sectionTitle}>Historique WPS</div>
                  {jobs.filter(j => j.method === 'wps_pixiedust').slice(0, 5).map(j => (
                    <div key={j.job_id} style={rowStyle}>
                      <span>{j.bssid}</span>
                      <span style={{ color: j.result ? '#44ff88' : '#888' }}>{j.result || j.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Evil Twin ── */}
          {tab === 'Evil Twin' && (
            <div>
              <div style={fTitle}>👥 Evil Twin / Rogue AP</div>
              <p style={fDesc}>Crée un faux AP identique à la cible pour capturer les identifiants WiFi.</p>
              <div style={{ padding: 10, background: '#1a0000', border: '1px solid #ff4444', borderRadius: 4, marginBottom: 12, fontSize: 11, color: '#ff8888' }}>
                ⚠️ Usage exclusivement légal — pentest autorisé uniquement.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[['Interface', 'interface'], ['SSID victime', 'ssid'], ['BSSID victime', 'bssid_victim'], ['Canal', 'channel']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} value={etForm[k]} onChange={e => setEtForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                ))}
              </div>
              <BtnRun label="🎭 Démarrer Evil Twin" color="#ff4444" onClick={() => post('/api/wifi/eviltwin/start', etForm)} />
            </div>
          )}

          {/* ── Connect ── */}
          {tab === 'Connect' && (
            <div>
              <div style={fTitle}>🔗 Connexion WiFi</div>
              <p style={fDesc}>Se connecter à un réseau avec une passphrase (obtenue par cracking ou connue).</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[['SSID', 'ssid'], ['Passphrase', 'passphrase'], ['Interface', 'interface']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} type={k === 'passphrase' ? 'password' : 'text'} value={connForm[k]} onChange={e => setConnForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                ))}
              </div>
              <BtnRun label="🔗 Connecter" color="#44ff88" onClick={() => post('/api/wifi/connect', connForm)} />
              {conns.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={sectionTitle}>Historique connexions</div>
                  {conns.slice(0, 5).map(c => (
                    <div key={c.conn_id} style={rowStyle}>
                      <span>{c.ssid}</span>
                      <span style={{ fontSize: 11, color: '#888' }}>{c.local_ip}</span>
                      <span style={{ color: c.status === 'connected' ? '#44ff88' : '#888', fontSize: 11 }}>{c.status}</span>
                      {c.status === 'connected' && <button style={smallBtn} onClick={() => { setPostForm(f => ({ ...f, gateway: c.gateway })); setTab('Post-Exploit') }}>Post-exploit</button>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Post-Exploit ── */}
          {tab === 'Post-Exploit' && (
            <div>
              <div style={fTitle}>🕵️ Post-Exploitation réseau</div>
              <p style={fDesc}>Scanner le réseau local après connexion — découverte d'hôtes, ports, SMB.</p>
              <div style={fieldStyle}><label style={labelStyle}>Gateway (ex: 192.168.1.1)</label><input style={inputStyle} value={postForm.gateway} onChange={e => setPostForm(f => ({ ...f, gateway: e.target.value }))} /></div>
              <BtnRun label="🔍 Scanner réseau (ARP)" onClick={async () => {
                const d = await post(`/api/wifi/connected/scan?gateway=${postForm.gateway}`, {})
                if (d?.hosts) setResult(d)
              }} />
              {result?.hosts && (
                <div style={{ marginTop: 12 }}>
                  <div style={sectionTitle}>{result.hosts.length} hôte(s) découvert(s)</div>
                  {result.hosts.map((h, i) => (
                    <div key={i} style={rowStyle}>
                      <span style={{ color: '#44aaff', fontFamily: 'monospace' }}>{h.ip}</span>
                      <span style={{ color: '#888', fontSize: 11 }}>{h.hostname || ''}</span>
                      <span style={{ color: '#666', fontSize: 11 }}>{h.vendor || ''}</span>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button style={smallBtn} onClick={() => { setPostForm(f => ({ ...f, ip: h.ip })); post(`/api/wifi/connected/host/${h.ip}/scan`, {}) }}>Ports</button>
                        <button style={smallBtn} onClick={() => post(`/api/wifi/connected/host/${h.ip}/smb`, {})}>SMB</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Automation ── */}
          {tab === 'Automation' && (
            <div>
              <div style={fTitle}>🤖 Workflow automatisé</div>
              <p style={fDesc}>Pipeline complet : Scan → WPS → Handshake → Crack → Connexion → ARP scan → Rapport.</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[['Interface', 'interface'], ['BSSID cible (optionnel)', 'target_bssid'], ['Durée scan (s)', 'scan_duration']].map(([l, k]) => (
                  <div key={k} style={fieldStyle}><label style={labelStyle}>{l}</label><input style={inputStyle} value={autoForm[k]} onChange={e => setAutoForm(f => ({ ...f, [k]: e.target.value }))} /></div>
                ))}
              </div>
              <BtnRun label="🚀 Lancer workflow" color="#ff8800" onClick={() => post('/api/wifi/automation/run', autoForm)} />
              {result?.log && (
                <div style={{ marginTop: 12, maxHeight: 300, overflowY: 'auto', background: '#0a0a0a', padding: 8, borderRadius: 4 }}>
                  {result.log.map((l, i) => (
                    <div key={i} style={{ fontSize: 11, padding: '2px 0', color: '#ccc' }}>
                      <span style={{ color: '#555' }}>{l.time?.slice(11, 19)} </span>{l.msg}
                    </div>
                  ))}
                </div>
              )}
              {result?.cracked?.length > 0 && (
                <div style={{ marginTop: 12, background: '#001a00', border: '1px solid #44ff88', borderRadius: 4, padding: 10 }}>
                  <div style={{ color: '#44ff88', fontWeight: 700, marginBottom: 8 }}>✅ {result.cracked.length} réseau(x) cracké(s)</div>
                  {result.cracked.map((c, i) => (
                    <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>
                      {c.ssid} : <span style={{ color: '#44ff88', fontFamily: 'monospace' }}>{c.passphrase || '(ouvert)'}</span>
                      <span style={{ color: '#666', fontSize: 10, marginLeft: 8 }}>via {c.method}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Agent ── */}
          {tab === 'Agent' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={fTitle}>🤖 Agent IA WiFi</div>
              <div style={{ flex: 1, overflowY: 'auto', marginBottom: 12, minHeight: 200, maxHeight: 400, background: '#0a0a0a', borderRadius: 4, padding: 8 }}>
                {agentHistory.length === 0 && (
                  <div style={{ color: '#444', fontSize: 12, padding: 8 }}>
                    Exemples : "Scanne les réseaux sur wlan0", "Attaque le réseau SFR_B342", "Explique les résultats du scan"
                  </div>
                )}
                {agentHistory.map((m, i) => (
                  <div key={i} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: '#555', marginBottom: 2 }}>{m.role === 'user' ? '👤 Toi' : '🤖 Agent WiFi'}</div>
                    <div style={{ fontSize: 12, color: m.role === 'user' ? '#ccc' : '#44aaff', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{m.content}</div>
                  </div>
                ))}
                {loading && <div style={{ color: '#666', fontSize: 12 }}>⏳ Analyse en cours…</div>}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input style={{ ...inputStyle, flex: 1 }} value={agentMsg}
                  onChange={e => setAgentMsg(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendAgent()}
                  placeholder="Demande à l'agent WiFi…" />
                <button onClick={sendAgent} disabled={loading} style={{ padding: '6px 16px', background: '#44aaff', border: 'none', borderRadius: 4, color: '#000', fontWeight: 700, cursor: 'pointer', fontSize: 12 }}>
                  Envoyer
                </button>
              </div>
            </div>
          )}

          {/* Résultat JSON */}
          {result && tab !== 'Automation' && tab !== 'Agent' && (
            <ResultBox result={result} />
          )}
        </div>

        {/* Log panel */}
        <div style={{ width: 240, borderLeft: '1px solid #1a1a1a', overflowY: 'auto', background: '#080808' }}>
          <div style={{ padding: '6px 10px', fontSize: 11, color: '#555', borderBottom: '1px solid #1a1a1a' }}>Journal</div>
          {log.map((l, i) => (
            <div key={i} style={{ padding: '3px 8px', fontSize: 10, borderBottom: '1px solid #0d0d0d', lineHeight: 1.4 }}>
              <span style={{ color: '#444' }}>{l.time} </span>
              <span style={{ color: l.type === 'error' ? '#ff4444' : l.type === 'success' ? '#44ff88' : '#888' }}>{l.msg}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function NetworkSelect({ networks, onSelect, label = 'Sélectionner un réseau' }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ fontSize: 11, color: '#666', marginBottom: 3, display: 'block' }}>{label}</label>
      <select onChange={e => onSelect(networks[+e.target.value])}
        style={{ background: '#111', border: '1px solid #333', color: '#ccc', padding: '5px 8px', borderRadius: 4, fontSize: 11, width: '100%' }}>
        <option value="">— Choisir —</option>
        {networks.map((n, i) => (
          <option key={i} value={i}>{n.ssid || 'Hidden'} ({n.bssid}) {n.wps_enabled ? '[WPS]' : ''}</option>
        ))}
      </select>
    </div>
  )
}

function ResultBox({ result }) {
  const good = result?.status === 'cracked' || result?.status === 'connected' || result?.status === 'captured'
  return (
    <div style={{ marginTop: 16, padding: 10, background: good ? '#001a00' : '#111', border: `1px solid ${good ? '#44ff88' : '#333'}`, borderRadius: 4 }}>
      <div style={{ fontSize: 11, color: good ? '#44ff88' : '#666', fontWeight: 700, marginBottom: 6 }}>
        {good ? '✅ Succès' : 'Résultat'}
      </div>
      {result.passphrase && <div style={{ fontSize: 14, color: '#44ff88', fontFamily: 'monospace', marginBottom: 6 }}>Passphrase : {result.passphrase}</div>}
      {result.local_ip   && <div style={{ fontSize: 12, color: '#44aaff', fontFamily: 'monospace', marginBottom: 4 }}>IP locale : {result.local_ip} / GW : {result.gateway}</div>}
      <pre style={{ fontSize: 10, color: '#666', margin: 0, overflowX: 'auto', maxHeight: 200 }}>
        {JSON.stringify(result, null, 2)}
      </pre>
    </div>
  )
}

const fTitle       = { fontSize: 15, fontWeight: 700, color: '#44aaff', marginBottom: 6 }
const fDesc        = { fontSize: 11, color: '#666', marginBottom: 12, lineHeight: 1.5 }
const sectionTitle = { fontSize: 12, color: '#ff8800', marginBottom: 8, fontWeight: 700 }
const rowStyle     = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #1a1a1a', gap: 8 }
const smallBtn     = { padding: '3px 8px', background: '#1a2233', border: '1px solid #44aaff55', color: '#44aaff', borderRadius: 3, cursor: 'pointer', fontSize: 10 }
