import { useState, useEffect, useRef, useCallback } from 'react'

const API = '/api/offensive'
const C2_API = '/api/c2'

const C2_META = {
  sliver:   { icon: '🐍', color: '#10b981', port: 31337, label: 'Sliver C2' },
  havoc:    { icon: '🔥', color: '#f97316', port: 40056, label: 'Havoc C2' },
  gophish:  { icon: '🎣', color: '#38bdf8', port: 3333,  label: 'Gophish' },
  evilginx: { icon: '👁',  color: '#a78bfa', port: 443,   label: 'Evilginx' },
}

const LEVEL_STYLES = {
  1: { border: '#38bdf8', glow: 'rgba(56,189,248,0.25)', badge: '#0369a1' },
  2: { border: '#a78bfa', glow: 'rgba(167,139,250,0.25)', badge: '#6d28d9' },
  3: { border: '#f97316', glow: 'rgba(249,115,22,0.25)',  badge: '#c2410c' },
  4: { border: '#10b981', glow: 'rgba(16,185,129,0.25)',  badge: '#065f46' },
}

const PIPELINE_STAGES = [
  { id: 'fuzz',    icon: '🐛', label: 'Fuzzing',  desc: 'AFL++ génère des crashs' },
  { id: 'crash',   icon: '💢', label: 'Crash',    desc: 'Triage + exploitabilité' },
  { id: 'reverse', icon: '🔬', label: 'Reverse',  desc: 'Analyse binaire' },
  { id: 'exploit', icon: '💥', label: 'Exploit',  desc: 'Template pwntools' },
]

