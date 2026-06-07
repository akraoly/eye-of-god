/**
 * NetworkSnifferView — Capture réseau live, filtres BPF, détection creds
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const PROTO_COLORS = {
  HTTP:  '#4ade80',
  HTTPS: '#38bdf8',
  DNS:   '#60a5fa',
  SMB:   '#ef4444',
  FTP:   '#fbbf24',
  SSH:   '#a78bfa',
  TELNET:'#f97316',
  ARP:   '#94a3b8',
  ICMP:  '#64748b',
}

const PROTO_BG = Object.fromEntries(
  Object.entries(PROTO_COLORS).map(([k, v]) => [k, v + '18'])
)

const BPF_PRESETS = [
  { label: 'HTTP', filter: 'tcp port 80' },
  { label: 'DNS',  filter: 'udp port 53' },
  { label: 'FTP',  filter: 'tcp port 21' },
  { label: 'SMB',  filter: 'tcp port 445' },
  { label: 'Telnet', filter: 'tcp port 23' },
  { label: 'SSH',  filter: 'tcp port 22' },
]

function ProtoBadge({ proto }) {
  const p = (proto || '').toUpperCase()
  const color = PROTO_COLORS[p] || '#94a3b8'
  const bg    = PROTO_BG[p]    || '#94a3b818'
  return (
    <span style={{ background: bg, color, border: `1px solid ${color}40`,
      borderRadius: 4, padding: '1px 6px', fontSize: '0.6rem', fontWeight: 700, minWidth: 50, textAlign: 'center', display: 'inline-block' }}>
      {p || '???'}
    </span>
  )
}

export default function NetworkSnifferView() {
  const [interfaces,   setInterfaces]   = useState([])
  const [iface,        setIface]        = useState('')
  const [bpfFilter,    setBpfFilter]    = useState('')
  const [capturing,    setCapturing]    = useState(false)
  const [packets,      setPackets]      = useState([])
  const [credentials,  setCredentials]  = useState([])
  const [activeTab,    setActiveTab]    = useState('all')
  const [error,        setError]        = useState('')
  const feedRef  = useRef(null)
  const wsRef    = useRef(null)
  const jobIdRef = useRef(null)

  // Charger les interfaces
  useEffect(() => {
    apiFetch('/capture/interfaces').then(r => r.json()).then(d => {
      const ifaces = d.interfaces || []
      setInterfaces(ifaces)
      if (ifaces.length > 0) setIface(ifaces[0].name || ifaces[0])
    }).catch(() => {})
  }, [])

  // Auto-scroll
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [packets])

  const startCapture = async () => {
    setError('')
    setPackets([])
    setCredentials([])
    try {
      const r = await apiFetch('/capture/start', {
        method: 'POST',
        body: JSON.stringify({ interface: iface, filter: bpfFilter || undefined }),
      })
      if (!r.ok) throw new Error('Impossible de démarrer la capture')
      const d = await r.json()
      jobIdRef.current = d.job_id
      setCapturing(true)

      // WebSocket pour les paquets live
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const token = localStorage.getItem('eye_token') || ''
      const ws = new WebSocket(`${proto}//${window.location.host}/api/capture/ws/${d.job_id}?token=${token}`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const pkt = JSON.parse(e.data)
          if (pkt.type === 'packet') {
            setPackets(prev => [...prev, pkt].slice(-500))
          }
          if (pkt.type === 'credential') {
            setCredentials(prev => [pkt, ...prev].slice(0, 50))
          }
        } catch {}
      }
      ws.onerror = () => {}
    } catch (e) { setError(e.message) }
  }

  const stopCapture = async () => {
    wsRef.current?.close()
    setCapturing(false)
    if (jobIdRef.current) {
      try {
        await apiFetch(`/capture/stop/${jobIdRef.current}`, { method: 'POST' })
      } catch {}
    }
  }

  useEffect(() => () => wsRef.current?.close(), [])

  const exportPcap = () => {
    if (!jobIdRef.current) return
    const token = localStorage.getItem('eye_token') || ''
    window.open(`/api/capture/export/${jobIdRef.current}?token=${token}`, '_blank')
  }

  // Filtrer par onglet
  const filteredPackets = packets.filter(p => {
    if (activeTab === 'all') return true
    if (activeTab === 'http') return ['HTTP', 'HTTPS'].includes((p.protocol || '').toUpperCase())
    if (activeTab === 'dns')  return (p.protocol || '').toUpperCase() === 'DNS'
    if (activeTab === 'creds') return p.has_credentials
    return true
  })

  const TABS = [
    { id: 'all',   label: `Tous (${packets.length})` },
    { id: 'http',  label: `HTTP (${packets.filter(p => ['HTTP','HTTPS'].includes((p.protocol||'').toUpperCase())).length})` },
    { id: 'dns',   label: `DNS (${packets.filter(p => (p.protocol||'').toUpperCase() === 'DNS').length})` },
    { id: 'creds', label: `🔑 Creds (${credentials.length})` },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>📡</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            NETWORK SNIFFER
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Capture · Analyse · Extraction de Credentials
          </div>
        </div>
        {capturing && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', animation: 'neon-pulse 1s infinite', display: 'inline-block' }} />
            <span style={{ color: '#ef4444', fontSize: '0.75rem', fontWeight: 700 }}>{packets.length} paquets</span>
          </div>
        )}
      </div>

      {/* Contrôles */}
      <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
          {/* Interface */}
          <select
            value={iface} onChange={e => setIface(e.target.value)}
            disabled={capturing}
            style={{
              padding: '8px 12px', background: '#000820', border: '1px solid var(--border2)',
              borderRadius: 8, color: 'var(--text)', fontSize: '0.8rem', minWidth: 160,
            }}
          >
            {interfaces.length === 0 && <option value="">Chargement…</option>}
            {interfaces.map((f, i) => (
              <option key={i} value={f.name || f}>{f.name || f}</option>
            ))}
          </select>

          {/* BPF filter */}
          <input
            value={bpfFilter} onChange={e => setBpfFilter(e.target.value)}
            placeholder="Filtre BPF… ex: tcp port 80"
            disabled={capturing}
            style={{
              flex: 1, minWidth: 200, padding: '8px 12px', background: '#000820',
              border: '1px solid var(--border2)', borderRadius: 8,
              color: 'var(--text)', fontSize: '0.8rem', fontFamily: 'monospace',
            }}
          />

          {/* Start/Stop */}
          {!capturing ? (
            <button onClick={startCapture} style={{
              padding: '8px 24px', background: 'var(--accent2)', border: 'none',
              borderRadius: 8, color: '#000', cursor: 'pointer', fontWeight: 800, fontSize: '0.82rem',
            }}>▶ Capturer</button>
          ) : (
            <button onClick={stopCapture} style={{
              padding: '8px 24px', background: '#ef444430', border: '1px solid #ef4444',
              borderRadius: 8, color: '#ef4444', cursor: 'pointer', fontWeight: 800, fontSize: '0.82rem',
            }}>⏹ Arrêter</button>
          )}

          <button onClick={exportPcap} disabled={!jobIdRef.current} style={{
            padding: '8px 16px', background: '#38bdf820', border: '1px solid #38bdf850',
            borderRadius: 8, color: '#38bdf8', cursor: 'pointer', fontSize: '0.75rem',
            opacity: !jobIdRef.current ? 0.4 : 1,
          }}>⬇ PCAP</button>
        </div>

        {/* BPF Presets */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)', alignSelf: 'center' }}>Presets:</span>
          {BPF_PRESETS.map(p => (
            <button key={p.label} onClick={() => setBpfFilter(p.filter)} disabled={capturing} style={{
              padding: '3px 10px', borderRadius: 6,
              background: bpfFilter === p.filter ? 'var(--glow2)' : '#ffffff08',
              border: `1px solid ${bpfFilter === p.filter ? 'var(--accent)' : 'var(--border)'}`,
              color: bpfFilter === p.filter ? 'var(--accent)' : 'var(--text2)',
              cursor: 'pointer', fontSize: '0.68rem', fontWeight: 600,
            }}>{p.label}</button>
          ))}
        </div>

        {error && <div style={{ marginTop: 10, color: '#ef4444', fontSize: '0.75rem' }}>⚠ {error}</div>}
      </div>

      {/* Credentials Alert */}
      {credentials.length > 0 && (
        <div style={{
          background: '#ef444415', border: '1px solid #ef444450', borderRadius: 12,
          padding: '12px 16px', marginBottom: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: '1rem' }}>🔑</span>
            <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '0.82rem' }}>
              CREDENTIALS DÉTECTÉS — {credentials.length}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 120, overflowY: 'auto' }}>
            {credentials.map((c, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, fontSize: '0.72rem', fontFamily: 'monospace' }}>
                <span style={{ color: 'var(--text3)' }}>{c.timestamp?.slice(11, 19)}</span>
                <span style={{ color: '#fbbf24' }}>{c.protocol}</span>
                <span style={{ color: '#ef4444' }}>{c.username}</span>
                <span style={{ color: 'var(--text3)' }}>:</span>
                <span style={{ color: '#ef4444' }}>{c.password}</span>
                <span style={{ color: 'var(--text2)' }}>{c.src} → {c.dst}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 0, borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            padding: '8px 18px', background: 'transparent',
            borderBottom: t.id === activeTab ? '2px solid var(--accent)' : '2px solid transparent',
            border: 'none', borderRadius: 0,
            color: t.id === activeTab ? 'var(--accent)' : 'var(--text2)',
            cursor: 'pointer', fontSize: '0.75rem', fontWeight: t.id === activeTab ? 700 : 400,
            transition: 'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {/* Packet feed */}
      <div ref={feedRef} className="packet-feed" style={{
        background: '#000a18', border: '1px solid var(--border)', borderRadius: '0 0 12px 12px',
        height: 420, overflowY: 'auto', fontFamily: 'monospace',
      }}>
        {filteredPackets.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 60, color: 'var(--text3)', fontSize: '0.78rem' }}>
            {capturing ? '⟳ En attente de paquets…' : 'Démarrer la capture pour voir les paquets'}
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr style={{ position: 'sticky', top: 0, background: '#000c1a', zIndex: 1 }}>
                <th style={{ padding: '6px 12px', textAlign: 'left', color: 'var(--text3)', fontWeight: 600, borderBottom: '1px solid var(--border)', width: 70 }}>Proto</th>
                <th style={{ padding: '6px 12px', textAlign: 'left', color: 'var(--text3)', fontWeight: 600, borderBottom: '1px solid var(--border)', width: 90 }}>Heure</th>
                <th style={{ padding: '6px 12px', textAlign: 'left', color: 'var(--text3)', fontWeight: 600, borderBottom: '1px solid var(--border)' }}>Source → Destination</th>
                <th style={{ padding: '6px 12px', textAlign: 'left', color: 'var(--text3)', fontWeight: 600, borderBottom: '1px solid var(--border)' }}>Info</th>
                <th style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--text3)', fontWeight: 600, borderBottom: '1px solid var(--border)', width: 70 }}>Taille</th>
              </tr>
            </thead>
            <tbody>
              {filteredPackets.slice(-300).map((p, i) => (
                <tr key={i} style={{
                  background: p.has_credentials ? '#ef444410' : i % 2 === 0 ? '#ffffff03' : 'transparent',
                  borderBottom: '1px solid #ffffff05',
                }}>
                  <td style={{ padding: '4px 12px' }}><ProtoBadge proto={p.protocol} /></td>
                  <td style={{ padding: '4px 12px', color: 'var(--text3)' }}>{p.timestamp?.slice(11, 19) || '--:--:--'}</td>
                  <td style={{ padding: '4px 12px', color: 'var(--text)' }}>
                    <span style={{ color: '#38bdf8' }}>{p.src || '?'}</span>
                    <span style={{ color: 'var(--text3)', margin: '0 4px' }}>→</span>
                    <span style={{ color: '#a78bfa' }}>{p.dst || '?'}</span>
                  </td>
                  <td style={{ padding: '4px 12px', color: 'var(--text2)', overflow: 'hidden', maxWidth: 340, textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.has_credentials && <span style={{ color: '#ef4444', marginRight: 6 }}>🔑</span>}
                    {p.info || p.summary || ''}
                  </td>
                  <td style={{ padding: '4px 12px', color: 'var(--text3)', textAlign: 'right' }}>
                    {p.size ? `${p.size}B` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
