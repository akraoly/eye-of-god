import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

export default function AnonymizerControl() {
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState(null)
  const [vpnConfig, setVpnConfig] = useState('')
  const [macIface, setMacIface] = useState('eth0')
  const [customMAC, setCustomMAC] = useState('')
  const [proxies, setProxies] = useState('socks5://127.0.0.1:1080\nsocks5://proxy2.example.com:9050')
  const [torCountry, setTorCountry] = useState('')
  const [dnsProvider, setDnsProvider] = useState('cloudflare')
  const [autoRefresh, setAutoRefresh] = useState(false)

  useEffect(() => { loadStatus() }, [])
  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(loadStatus, 5000)
    return () => clearInterval(t)
  }, [autoRefresh])

  const loadStatus = async () => { const r = await apiFetch('/anonymizer/status'); if (!r.error) setStatus(r) }
  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false); loadStatus() } }

  const startTor = () => act(async () => { const r = await apiFetch('/anonymizer/tor/start', { method: 'POST', body: { country: torCountry || null, authorization_confirmed: auth } }); setResult(r) })
  const stopTor = () => act(async () => { const r = await apiFetch('/anonymizer/tor/stop', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const newIdentity = () => act(async () => { const r = await apiFetch('/anonymizer/tor/new_identity', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const startVPN = () => act(async () => { const r = await apiFetch('/anonymizer/vpn/start', { method: 'POST', body: { config_path: vpnConfig, authorization_confirmed: auth } }); setResult(r) })
  const stopVPN = () => act(async () => { const r = await apiFetch('/anonymizer/vpn/stop', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const spoofMAC = () => act(async () => { const r = await apiFetch('/anonymizer/mac/spoof', { method: 'POST', body: { interface: macIface, mac_address: customMAC || null, authorization_confirmed: auth } }); setResult(r) })
  const configProxy = () => act(async () => { const list = proxies.split('\n').filter(Boolean); const r = await apiFetch('/anonymizer/proxy/configure', { method: 'POST', body: { proxies: list, protocol: 'socks5', authorization_confirmed: auth } }); setResult(r) })
  const configDNS = () => act(async () => { const r = await apiFetch('/anonymizer/dns/doh', { method: 'POST', body: { provider: dnsProvider, authorization_confirmed: auth } }); setResult(r) })
  const rotateUA = () => act(async () => { const r = await apiFetch('/anonymizer/useragent/rotate', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const checkLeaks = () => act(async () => { const r = await apiFetch('/anonymizer/leak/check', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const activateAll = () => act(async () => { const r = await apiFetch('/anonymizer/activate/all', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })
  const deactivateAll = () => act(async () => { const r = await apiFetch('/anonymizer/deactivate/all', { method: 'POST', body: { authorization_confirmed: auth } }); setResult(r) })

  const scoreColor = (s) => s >= 75 ? '#7fff7f' : s >= 50 ? '#ffa500' : '#ff7070'
  const gradeColor = (g) => ({ A: '#7fff7f', B: '#a0ff70', C: '#ffa500', D: '#ff8000', F: '#ff4444' }[g] || '#ff4444')

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>🥷 Anonymisation Multi-Couches</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>Tor · VPN · MAC Spoofing · ProxyChains · DNS over HTTPS</p>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Opération OPSEC autorisée dans le cadre du pentest</span>
      </label>

      {/* Score Dashboard */}
      {status && (
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h4 style={{ color: '#ff6b35', margin: 0 }}>Score Anonymat</h4>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, cursor: 'pointer' }}>
                <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
                <span style={{ color: '#888' }}>Auto-refresh</span>
              </label>
              <button onClick={loadStatus} style={{ padding: '4px 10px', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>↻</button>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 16 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, fontWeight: 900, color: scoreColor(status.anonymity_score || 0) }}>{status.anonymity_score || 0}</div>
              <div style={{ fontSize: 12, color: '#888' }}>/ 100</div>
            </div>
            <div style={{ fontSize: 56, fontWeight: 900, color: gradeColor(status.grade), width: 70, textAlign: 'center' }}>{status.grade}</div>
            <div style={{ flex: 1 }}>
              <div style={{ height: 12, background: '#1a1a1a', borderRadius: 6, overflow: 'hidden', marginBottom: 8 }}>
                <div style={{ height: '100%', width: `${status.anonymity_score || 0}%`, background: `linear-gradient(90deg, #ff6b35, ${scoreColor(status.anonymity_score || 0)})`, borderRadius: 6, transition: 'width 0.5s' }} />
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(status.active_layers || []).map(l => (
                  <span key={l} style={{ fontSize: 11, background: '#0d1a0d', color: '#7fff7f', border: '1px solid #2d5a2d', padding: '2px 8px', borderRadius: 10 }}>{l}</span>
                ))}
              </div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
            {[
              { label: 'Tor', active: status.tor_active, icon: '🧅' },
              { label: 'VPN', active: status.vpn_active, icon: '🔒' },
              { label: 'MAC Spoofed', active: status.mac_spoofed, icon: '🎭' },
              { label: 'ProxyChain', active: status.proxy_chain_active, icon: '🔗' },
              { label: 'DNS over HTTPS', active: status.dns_over_https, icon: '🌍' },
            ].map(item => (
              <div key={item.label} style={{ background: item.active ? '#0d1a0d' : '#1a0d0d', border: `1px solid ${item.active ? '#2d5a2d' : '#5d2e2e'}`, borderRadius: 4, padding: '10px 8px', textAlign: 'center' }}>
                <div style={{ fontSize: 18, marginBottom: 4 }}>{item.icon}</div>
                <div style={{ fontSize: 11, color: item.active ? '#7fff7f' : '#ff7070', fontWeight: 600 }}>{item.active ? '✅ ON' : '❌ OFF'}</div>
                <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>{item.label}</div>
              </div>
            ))}
          </div>
          {status.real_ip && (
            <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>
              IP réelle: <span style={{ color: '#ff7070' }}>{status.real_ip}</span>
              {status.exit_ip && <span> → Exit: <span style={{ color: '#7fff7f' }}>{status.exit_ip}</span> ({status.exit_country})</span>}
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Quick Actions */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16, gridColumn: '1/-1' }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Actions Rapides</h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={activateAll} disabled={loading || !auth} style={{ padding: '10px 20px', background: '#1e3a1e', color: '#7fff7f', border: '2px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>⚡ TOUT ACTIVER</button>
            <button onClick={deactivateAll} disabled={loading || !auth} style={{ padding: '10px 20px', background: '#3a1e1e', color: '#ff7070', border: '2px solid #5a2e2e', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>🔓 TOUT DÉSACTIVER</button>
            <button onClick={checkLeaks} disabled={loading || !auth} style={{ padding: '10px 20px', background: '#1e2a3e', color: '#7fc4ff', border: '2px solid #2d4a6e', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>🔍 Test Fuite IP</button>
            <button onClick={newIdentity} disabled={loading || !auth || !status?.tor_active} style={{ padding: '10px 20px', background: '#2a1e3a', color: '#d0a0ff', border: '2px solid #4a3a6a', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>🧅 Nouvelle Identité Tor</button>
          </div>
        </div>

        {/* Tor */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>🧅 Tor Network</h4>
          <label style={{ fontSize: 12, color: '#aaa' }}>Pays de sortie (optionnel)</label>
          <input value={torCountry} onChange={e => setTorCountry(e.target.value)} placeholder="CH, DE, NL..." style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, marginBottom: 10, boxSizing: 'border-box' }} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={startTor} disabled={loading || !auth} style={{ flex: 1, padding: '8px 0', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>▶ Démarrer</button>
            <button onClick={stopTor} disabled={loading || !auth} style={{ flex: 1, padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer' }}>■ Stopper</button>
          </div>
        </div>

        {/* VPN */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>🔒 OpenVPN</h4>
          <label style={{ fontSize: 12, color: '#aaa' }}>Chemin config .ovpn</label>
          <input value={vpnConfig} onChange={e => setVpnConfig(e.target.value)} placeholder="/etc/openvpn/client.ovpn" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, marginBottom: 10, boxSizing: 'border-box' }} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={startVPN} disabled={loading || !auth || !vpnConfig} style={{ flex: 1, padding: '8px 0', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>▶ Connecter</button>
            <button onClick={stopVPN} disabled={loading || !auth} style={{ flex: 1, padding: '8px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer' }}>■ Déconnecter</button>
          </div>
        </div>

        {/* MAC Spoofing */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>🎭 MAC Address Spoofing</h4>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: '#aaa' }}>Interface</label>
              <select value={macIface} onChange={e => setMacIface(e.target.value)} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 6px', borderRadius: 4, marginTop: 2 }}>
                {['eth0', 'wlan0', 'eth1', 'wlan1', 'ens33'].map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div style={{ flex: 2 }}>
              <label style={{ fontSize: 11, color: '#aaa' }}>MAC (vide = aléatoire)</label>
              <input value={customMAC} onChange={e => setCustomMAC(e.target.value)} placeholder="AA:BB:CC:DD:EE:FF" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '5px 6px', borderRadius: 4, marginTop: 2, boxSizing: 'border-box' }} />
            </div>
          </div>
          <button onClick={spoofMAC} disabled={loading || !auth} style={{ width: '100%', padding: '8px 0', background: '#2a1e2a', color: '#d0a0ff', border: '1px solid #4a3a6a', borderRadius: 4, cursor: 'pointer' }}>🎭 Spoofer MAC</button>
        </div>

        {/* ProxyChain */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>🔗 ProxyChains</h4>
          <label style={{ fontSize: 12, color: '#aaa' }}>Proxies (un par ligne)</label>
          <textarea value={proxies} onChange={e => setProxies(e.target.value)} rows={4} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, fontFamily: 'inherit', resize: 'none', marginTop: 4, boxSizing: 'border-box' }} />
          <button onClick={configProxy} disabled={loading || !auth} style={{ width: '100%', marginTop: 8, padding: '8px 0', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 4, cursor: 'pointer' }}>🔗 Configurer ProxyChain</button>
        </div>

        {/* DNS over HTTPS + UA */}
        <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>🌍 DNS over HTTPS + User-Agent</h4>
          <label style={{ fontSize: 12, color: '#aaa' }}>Fournisseur DNS</label>
          <select value={dnsProvider} onChange={e => setDnsProvider(e.target.value)} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginTop: 4, marginBottom: 10 }}>
            <option value="cloudflare">Cloudflare (1.1.1.1)</option>
            <option value="google">Google (8.8.8.8)</option>
            <option value="quad9">Quad9 (9.9.9.9)</option>
          </select>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={configDNS} disabled={loading || !auth} style={{ flex: 1, padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>🌍 Activer DoH</button>
            <button onClick={rotateUA} disabled={loading || !auth} style={{ flex: 1, padding: '8px 0', background: '#2a1e3a', color: '#d0a0ff', border: '1px solid #4a3a6a', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>🔄 Rotation UA</button>
          </div>
        </div>
      </div>

      {(loading || result) && (
        <div style={{ background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 300 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
