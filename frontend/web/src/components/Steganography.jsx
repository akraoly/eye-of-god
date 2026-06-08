import { useState } from 'react'
import { apiFetch } from '../utils/auth'

export default function Steganography() {
  const [tab, setTab] = useState('image')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  // Image
  const [imgPath, setImgPath] = useState('')
  const [imgMsg, setImgMsg] = useState('')
  const [imgPass, setImgPass] = useState('')
  const [decodeImgPath, setDecodeImgPath] = useState('')

  // Audio
  const [audioPath, setAudioPath] = useState('')
  const [audioMsg, setAudioMsg] = useState('')
  const [decodeAudioPath, setDecodeAudioPath] = useState('')

  // Network
  const [netTarget, setNetTarget] = useState('192.168.1.1')
  const [netPort, setNetPort] = useState('80')
  const [netMsg, setNetMsg] = useState('')
  const [netDomain, setNetDomain] = useState('example.com')
  const [netUrl, setNetUrl] = useState('http://example.com/')
  const [netChannel, setNetChannel] = useState('tcp')

  // Detect
  const [detectPath, setDetectPath] = useState('')

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const encodeImage = () => act(async () => {
    const r = await apiFetch('/stego/image/encode', { method: 'POST', body: { image_path: imgPath, message: imgMsg, password: imgPass || null, authorization_confirmed: auth } })
    setResult(r)
  })
  const decodeImage = () => act(async () => {
    const r = await apiFetch('/stego/image/decode', { method: 'POST', body: { image_path: decodeImgPath, password: imgPass || null, authorization_confirmed: auth } })
    setResult(r)
  })
  const encodeAudio = () => act(async () => {
    const r = await apiFetch('/stego/audio/encode', { method: 'POST', body: { audio_path: audioPath, message: audioMsg, authorization_confirmed: auth } })
    setResult(r)
  })
  const decodeAudio = () => act(async () => {
    const r = await apiFetch('/stego/audio/decode', { method: 'POST', body: { audio_path: decodeAudioPath, authorization_confirmed: auth } })
    setResult(r)
  })
  const sendNet = () => act(async () => {
    let endpoint, body
    if (netChannel === 'tcp') { endpoint = '/stego/network/tcp'; body = { target_ip: netTarget, target_port: parseInt(netPort), message: netMsg, authorization_confirmed: auth } }
    else if (netChannel === 'dns') { endpoint = '/stego/network/dns'; body = { domain: netDomain, message: netMsg, authorization_confirmed: auth } }
    else { endpoint = '/stego/network/http'; body = { url: netUrl, message: netMsg, authorization_confirmed: auth } }
    const r = await apiFetch(endpoint, { method: 'POST', body })
    setResult(r)
  })
  const detectStego = () => act(async () => {
    const r = await apiFetch('/stego/detect', { method: 'POST', body: { file_path: detectPath, authorization_confirmed: auth } })
    setResult(r)
  })

  const methods = [
    { id: 'image_lsb', name: 'Image LSB', icon: '🖼', capacity: '~100KB/image', detectability: '🟢 Faible', description: 'Encode dans les bits de poids faible des pixels RGB' },
    { id: 'audio_spectrogram', name: 'Spectrogramme Audio', icon: '🎵', capacity: '~1KB/s audio', detectability: '🟢 Très faible', description: 'Encode dans le domaine fréquentiel du signal audio' },
    { id: 'tcp_timestamp', name: 'TCP Timestamp', icon: '🌐', capacity: '1 bit/paquet', detectability: '🟢 Très faible', description: 'Encode dans la parité des timestamps TCP' },
    { id: 'dns_txt', name: 'DNS TXT', icon: '🌍', capacity: '~200B/requête', detectability: '🟡 Moyen', description: 'Exfiltre en morceaux base32 via requêtes DNS TXT' },
    { id: 'http_header', name: 'HTTP Header', icon: '📡', capacity: '~500B/requête', detectability: '🟡 Moyen', description: 'Encode en base64 fragmenté dans les headers HTTP' },
  ]

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>🕵️ Stéganographie & Canaux Couverts</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>LSB Image · Spectrogramme Audio · TCP/DNS/HTTP Covert Channels</p>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Exfiltration autorisée dans le cadre du pentest</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['image', 'audio', 'network', 'detect', 'methods'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
      </div>

      {tab === 'image' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Encoder (LSB PNG/BMP)</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Image source</label>
              <input value={imgPath} onChange={e => setImgPath(e.target.value)} placeholder="./data/cover.png" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Message secret</label>
              <textarea value={imgMsg} onChange={e => setImgMsg(e.target.value)} rows={3} placeholder="Message à dissimuler..." style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'vertical' }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Mot de passe (optionnel)</label>
              <input type="password" value={imgPass} onChange={e => setImgPass(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={encodeImage} disabled={loading || !auth || !imgPath || !imgMsg} style={{ marginTop: 8, padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>🖼 Encoder dans l'image</button>
            </div>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Décoder (LSB)</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Image stéganographiée</label>
              <input value={decodeImgPath} onChange={e => setDecodeImgPath(e.target.value)} placeholder="./data/output_stego.png" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Mot de passe (si utilisé)</label>
              <input type="password" value={imgPass} onChange={e => setImgPass(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={decodeImage} disabled={loading || !auth || !decodeImgPath} style={{ marginTop: 8, padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>🔍 Décoder</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'audio' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Encoder dans Spectrogramme Audio</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Fichier audio WAV</label>
              <input value={audioPath} onChange={e => setAudioPath(e.target.value)} placeholder="./data/cover.wav" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Message secret</label>
              <textarea value={audioMsg} onChange={e => setAudioMsg(e.target.value)} rows={3} placeholder="Message dans le spectrogramme..." style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'vertical' }} />
              <button onClick={encodeAudio} disabled={loading || !auth || !audioPath || !audioMsg} style={{ marginTop: 8, padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>🎵 Encoder dans Audio</button>
            </div>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Décoder Spectrogramme</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Fichier audio stéganographié</label>
              <input value={decodeAudioPath} onChange={e => setDecodeAudioPath(e.target.value)} placeholder="./data/output_stego.wav" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={decodeAudio} disabled={loading || !auth || !decodeAudioPath} style={{ marginTop: 8, padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>🔍 Décoder</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'network' && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Canal Réseau</h4>
            <label style={{ fontSize: 12, color: '#aaa' }}>Type de canal</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6, marginBottom: 12 }}>
              {['tcp', 'dns', 'http'].map(c => (
                <label key={c} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '6px 8px', background: netChannel === c ? '#1e2a3e' : '#0d0d0d', border: `1px solid ${netChannel === c ? '#2d4a6e' : '#222'}`, borderRadius: 4 }}>
                  <input type="radio" name="channel" value={c} checked={netChannel === c} onChange={() => setNetChannel(c)} />
                  <span style={{ color: '#fff', textTransform: 'uppercase', fontSize: 12 }}>{c}</span>
                </label>
              ))}
            </div>
            <label style={{ fontSize: 12, color: '#aaa' }}>Message à exfiltrer</label>
            <textarea value={netMsg} onChange={e => setNetMsg(e.target.value)} rows={4} placeholder="Données à exfiltrer..." style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'none', marginTop: 4, boxSizing: 'border-box' }} />
            <button onClick={sendNet} disabled={loading || !auth || !netMsg} style={{ width: '100%', marginTop: 10, padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>📡 Envoyer via canal caché</button>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Paramètres du Canal</h4>
            {netChannel === 'tcp' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ fontSize: 12, color: '#aaa' }}>IP cible</label>
                <input value={netTarget} onChange={e => setNetTarget(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
                <label style={{ fontSize: 12, color: '#aaa' }}>Port</label>
                <input value={netPort} onChange={e => setNetPort(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
                <div style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 10, fontSize: 12, color: '#888', marginTop: 8 }}>
                  Encode chaque bit dans la parité des TCP timestamps. Indétectable par DPI standard.
                </div>
              </div>
            )}
            {netChannel === 'dns' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ fontSize: 12, color: '#aaa' }}>Domaine contrôlé</label>
                <input value={netDomain} onChange={e => setNetDomain(e.target.value)} placeholder="c2.attacker.com" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
                <div style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 10, fontSize: 12, color: '#888', marginTop: 8 }}>
                  Fragmente le message en chunks base32, envoie comme sous-domaines DNS TXT.
                </div>
              </div>
            )}
            {netChannel === 'http' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ fontSize: 12, color: '#aaa' }}>URL cible</label>
                <input value={netUrl} onChange={e => setNetUrl(e.target.value)} placeholder="http://example.com/resource" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
                <div style={{ background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: 4, padding: 10, fontSize: 12, color: '#888', marginTop: 8 }}>
                  Encode le message en base64 dans les headers X-Custom-* HTTP. Ressemble à du trafic légitime.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'detect' && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, maxWidth: 600 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Détection Stéganalyse</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: 12, color: '#aaa' }}>Fichier à analyser (image)</label>
            <input value={detectPath} onChange={e => setDetectPath(e.target.value)} placeholder="./data/suspect.png" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
            <button onClick={detectStego} disabled={loading || !auth || !detectPath} style={{ padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', marginTop: 4 }}>🔬 Analyser Stéganalyse LSB</button>
          </div>
          {result?.stego_detected !== undefined && (
            <div style={{ marginTop: 16, background: result.stego_detected ? '#1a0d0d' : '#0d1a0d', border: `1px solid ${result.stego_detected ? '#5d2e2e' : '#2d5a2d'}`, borderRadius: 6, padding: 16 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: result.stego_detected ? '#ff7070' : '#7fff7f', marginBottom: 8 }}>
                {result.stego_detected ? '⚠️ STÉGANOGRAPHIE DÉTECTÉE' : '✅ Aucune stéganographie détectée'}
              </div>
              <div style={{ fontSize: 12, color: '#888' }}>Confiance: {Math.round((result.confidence || 0) * 100)}%</div>
              {result.indicators?.map((ind, i) => (
                <div key={i} style={{ fontSize: 12, color: '#ffa500', marginTop: 4 }}>• {ind}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'methods' && (
        <div>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Méthodes Disponibles</h4>
          <div style={{ display: 'grid', gap: 10 }}>
            {methods.map(m => (
              <div key={m.id} style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <span style={{ fontSize: 20 }}>{m.icon}</span>
                    <span style={{ fontWeight: 700, color: '#fff', fontSize: 14 }}>{m.name}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <span style={{ fontSize: 12, color: '#888' }}>Cap: <b style={{ color: '#ffa500' }}>{m.capacity}</b></span>
                    <span style={{ fontSize: 12 }}>{m.detectability}</span>
                  </div>
                </div>
                <p style={{ color: '#888', fontSize: 12, margin: 0 }}>{m.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {(loading || (result && tab !== 'detect')) && (
        <div style={{ marginTop: 16, background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 300 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