export default function OffensiveView() {
  const [levels, setLevels]       = useState({})
  const [activeLevel, setActive]  = useState(null)
  const [terminal, setTerminal]   = useState('')
  const [running, setRunning]     = useState(false)
  const [binary, setBinary]       = useState('')
  const [target, setTarget]       = useState('')
  const [c2Status, setC2Status]   = useState({})
  const [c2Logs, setC2Logs]       = useState({})
  const [c2Loading, setC2Loading] = useState({})
  const [activeC2Log, setActiveC2Log] = useState(null)
  const c2PollRef = useRef(null)
  const [pipeStage, setPipe]      = useState(null)
  const termRef = useRef(null)

  useEffect(() => {
    fetch(`${API}/levels`)
      .then(r => r.json())
      .then(d => setLevels(d.levels || {}))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [terminal])

  // Charge l'état initial des C2
  const refreshC2Status = useCallback(() => {
    fetch(`${C2_API}/`)
      .then(r => r.json())
      .then(d => {
        const map = {}
        ;(d.c2s || []).forEach(s => { map[s.name] = s })
        setC2Status(map)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    refreshC2Status()
  }, [refreshC2Status])

  // Polling des logs pour les C2 actifs
  useEffect(() => {
    c2PollRef.current = setInterval(() => {
      Object.values(c2Status).forEach(s => {
        if (s.running) {
          fetch(`${C2_API}/logs/${s.name}?n=60`)
            .then(r => r.json())
            .then(d => setC2Logs(prev => ({ ...prev, [s.name]: d.lines || [] })))
            .catch(() => {})
        }
      })
      // Refresh statuts
      refreshC2Status()
    }, 2000)
    return () => clearInterval(c2PollRef.current)
  }, [c2Status, refreshC2Status])

  const startC2 = async (name) => {
    setC2Loading(prev => ({ ...prev, [name]: true }))
    try {
      const r = await fetch(`${C2_API}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const d = await r.json()
      log(`\n[C2] ${name.toUpperCase()} : ${d.message || d.error}`)
      refreshC2Status()
      if (d.success) setActiveC2Log(name)
    } catch (e) { log(`[!] ${e.message}`) }
    setC2Loading(prev => ({ ...prev, [name]: false }))
  }

  const stopC2 = async (name) => {
    setC2Loading(prev => ({ ...prev, [name]: true }))
    try {
      const r = await fetch(`${C2_API}/stop/${name}`, { method: 'POST' })
      const d = await r.json()
      log(`\n[C2] ${name.toUpperCase()} : ${d.message || d.error}`)
      refreshC2Status()
    } catch (e) { log(`[!] ${e.message}`) }
    setC2Loading(prev => ({ ...prev, [name]: false }))
  }

  const log = (msg) => setTerminal(prev => prev + msg + '\n')

  const runTool = async (level, tool, params = {}) => {
    setRunning(true)
    log(`\n[+] Lancement ${tool} (niveau ${level})...`)
    try {
      const r = await fetch(`${API}/run/tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level, tool, params }),
      })
      const d = await r.json()
      log(d.output || d.error || '(pas de sortie)')
      if (d.next_step) log(`\n[→] Étape suivante : ${d.next_step}`)
    } catch (e) {
      log(`[!] Erreur : ${e.message}`)
    }
    setRunning(false)
  }

  const runPipeline = async (stage) => {
    if (!binary) { log('[!] Renseigne le binaire avant de lancer.'); return }
    setRunning(true); setPipe(stage)
    const endpoint = {
      fuzz:    `${API}/pipeline/fuzz`,
      crash:   `${API}/pipeline/analyse-crash`,
      reverse: `${API}/pipeline/reverse`,
      exploit: `${API}/pipeline/exploit-template`,
    }[stage]
    log(`\n[+] Pipeline — stage: ${stage} sur ${binary}`)
    try {
      const body = stage === 'fuzz'
        ? { binary, corpus: '/tmp/corpus', output: '/tmp/fuzz_out', timeout: 20 }
        : stage === 'crash'
        ? { binary, crash: '/tmp/fuzz_out/default/crashes/id:000000' }
        : stage === 'exploit'
        ? { binary, offset: 0, lhost: target || '127.0.0.1', lport: 4444 }
        : { binary }
      const r = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (stage === 'exploit') log(d.exploit_template || d.error || '')
      else log(d.output || d.gdb_trace || d.main_disasm || d.error || JSON.stringify(d, null, 2))
      if (d.next_step) log(`\n[→] Prochaine étape : ${d.next_step}`)
      if (d.recommendation) log(`[!] ${d.recommendation}`)
    } catch(e) { log(`[!] ${e.message}`) }
    setRunning(false); setPipe(null)
  }

  const quickRun = async (level, tool) => {
    const params = {}
    if (target) params.target = target
    if (binary) params.binary = binary
    if (target && !target.startsWith('http') && !target.match(/\//)) {
      params.domain = target
    }
    await runTool(level, tool, params)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12, padding: 16, overflowY: 'auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <span style={{ fontSize: '1.5rem' }}>⚔️</span>
        <div>
          <div style={{ color: 'var(--elec)', fontWeight: 700, fontSize: '1.1rem', letterSpacing: 2 }}>
            OFFENSIVE — 4 NIVEAUX RED TEAM
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '0.72rem' }}>
            Recon → Vulnérabilités → Exploitation → Mouvement avancé
          </div>
        </div>
      </div>

      {/* Inputs globaux */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={target}
          onChange={e => setTarget(e.target.value)}
          placeholder="Cible (IP / domaine / URL)"
          style={inputStyle}
        />
        <input
          value={binary}
          onChange={e => setBinary(e.target.value)}
          placeholder="Binaire (ex: ./target)"
          style={inputStyle}
        />
        <button onClick={() => setTerminal('')}
          style={{ ...btnStyle, background: 'rgba(255,255,255,0.06)', minWidth: 80 }}>
          Effacer
        </button>
      </div>

      {/* C2 Control Panel */}
      <div style={c2PanelStyle}>
        <div style={{ color: '#a78bfa', fontWeight: 600, fontSize: '0.8rem', marginBottom: 10, letterSpacing: 2 }}>
          🧠 C2 FRAMEWORKS — CONTRÔLE EN TEMPS RÉEL
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {Object.entries(C2_META).map(([name, meta]) => {
            const status = c2Status[name] || {}
            const running = status.running
            const loading = c2Loading[name]
            const isLogOpen = activeC2Log === name
            return (
              <div key={name} style={{
                background: running ? `${meta.color}18` : 'rgba(255,255,255,0.02)',
                border: `1px solid ${running ? meta.color : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 8, padding: '8px 10px',
                transition: 'all 0.3s',
                boxShadow: running ? `0 0 12px ${meta.color}40` : 'none',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: '1rem' }}>{meta.icon}</span>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: running ? '#10b981' : '#6b7280',
                    boxShadow: running ? '0 0 6px #10b981' : 'none',
                    display: 'inline-block',
                  }} />
                </div>
                <div style={{ color: meta.color, fontWeight: 700, fontSize: '0.72rem', marginBottom: 1 }}>
                  {meta.label}
                </div>
                <div style={{ color: 'var(--text-dim)', fontSize: '0.6rem', marginBottom: 4 }}>
                  {running
                    ? `PID ${status.pid} · port ${meta.port} · ${status.uptime || '...'}`
                    : `port ${meta.port}`}
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {!running ? (
                    <button
                      onClick={() => startC2(name)}
                      disabled={loading}
                      style={{ ...c2BtnStyle, borderColor: meta.color, color: meta.color, flex: 1 }}
                    >
                      {loading ? '...' : '▶ Start'}
                    </button>
                  ) : (
                    <button
                      onClick={() => stopC2(name)}
                      disabled={loading}
                      style={{ ...c2BtnStyle, borderColor: '#ef4444', color: '#ef4444', flex: 1 }}
                    >
                      {loading ? '...' : '■ Stop'}
                    </button>
                  )}
                  <button
                    onClick={() => setActiveC2Log(isLogOpen ? null : name)}
                    style={{ ...c2BtnStyle, borderColor: 'rgba(255,255,255,0.15)', color: 'var(--text-dim)' }}
                  >
                    📋
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Viewer de logs C2 */}
        {activeC2Log && (
          <div style={{ marginTop: 8 }}>
            <div style={{ color: 'var(--text-dim)', fontSize: '0.65rem', marginBottom: 4, letterSpacing: 1 }}>
              LOGS — {activeC2Log.toUpperCase()}
              {c2Status[activeC2Log]?.running && (
                <span style={{ color: '#10b981', marginLeft: 6 }}>● LIVE</span>
              )}
            </div>
            <pre style={{
              background: 'rgba(0,0,0,0.7)',
              border: `1px solid ${C2_META[activeC2Log]?.color || '#333'}40`,
              borderRadius: 6, padding: 10,
              color: C2_META[activeC2Log]?.color || '#7fffb0',
              fontSize: '0.65rem', fontFamily: 'monospace',
              maxHeight: 160, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            }}>
              {(c2Logs[activeC2Log] || []).join('\n') || `(${activeC2Log} non démarré ou aucun log)`}
            </pre>
          </div>
        )}
      </div>

      {/* Pipeline fuzzing → exploit */}
      <div style={pipelineBox}>
        <div style={{ color: 'var(--gold)', fontWeight: 600, fontSize: '0.8rem', marginBottom: 8, letterSpacing: 2 }}>
          ⚡ PIPELINE : FUZZING → CRASH → REVERSE → EXPLOIT
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {PIPELINE_STAGES.map((s, i) => (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <button
                onClick={() => runPipeline(s.id)}
                disabled={running}
                style={{
                  ...btnStyle,
                  background: pipeStage === s.id
                    ? 'rgba(249,115,22,0.3)' : 'rgba(249,115,22,0.08)',
                  border: '1px solid rgba(249,115,22,0.4)',
                  color: '#f97316',
                  minWidth: 110,
                }}
              >
                {s.icon} {s.label}
                <div style={{ fontSize: '0.62rem', opacity: 0.7 }}>{s.desc}</div>
              </button>
              {i < PIPELINE_STAGES.length - 1 && (
                <span style={{ color: 'rgba(249,115,22,0.5)', fontSize: '1.2rem' }}>→</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 4 niveaux */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {[1, 2, 3, 4].map(n => {
          const lvl = levels[n]
          if (!lvl) return null
          const style = LEVEL_STYLES[n]
          const isActive = activeLevel === n
          return (
            <div key={n}
              style={{
                border: `1px solid ${isActive ? style.border : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 10,
                background: isActive ? `${style.glow}` : 'rgba(255,255,255,0.02)',
                padding: 12,
                cursor: 'pointer',
                transition: 'all 0.2s',
                boxShadow: isActive ? `0 0 18px ${style.glow}` : 'none',
              }}
              onClick={() => setActive(isActive ? null : n)}
            >
              {/* Niveau header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: '1.1rem' }}>{lvl.icon}</span>
                <span style={{
                  background: style.badge, color: '#fff',
                  fontSize: '0.65rem', padding: '2px 6px', borderRadius: 20, fontWeight: 700,
                }}>
                  N{n}
                </span>
              </div>
              <div style={{ color: style.border, fontWeight: 700, fontSize: '0.82rem', marginBottom: 2 }}>
                {lvl.name}
              </div>
              <div style={{ color: 'var(--text-dim)', fontSize: '0.68rem', marginBottom: 8 }}>
                {lvl.impact}
              </div>

              {/* Tools rapides */}
              {isActive && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.65rem', marginBottom: 6, letterSpacing: 1 }}>
                    OUTILS ({lvl.tools_count}) — clic pour lancer
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
                    {(lvl.tools || []).map(t => (
                      <button key={t.name}
                        onClick={e => { e.stopPropagation(); quickRun(n, t.name) }}
                        disabled={running}
                        title={t.description}
                        style={{
                          background: `rgba(${hexToRgb(style.border)},0.12)`,
                          border: `1px solid ${style.border}30`,
                          color: style.border,
                          padding: '3px 8px',
                          borderRadius: 12,
                          fontSize: '0.68rem',
                          cursor: 'pointer',
                          fontFamily: 'monospace',
                        }}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Terminal */}
      <div style={{ flex: 1, minHeight: 220 }}>
        <div style={{ color: 'var(--text-dim)', fontSize: '0.68rem', marginBottom: 4, letterSpacing: 2 }}>
          TERMINAL {running && <span style={{ color: '#f97316' }}>● EN COURS</span>}
        </div>
        <pre
          ref={termRef}
          style={{
            background: 'rgba(0,0,0,0.6)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 8,
            padding: 12,
            color: '#7fffb0',
            fontSize: '0.72rem',
            fontFamily: 'monospace',
            minHeight: 180,
            maxHeight: 340,
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {terminal || 'L\'Œil de Dieu — Terminal offensif\nSélectionne un niveau ou lance le pipeline...\n'}
        </pre>
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return r ? `${parseInt(r[1],16)},${parseInt(r[2],16)},${parseInt(r[3],16)}` : '255,255,255'
}

const inputStyle = {
  flex: 1,
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: '0.78rem',
  fontFamily: 'monospace',
  outline: 'none',
}

const btnStyle = {
  background: 'rgba(56,189,248,0.1)',
  border: '1px solid rgba(56,189,248,0.3)',
  color: 'var(--elec)',
  borderRadius: 8,
  padding: '6px 10px',
  cursor: 'pointer',
  fontSize: '0.75rem',
  fontFamily: 'inherit',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 1,
}

const pipelineBox = {
  background: 'rgba(249,115,22,0.05)',
  border: '1px solid rgba(249,115,22,0.2)',
  borderRadius: 10,
  padding: 12,
}

const c2PanelStyle = {
  background: 'rgba(167,139,250,0.04)',
  border: '1px solid rgba(167,139,250,0.2)',
  borderRadius: 10,
  padding: 12,
}

const c2BtnStyle = {
  background: 'transparent',
  border: '1px solid',
  borderRadius: 6,
  padding: '3px 6px',
  cursor: 'pointer',
  fontSize: '0.65rem',
  fontFamily: 'monospace',
  transition: 'opacity 0.2s',
}
