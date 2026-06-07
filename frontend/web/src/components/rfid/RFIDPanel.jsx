/**
 * RFIDPanel — RFID Badge Tool (Proxmark3)
 * Sections: Scan / Dump / Clone / Analysis / Simulate / Cartes sauvegardées
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../../utils/auth'

// ── Couleurs sévérité ─────────────────────────────────────────────────────────
const SEV_COLOR = {
  CRITICAL: '#ff4444',
  HIGH:     '#ff6b35',
  MEDIUM:   '#ffd700',
  LOW:      '#00d4ff',
  INFO:     '#6b8aaa',
}

// ── Badge sévérité ────────────────────────────────────────────────────────────
function SevBadge({ sev }) {
  const c = SEV_COLOR[sev] || '#6b8aaa'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      border: `1px solid ${c}`, color: c,
      fontSize: 10, fontWeight: 700, letterSpacing: 1,
    }}>{sev}</span>
  )
}

// ── Hex dump grid ─────────────────────────────────────────────────────────────
function HexDump({ blocks }) {
  if (!blocks || Object.keys(blocks).length === 0) return null
  return (
    <div style={{
      fontFamily: 'monospace', fontSize: 11, color: 'var(--text2)',
      background: '#000820', borderRadius: 8, padding: 12,
      maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border)',
    }}>
      {Object.entries(blocks).map(([blk, data]) => {
        // Affiche 16 bytes par ligne (32 hex chars)
        const hex = (data || '').toUpperCase()
        const pairs = hex.match(/.{1,2}/g) || []
        const isKey = parseInt(blk) % 4 === 3
        return (
          <div key={blk} style={{
            display: 'flex', gap: 8, padding: '2px 0',
            color: isKey ? '#ff6b35' : 'var(--text2)',
          }}>
            <span style={{ color: '#3a5a7a', minWidth: 28 }}>
              {String(blk).padStart(2, '0')}
            </span>
            <span style={{ flex: 1, letterSpacing: 1 }}>
              {pairs.join(' ')}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── ProgressBar blocs ─────────────────────────────────────────────────────────
function BlockProgress({ current, total = 64 }) {
  const pct = total > 0 ? Math.min((current / total) * 100, 100) : 0
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text3)' }}>BLOCS LUS</span>
        <span style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 700 }}>
          {current} / {total}
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--bg2)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: 'linear-gradient(90deg, #00d4ff, #0066cc)',
          borderRadius: 3, transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  )
}

// ── Composant principal ───────────────────────────────────────────────────────
export default function RFIDPanel() {
  const [section,         setSection]         = useState('scan')
  const [pm3Status,       setPm3Status]       = useState(null)
  const [statusLoading,   setStatusLoading]   = useState(false)

  // Scan
  const [scanning,        setScanning]        = useState(false)
  const [scanResult,      setScanResult]      = useState(null)
  const [scanError,       setScanError]       = useState('')

  // Dump
  const [dumping,         setDumping]         = useState(false)
  const [dumpResult,      setDumpResult]      = useState(null)
  const [dumpCardType,    setDumpCardType]    = useState('hf_mifare_classic')
  const [dumpProgress,    setDumpProgress]    = useState(0)
  const dumpTimer = useRef(null)

  // Clone
  const [cloneUID,        setCloneUID]        = useState('')
  const [cloneDataHex,    setCloneDataHex]    = useState('')
  const [cloneTarget,     setCloneTarget]     = useState('lf_t55xx')
  const [cloning,         setCloning]         = useState(false)
  const [cloneResult,     setCloneResult]     = useState(null)

  // Analysis
  const [analyzeRaw,      setAnalyzeRaw]      = useState('')
  const [analyzeResult,   setAnalyzeResult]   = useState(null)
  const [vulnType,        setVulnType]        = useState('')
  const [vulns,           setVulns]           = useState(null)

  // Simulate
  const [simUID,          setSimUID]          = useState('04A3F2112233')
  const [simDataHex,      setSimDataHex]      = useState('')
  const [simCardType,     setSimCardType]     = useState('hf_mifare_classic')
  const [simDuration,     setSimDuration]     = useState(30)
  const [simulating,      setSimulating]      = useState(false)
  const [simResult,       setSimResult]       = useState(null)

  // Cards list
  const [cards,           setCards]           = useState([])
  const [cardsLoading,    setCardsLoading]    = useState(false)

  // ── Helpers ──────────────────────────────────────────────────────────────

  const api = useCallback(async (path, opts = {}) => {
    const res = await apiFetch(`/rfid${path}`, opts)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return res.json()
  }, [])

  // ── Status PM3 ────────────────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    setStatusLoading(true)
    try {
      const d = await api('/status')
      setPm3Status(d)
    } catch {
      setPm3Status({ connected: false, simulation_mode: true })
    }
    setStatusLoading(false)
  }, [api])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const loadCards = useCallback(async () => {
    setCardsLoading(true)
    try {
      const d = await api('/cards')
      setCards(d.cards || [])
    } catch { /* ignore */ }
    setCardsLoading(false)
  }, [api])

  useEffect(() => { loadCards() }, [loadCards])

  // ── Scan ─────────────────────────────────────────────────────────────────

  const handleScan = async () => {
    setScanning(true)
    setScanResult(null)
    setScanError('')
    try {
      const d = await api('/scan', { method: 'POST' })
      setScanResult(d.card)
      loadCards()
    } catch (e) {
      setScanError(e.message)
    }
    setScanning(false)
  }

  // ── Dump ─────────────────────────────────────────────────────────────────

  const handleDump = async () => {
    setDumping(true)
    setDumpResult(null)
    setDumpProgress(0)
    // Simule la progression visuelle
    dumpTimer.current = setInterval(() => {
      setDumpProgress(p => (p >= 63 ? 63 : p + 1))
    }, 200)
    try {
      const d = await api('/dump', {
        method: 'POST',
        body: JSON.stringify({ card_type: dumpCardType }),
      })
      clearInterval(dumpTimer.current)
      setDumpProgress(d.blocks_count || 64)
      setDumpResult(d)
    } catch (e) {
      clearInterval(dumpTimer.current)
      setScanError(e.message)
    }
    setDumping(false)
  }

  useEffect(() => () => clearInterval(dumpTimer.current), [])

  // ── Clone ─────────────────────────────────────────────────────────────────

  const handleClone = async () => {
    if (!cloneUID) return
    setCloning(true)
    setCloneResult(null)
    try {
      const d = await api('/clone', {
        method: 'POST',
        body: JSON.stringify({ source_uid: cloneUID, data_hex: cloneDataHex, target_type: cloneTarget }),
      })
      setCloneResult(d)
    } catch (e) {
      setCloneResult({ success: false, message: e.message })
    }
    setCloning(false)
  }

  // ── Analysis ─────────────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!analyzeRaw) return
    try {
      const d = await api('/analyze', {
        method: 'POST',
        body: JSON.stringify({ raw_data: analyzeRaw }),
      })
      setAnalyzeResult(d)
    } catch (e) {
      setAnalyzeResult({ error: e.message })
    }
  }

  const handleVulnScan = async () => {
    if (!vulnType) return
    try {
      const d = await api('/vuln-scan', {
        method: 'POST',
        body: JSON.stringify({ card_type: vulnType }),
      })
      setVulns(d.vulnerabilities || [])
    } catch { /* ignore */ }
  }

  // ── Simulate ─────────────────────────────────────────────────────────────

  const handleSimulate = async () => {
    setSimulating(true)
    setSimResult(null)
    try {
      const d = await api('/simulate', {
        method: 'POST',
        body: JSON.stringify({ uid: simUID, data_hex: simDataHex, card_type: simCardType, duration: simDuration }),
      })
      setSimResult(d)
    } catch (e) {
      setSimResult({ success: false, message: e.message })
    }
    setSimulating(false)
  }

  // ── Export ────────────────────────────────────────────────────────────────

  const exportData = (fmt) => {
    if (!dumpResult) return
    const { blocks, keys_found } = dumpResult
    let content, mime, ext

    if (fmt === 'json') {
      content = JSON.stringify({ blocks, keys_found, exported_at: new Date().toISOString() }, null, 2)
      mime = 'application/json'; ext = 'json'
    } else if (fmt === 'eml') {
      content = Object.values(blocks || {}).join('\n')
      mime = 'text/plain'; ext = 'eml'
    } else {
      // .bin — hex brut
      const hex = Object.values(blocks || {}).join('')
      const bytes = new Uint8Array(hex.match(/.{1,2}/g).map(b => parseInt(b, 16)))
      const blob = new Blob([bytes], { type: 'application/octet-stream' })
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
      a.download = `rfid_dump.bin`; a.click(); return
    }

    const blob = new Blob([content], { type: mime })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `rfid_dump.${ext}`; a.click()
  }

  // ── PM3 status badge ──────────────────────────────────────────────────────

  const pm3Color  = pm3Status?.connected ? '#00ff88' : (pm3Status?.simulation_mode ? '#ffd700' : '#ff4444')
  const pm3Label  = pm3Status?.connected ? 'PM3 CONNECTÉ' : (pm3Status?.simulation_mode ? 'SIMULATION' : 'NON CONNECTÉ')

  // ── Tabs ─────────────────────────────────────────────────────────────────

  const SECTIONS = [
    { id: 'scan',     label: 'Scan' },
    { id: 'dump',     label: 'Dump' },
    { id: 'clone',    label: 'Clone' },
    { id: 'analysis', label: 'Analyse' },
    { id: 'simulate', label: 'Simulate' },
  ]

  return (
    <div style={{ fontFamily: 'monospace', color: 'var(--text)', minHeight: '100%' }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24 }}>📡</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
              RFID BADGE TOOL
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: 1 }}>
              Proxmark3 · Clone · Analyse · Simulation
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 12px', borderRadius: 20, border: `1px solid ${pm3Color}`,
            color: pm3Color, fontSize: 11, fontWeight: 700,
          }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: pm3Color, display: 'inline-block' }} />
            {pm3Label}
          </span>
          <button
            onClick={fetchStatus}
            disabled={statusLoading}
            style={{
              background: 'none', border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text3)', padding: '4px 10px', cursor: 'pointer', fontSize: 12,
            }}
          >
            {statusLoading ? '...' : 'Actualiser'}
          </button>
        </div>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 1 }}>
        {SECTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            style={{
              background: section === s.id ? 'var(--accent)20' : 'none',
              border: 'none',
              borderBottom: section === s.id ? '2px solid var(--accent)' : '2px solid transparent',
              color: section === s.id ? 'var(--accent)' : 'var(--text3)',
              padding: '8px 16px', cursor: 'pointer', fontSize: 12, fontWeight: 700,
              letterSpacing: 1, fontFamily: 'monospace',
            }}
          >{s.label}</button>
        ))}
      </div>

      {/* ── Section: SCAN ──────────────────────────────────────────────────── */}
      {section === 'scan' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Bouton scan */}
          <div style={card}>
            <div style={cardLabel}>SCANNER UNE CARTE</div>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{ fontSize: 56, marginBottom: 16 }}>
                {scanning ? '🔄' : '💳'}
              </div>
              <button
                onClick={handleScan}
                disabled={scanning}
                style={scanning ? btnDisabled : btnPrimary}
              >
                {scanning ? 'Recherche en cours…' : 'SCANNER'}
              </button>
              {scanError && (
                <div style={{ marginTop: 12, color: '#ff4444', fontSize: 12 }}>{scanError}</div>
              )}
            </div>
          </div>

          {/* Résultat */}
          <div style={card}>
            <div style={cardLabel}>RÉSULTAT</div>
            {!scanResult ? (
              <div style={{ color: 'var(--text3)', fontSize: 13, paddingTop: 20, textAlign: 'center' }}>
                En attente d'un scan…
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <Row label="UID" value={<span style={{ color: 'var(--accent)', fontWeight: 700 }}>{scanResult.uid}</span>} />
                <Row label="Type" value={scanResult.card_type} />
                <Row label="Protocole" value={
                  scanResult.protocol
                    ? <span style={{ padding: '2px 8px', borderRadius: 4, background: '#00d4ff20', border: '1px solid #00d4ff40', color: '#00d4ff', fontSize: 11 }}>{scanResult.protocol}</span>
                    : '—'
                } />
                {scanResult.atqa && <Row label="ATQA" value={scanResult.atqa} />}
                {scanResult.sak  && <Row label="SAK"  value={scanResult.sak} />}
                {scanResult.simulated && (
                  <span style={{ color: '#ffd700', fontSize: 11, fontWeight: 700 }}>MODE SIMULATION</span>
                )}
                <button
                  onClick={() => { setCloneUID(scanResult.uid); setSection('clone') }}
                  style={{ ...btnSecondary, marginTop: 8 }}
                >
                  Cloner cette carte →
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Section: DUMP ──────────────────────────────────────────────────── */}
      {section === 'dump' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={card}>
            <div style={cardLabel}>DUMP COMPLET</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>TYPE DE CARTE</div>
                <select
                  value={dumpCardType}
                  onChange={e => setDumpCardType(e.target.value)}
                  style={selectStyle}
                >
                  <option value="hf_mifare_classic">MIFARE Classic</option>
                  <option value="hf_mifare_ultralight">MIFARE Ultralight</option>
                  <option value="hf_desfire">DESFire</option>
                  <option value="hf_iclass">iCLASS</option>
                  <option value="lf_em4100">EM4100 (LF)</option>
                  <option value="lf_hid">HID Prox (LF)</option>
                </select>
              </div>
              <button onClick={handleDump} disabled={dumping} style={dumping ? btnDisabled : btnPrimary}>
                {dumping ? 'Dump en cours…' : 'DUMP FULL'}
              </button>
            </div>

            {(dumping || dumpResult) && (
              <BlockProgress current={dumpProgress} total={64} />
            )}
          </div>

          {dumpResult && (
            <>
              {/* Clés trouvées */}
              {dumpResult.keys_found && dumpResult.keys_found.length > 0 && (
                <div style={card}>
                  <div style={cardLabel}>CLÉS TROUVÉES</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {dumpResult.keys_found.map((k, i) => (
                      <span key={i} style={{
                        padding: '4px 12px', borderRadius: 6,
                        background: '#00d4ff15', border: '1px solid #00d4ff40',
                        color: '#00d4ff', fontSize: 12, fontWeight: 700,
                      }}>{k}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* HexDump */}
              <div style={card}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', marginBottom: 12,
                }}>
                  <div style={cardLabel}>HEX DUMP</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {['.eml', '.bin', '.json'].map(fmt => (
                      <button
                        key={fmt}
                        onClick={() => exportData(fmt.replace('.', ''))}
                        style={btnSmall}
                      >Export {fmt}</button>
                    ))}
                  </div>
                </div>
                <HexDump blocks={dumpResult.blocks || {}} />
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Section: CLONE ─────────────────────────────────────────────────── */}
      {section === 'clone' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={card}>
            <div style={cardLabel}>SOURCE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={fieldLabel}>UID SOURCE</div>
                <input
                  value={cloneUID}
                  onChange={e => setCloneUID(e.target.value)}
                  placeholder="04:A3:F2:11:22:33 ou 04A3F2112233"
                  style={inputStyle}
                />
              </div>
              <div>
                <div style={fieldLabel}>DONNÉES HEX (optionnel)</div>
                <textarea
                  value={cloneDataHex}
                  onChange={e => setCloneDataHex(e.target.value)}
                  placeholder="Données hex du dump…"
                  rows={4}
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              </div>
            </div>
          </div>

          <div style={card}>
            <div style={cardLabel}>CIBLE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={fieldLabel}>TYPE DE CARTE CIBLE</div>
                <select value={cloneTarget} onChange={e => setCloneTarget(e.target.value)} style={selectStyle}>
                  <option value="lf_t55xx">T55xx (LF — universel)</option>
                  <option value="lf_em4305">EM4305 (LF)</option>
                  <option value="hf_mifare_classic">MIFARE Classic (HF)</option>
                </select>
              </div>

              <button
                onClick={handleClone}
                disabled={cloning || !cloneUID}
                style={cloning || !cloneUID ? btnDisabled : btnDanger}
              >
                {cloning ? 'Clonage en cours…' : 'CLONER'}
              </button>

              {cloneResult && (
                <div style={{
                  padding: 12, borderRadius: 8,
                  border: `1px solid ${cloneResult.success ? '#00ff88' : '#ff4444'}`,
                  background: cloneResult.success ? '#00ff8815' : '#ff444415',
                  color: cloneResult.success ? '#00ff88' : '#ff4444',
                  fontSize: 12,
                }}>
                  {cloneResult.success
                    ? `Clonage réussi${cloneResult.simulated ? ' (SIMULATION)' : ''}`
                    : `Échec: ${cloneResult.message}`}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Section: ANALYSIS ──────────────────────────────────────────────── */}
      {section === 'analysis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Analyse raw data */}
          <div style={card}>
            <div style={cardLabel}>ANALYSE DE DONNÉES BRUTES</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <div style={fieldLabel}>DONNÉES HEX BRUTES</div>
                <input
                  value={analyzeRaw}
                  onChange={e => setAnalyzeRaw(e.target.value)}
                  placeholder="ex: 200A2345…"
                  style={inputStyle}
                />
              </div>
              <button onClick={handleAnalyze} disabled={!analyzeRaw} style={!analyzeRaw ? btnDisabled : btnPrimary}>
                Analyser
              </button>
            </div>

            {analyzeResult && !analyzeResult.error && (
              <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <Row label="Format"       value={<strong style={{ color: 'var(--accent)' }}>{analyzeResult.format}</strong>} />
                <Row label="Bits"         value={analyzeResult.bits} />
                <Row label="Site Code"    value={analyzeResult.site_code || '—'} />
                <Row label="Badge N°"     value={analyzeResult.badge_number || '—'} />
                <Row label="Facility"     value={analyzeResult.facility_code || '—'} />
              </div>
            )}
            {analyzeResult?.error && (
              <div style={{ color: '#ff4444', fontSize: 12, marginTop: 10 }}>{analyzeResult.error}</div>
            )}
          </div>

          {/* Vuln scan */}
          <div style={card}>
            <div style={cardLabel}>SCAN DE VULNÉRABILITÉS</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
              <div style={{ flex: 1 }}>
                <div style={fieldLabel}>TYPE DE CARTE</div>
                <select value={vulnType} onChange={e => setVulnType(e.target.value)} style={selectStyle}>
                  <option value="">— Choisir —</option>
                  <option value="lf_em4100">EM4100</option>
                  <option value="lf_hid">HID Prox</option>
                  <option value="hf_mifare_classic">MIFARE Classic</option>
                  <option value="hf_iclass">iCLASS</option>
                  <option value="hf_desfire">DESFire</option>
                </select>
              </div>
              <button onClick={handleVulnScan} disabled={!vulnType} style={!vulnType ? btnDisabled : btnWarning}>
                Scanner
              </button>
            </div>

            {vulns && vulns.map((v, i) => (
              <div key={i} style={{
                padding: 12, borderRadius: 8, marginBottom: 8,
                border: `1px solid ${SEV_COLOR[v.severity] || '#3a5a7a'}20`,
                background: `${SEV_COLOR[v.severity] || '#3a5a7a'}08`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text)', fontSize: 13 }}>{v.title}</span>
                  <SevBadge sev={v.severity} />
                </div>
                <p style={{ fontSize: 12, color: 'var(--text2)', margin: 0 }}>{v.description}</p>
                {v.cwe && (
                  <span style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4, display: 'block' }}>
                    {v.cwe} · {v.mitre}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Section: SIMULATE ──────────────────────────────────────────────── */}
      {section === 'simulate' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={card}>
            <div style={cardLabel}>PARAMÈTRES D'ÉMULATION</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={fieldLabel}>UID</div>
                <input value={simUID} onChange={e => setSimUID(e.target.value)} style={inputStyle} placeholder="04A3F2112233" />
              </div>
              <div>
                <div style={fieldLabel}>TYPE</div>
                <select value={simCardType} onChange={e => setSimCardType(e.target.value)} style={selectStyle}>
                  <option value="hf_mifare_classic">MIFARE Classic</option>
                  <option value="lf_em4100">EM4100</option>
                  <option value="lf_hid">HID Prox</option>
                </select>
              </div>
              <div>
                <div style={fieldLabel}>DURÉE (secondes)</div>
                <input
                  type="number" min={5} max={300}
                  value={simDuration} onChange={e => setSimDuration(Number(e.target.value))}
                  style={inputStyle}
                />
              </div>
              <div>
                <div style={fieldLabel}>DONNÉES HEX (optionnel)</div>
                <input value={simDataHex} onChange={e => setSimDataHex(e.target.value)} style={inputStyle} placeholder="Laisser vide = vide" />
              </div>
            </div>
          </div>

          <div style={card}>
            <div style={cardLabel}>ÉMULATION</div>
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>
                {simulating ? '📡' : '💳'}
              </div>
              <button
                onClick={handleSimulate}
                disabled={simulating || !simUID}
                style={simulating || !simUID ? btnDisabled : btnPrimary}
              >
                {simulating ? `Émulation en cours… (${simDuration}s)` : 'SIMULATE'}
              </button>
              {simResult && (
                <div style={{
                  marginTop: 16, padding: 12, borderRadius: 8,
                  border: `1px solid ${simResult.success ? '#00ff88' : '#ff4444'}`,
                  background: simResult.success ? '#00ff8815' : '#ff444415',
                  color: simResult.success ? '#00ff88' : '#ff4444',
                  fontSize: 12,
                }}>
                  {simResult.message || (simResult.success ? 'Émulation terminée' : 'Échec')}
                </div>
              )}
              {simulating && (
                <p style={{ color: 'var(--text3)', fontSize: 12, marginTop: 12 }}>
                  Approchez un lecteur de la carte Proxmark3…
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Liste cartes scannées ───────────────────────────────────────────── */}
      <div style={{ ...card, marginTop: 20 }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', marginBottom: 12,
        }}>
          <div style={cardLabel}>CARTES ENREGISTRÉES ({cards.length})</div>
          <button onClick={loadCards} disabled={cardsLoading} style={btnSmall}>
            {cardsLoading ? '…' : 'Actualiser'}
          </button>
        </div>
        {cards.length === 0 ? (
          <div style={{ color: 'var(--text3)', fontSize: 13, textAlign: 'center', padding: 20 }}>
            Aucune carte scannée
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cards.map(c => (
              <div key={c.id} style={{
                display: 'flex', gap: 12, alignItems: 'center',
                padding: '10px 12px', borderRadius: 8,
                background: 'var(--bg2)', border: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: 20 }}>💳</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 13 }}>{c.uid}</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>
                    {c.card_type} · {c.protocol || 'unknown'}
                    {c.simulated && ' · SIM'}
                    {c.cloned && ' · CLONÉ'}
                  </div>
                </div>
                {c.vulnerabilities && c.vulnerabilities.length > 0 && (
                  <SevBadge sev={c.vulnerabilities[0].severity} />
                )}
                <button
                  onClick={() => { setCloneUID(c.uid); setSection('clone') }}
                  style={btnSmall}
                >Clone</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: 1 }}>{label}</span>
      <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 600 }}>{value}</span>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const card = {
  background: 'var(--bg-card, #0a1628)',
  border: '1px solid var(--border)',
  borderRadius: 12, padding: 16,
}

const cardLabel = {
  fontSize: 10, color: 'var(--text3)',
  letterSpacing: 1.5, fontWeight: 700, marginBottom: 12,
}

const fieldLabel = {
  fontSize: 10, color: 'var(--text3)', letterSpacing: 1, marginBottom: 4,
}

const inputStyle = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--bg, #050a14)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '8px 12px', color: 'var(--text)',
  fontSize: 12, fontFamily: 'monospace', outline: 'none',
}

const selectStyle = {
  ...inputStyle, cursor: 'pointer',
}

const btnBase = {
  padding: '9px 18px', borderRadius: 8, fontSize: 12,
  fontWeight: 800, cursor: 'pointer', letterSpacing: 1,
  fontFamily: 'monospace', border: 'none', transition: 'opacity 0.15s',
}

const btnPrimary = {
  ...btnBase, background: '#00d4ff', color: '#050a14',
}

const btnDanger = {
  ...btnBase, background: '#ff4444', color: '#ffffff',
}

const btnWarning = {
  ...btnBase, background: '#ffd700', color: '#050a14',
}

const btnSecondary = {
  ...btnBase,
  background: 'none', border: '1px solid #00d4ff40', color: '#00d4ff',
}

const btnDisabled = {
  ...btnBase, background: '#1a3a5c', color: '#3a5a7a', cursor: 'not-allowed',
}

const btnSmall = {
  padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 700,
  cursor: 'pointer', fontFamily: 'monospace',
  background: 'none', border: '1px solid var(--border)', color: 'var(--text3)',
}
