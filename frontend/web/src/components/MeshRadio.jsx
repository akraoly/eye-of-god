import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

export default function MeshRadio() {
  const [tab, setTab] = useState('network')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [nodes, setNodes] = useState([])
  const [messages, setMessages] = useState([])
  const [topology, setTopology] = useState(null)
  const [localNode, setLocalNode] = useState(null)
  const [activeNodes, setActiveNodes] = useState([])
  const pollRef = useRef(null)

  // Init node params
  const [devicePort, setDevicePort] = useState('/dev/ttyUSB0')
  const [nodeName, setNodeName] = useState('Alpha-1')
  const [frequency, setFrequency] = useState('868.0')

  // Messaging
  const [broadcastMsg, setBroadcastMsg] = useState('')
  const [directTarget, setDirectTarget] = useState('')
  const [directMsg, setDirectMsg] = useState('')
  const [encrypted, setEncrypted] = useState(true)
  const [lastMsgId, setLastMsgId] = useState(0)

  // File transfer
  const [ftTarget, setFtTarget] = useState('')
  const [ftFile, setFtFile] = useState('')

  useEffect(() => {
    loadNodes(); loadMessages()
  }, [])

  useEffect(() => {
    if (localNode) {
      pollRef.current = setInterval(pollMessages, 4000)
    }
    return () => clearInterval(pollRef.current)
  }, [localNode, lastMsgId])

  const loadNodes = async () => { const r = await apiFetch('/mesh/nodes'); if (Array.isArray(r)) setNodes(r) }
  const loadMessages = async () => {
    if (!localNode) {
      const r = await apiFetch('/mesh/messages/local')
      if (Array.isArray(r)) setMessages(r)
      return
    }
    const r = await apiFetch(`/mesh/messages/${localNode.node_id}`)
    if (Array.isArray(r)) { setMessages(r); if (r.length > 0) setLastMsgId(r[r.length - 1].id) }
  }
  const pollMessages = async () => { if (!localNode) return; await loadMessages() }

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const initNode = () => act(async () => {
    const r = await apiFetch('/mesh/node/init', { method: 'POST', body: { device_port: devicePort, node_name: nodeName, frequency_mhz: parseFloat(frequency), power: 20, authorization_confirmed: auth } })
    setResult(r); if (r.node_id) { setLocalNode(r); setActiveNodes(prev => [...prev, r]); loadTopology(r.node_id) }
  })

  const loadTopology = async (nid) => {
    const r = await apiFetch(`/mesh/topology/${nid || (localNode?.node_id || 'mesh_001')}`)
    if (!r.error) setTopology(r)
  }

  const sendBroadcast = () => act(async () => {
    if (!localNode || !broadcastMsg) return
    const r = await apiFetch('/mesh/broadcast', { method: 'POST', body: { node_id: localNode.node_id, message: broadcastMsg, encrypted, authorization_confirmed: auth } })
    setResult(r); setBroadcastMsg(''); loadMessages()
  })

  const sendDirect = () => act(async () => {
    if (!localNode || !directTarget || !directMsg) return
    const r = await apiFetch('/mesh/direct', { method: 'POST', body: { node_id: localNode.node_id, target_node_id: directTarget, message: directMsg, authorization_confirmed: auth } })
    setResult(r); setDirectMsg(''); loadMessages()
  })

  const sendFile = () => act(async () => {
    const r = await apiFetch('/mesh/file/transfer', { method: 'POST', body: { node_id: localNode?.node_id || 'local', target_node_id: ftTarget, file_path: ftFile, authorization_confirmed: auth } })
    setResult(r)
  })

  const scanFreqs = () => act(async () => {
    const r = await apiFetch('/mesh/scan', { method: 'POST', body: { start_mhz: 863.0, end_mhz: 870.0, authorization_confirmed: auth } })
    setResult(r)
  })

  const signalColor = (dbm) => {
    if (dbm >= -70) return '#7fff7f'
    if (dbm >= -85) return '#ffa500'
    return '#ff7070'
  }

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>📻 Mesh Radio — LoRa Off-Grid</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>LilyGO TTGO · Heltec LoRa32 · Meshtastic 2.x · 868 MHz EU</p>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Réseau mesh autorisé (fréquences ISM)</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['network', 'init', 'messages', 'transfer', 'scan'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
        {localNode && <span style={{ marginLeft: 'auto', fontSize: 12, color: '#7fff7f', alignSelf: 'center' }}>📡 {localNode.name} ({localNode.node_id.slice(0, 12)})</span>}
      </div>

      {tab === 'network' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ color: '#ff6b35', margin: 0 }}>Nœuds Mesh ({nodes.length})</h4>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={loadNodes} style={{ padding: '5px 12px', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>↻</button>
              <button onClick={() => loadTopology()} style={{ padding: '5px 12px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Topologie</button>
            </div>
          </div>
          <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
            {nodes.map(n => (
              <div key={n.node_id} style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', marginBottom: 4 }}>{n.name}</div>
                  <div style={{ fontSize: 12, color: '#888' }}>{n.node_id} · {n.frequency_mhz} MHz · {n.hops} hops</div>
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: signalColor(n.signal_dbm), fontWeight: 600 }}>{n.signal_dbm} dBm</span>
                  <button onClick={() => setDirectTarget(n.node_id)} style={{ fontSize: 11, padding: '4px 10px', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 3, cursor: 'pointer' }}>→ DM</button>
                </div>
              </div>
            ))}
          </div>
          {topology && (
            <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Topologie réseau</h4>
              <div style={{ display: 'grid', gap: 6 }}>
                {(topology.edges || []).map((e, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 12, padding: '4px 0', borderBottom: '1px solid #1a1a1a' }}>
                    <span style={{ color: '#7fc4ff', width: 120, fontWeight: 600 }}>{e.from.slice(0, 10)}</span>
                    <span style={{ color: '#555' }}>──</span>
                    <span style={{ color: signalColor(e.rssi), width: 70 }}>{e.rssi} dBm</span>
                    <span style={{ color: '#888' }}>SNR {e.snr}</span>
                    <span style={{ color: '#555' }}>──→</span>
                    <span style={{ color: '#7fff7f', fontWeight: 600 }}>{e.to.slice(0, 10)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'init' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 500 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Initialiser Nœud Local</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 12, color: '#aaa' }}>Port série</label>
            <select value={devicePort} onChange={e => setDevicePort(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }}>
              {['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1'].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <label style={{ fontSize: 12, color: '#aaa' }}>Nom du nœud</label>
            <input value={nodeName} onChange={e => setNodeName(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <label style={{ fontSize: 12, color: '#aaa' }}>Fréquence (MHz)</label>
            <select value={frequency} onChange={e => setFrequency(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }}>
              <option value="868.0">868.0 MHz (EU ISM)</option>
              <option value="868.1">868.1 MHz (EU ISM)</option>
              <option value="915.0">915.0 MHz (US ISM)</option>
              <option value="433.0">433.0 MHz (EU ISM)</option>
            </select>
            <button onClick={initNode} disabled={loading || !auth} style={{ marginTop: 8, padding: '10px 0', background: '#ff6b35', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>📡 Initialiser Nœud Mesh</button>
          </div>
          {localNode && (
            <div style={{ marginTop: 16, background: '#0d1a0d', border: '1px solid #2d5a2d', borderRadius: 4, padding: 12 }}>
              <div style={{ color: '#7fff7f', fontSize: 13, fontWeight: 600 }}>✓ Nœud actif: {localNode.name}</div>
              <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>Mesh ID: {localNode.mesh_id} · {localNode.nodes_reachable} nœuds joignables</div>
            </div>
          )}
        </div>
      )}

      {tab === 'messages' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Broadcast Réseau</h4>
              <textarea value={broadcastMsg} onChange={e => setBroadcastMsg(e.target.value)} rows={3} placeholder="Message à diffuser à tous les nœuds..." style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'none', boxSizing: 'border-box' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, cursor: 'pointer', flex: 1 }}>
                  <input type="checkbox" checked={encrypted} onChange={e => setEncrypted(e.target.checked)} />
                  <span style={{ color: encrypted ? '#7fff7f' : '#888' }}>Chiffré AES-256</span>
                </label>
                <button onClick={sendBroadcast} disabled={loading || !auth || !broadcastMsg} style={{ padding: '7px 16px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>📢 Broadcast</button>
              </div>
            </div>
            <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Message Direct</h4>
              <input value={directTarget} onChange={e => setDirectTarget(e.target.value)} placeholder="Node ID cible (mesh_001...)" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginBottom: 8, boxSizing: 'border-box' }} />
              <textarea value={directMsg} onChange={e => setDirectMsg(e.target.value)} rows={3} placeholder="Message confidentiel..." style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'none', boxSizing: 'border-box' }} />
              <button onClick={sendDirect} disabled={loading || !auth || !directTarget || !directMsg} style={{ marginTop: 8, padding: '7px 0', width: '100%', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>🔒 Envoyer DM</button>
            </div>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <h4 style={{ color: '#ff6b35', margin: 0 }}>Messagerie ({messages.length})</h4>
              <button onClick={loadMessages} style={{ padding: '4px 10px', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>↻</button>
            </div>
            <div style={{ maxHeight: 300, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {messages.map(m => (
                <div key={m.id} style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 10, borderLeft: `3px solid ${m.to === 'broadcast' ? '#4fc3f7' : '#7fff7f'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: '#7fc4ff', fontWeight: 600 }}>{m.from_name || m.from_node}</span>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {m.encrypted && <span style={{ fontSize: 10, color: '#7fff7f', background: '#0d1a0d', padding: '1px 5px', borderRadius: 2 }}>🔒</span>}
                      <span style={{ fontSize: 10, color: '#555' }}>{m.ts?.slice(11, 19)}</span>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: '#e0e0e0' }}>{m.body}</div>
                  <div style={{ fontSize: 10, color: '#555', marginTop: 4 }}>→ {m.to === 'broadcast' ? 'BROADCAST' : m.to}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'transfer' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 500 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Transfert Fichier LoRa (1200 bps)</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 12, color: '#aaa' }}>Nœud destinataire</label>
            <input value={ftTarget} onChange={e => setFtTarget(e.target.value)} placeholder="mesh_002" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <label style={{ fontSize: 12, color: '#aaa' }}>Chemin fichier</label>
            <input value={ftFile} onChange={e => setFtFile(e.target.value)} placeholder="./data/exfil.txt" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <button onClick={sendFile} disabled={loading || !auth || !ftTarget || !ftFile} style={{ marginTop: 8, padding: '10px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>📤 Transférer (fragmenté)</button>
            <div style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 10, fontSize: 12 }}>
              <div style={{ color: '#888' }}>⚠ LoRa = débit faible mais longue portée:</div>
              <div style={{ color: '#ffa500', marginTop: 4 }}>• 1 Ko ≈ 6 secondes</div>
              <div style={{ color: '#ffa500' }}>• 100 Ko ≈ 10 minutes</div>
              <div style={{ color: '#ffa500' }}>• Portée max: ~15 km (ligne de vue)</div>
            </div>
          </div>
        </div>
      )}

      {tab === 'scan' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Scanner Fréquences LoRa</h4>
          <button onClick={scanFreqs} disabled={loading || !auth} style={{ padding: '8px 20px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', marginBottom: 16 }}>🔍 Scanner 863–870 MHz</button>
          {result && Array.isArray(result) && (
            <div style={{ display: 'grid', gap: 6 }}>
              {result.map((f, i) => (
                <div key={i} style={{ background: '#0d0d0d', border: '1px solid #222', borderRadius: 4, padding: 10, display: 'flex', gap: 16, alignItems: 'center' }}>
                  <span style={{ color: '#7fc4ff', fontWeight: 600, width: 80 }}>{f.frequency_mhz} MHz</span>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: f.active ? '#7fff7f' : '#444' }} />
                  <span style={{ color: signalColor(f.rssi_dbm), width: 80 }}>{f.rssi_dbm} dBm</span>
                  {f.detected_nodes > 0 && <span style={{ fontSize: 12, color: '#888' }}>{f.detected_nodes} nœud(s)</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {(loading || (result && !Array.isArray(result))) && (
        <div style={{ marginTop: 16, background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 300 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
