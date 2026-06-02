import { useState } from 'react'
import { apiFetch } from '../utils/auth'

const api = (path, opts) => apiFetch(path, opts).then(r => r.json())

export default function CodeView() {
  const [tab, setTab] = useState('explorer')
  return (
    <div className="panel-view">
      <div className="panel-tabs">
        {[['explorer','🗂️ Explorer'],['terminal','⚡ Terminal'],['git','🔀 Git']].map(([id,label]) => (
          <button key={id} className={`panel-tab ${tab===id?'active':''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <div className="panel-body">
        {tab === 'explorer' && <ExplorerTab />}
        {tab === 'terminal' && <TerminalTab />}
        {tab === 'git'      && <GitTab />}
      </div>
    </div>
  )
}

function ExplorerTab() {
  const [path,    setPath]    = useState('/home/kali/eye-of-god')
  const [result,  setResult]  = useState(null)
  const [tree,    setTree]    = useState('')
  const [loading, setLoading] = useState(false)

  const explore = async () => {
    setLoading(true); setResult(null); setTree('')
    try {
      const [info, treeRes] = await Promise.all([
        api('/code/explore', { method:'POST', body: JSON.stringify({ path }) }),
        api('/code/tree',    { method:'POST', body: JSON.stringify({ path, max_depth: 4 }) }),
      ])
      setResult(info); setTree(treeRes.tree || '')
    } finally { setLoading(false) }
  }

  return (
    <div className="cv-section">
      <div className="cv-row">
        <input className="cv-input" value={path} onChange={e => setPath(e.target.value)}
          placeholder="/chemin/du/projet" onKeyDown={e => e.key==='Enter' && explore()} />
        <button className="cv-btn" onClick={explore} disabled={loading}>
          {loading ? '…' : 'Explorer'}
        </button>
      </div>
      {result && !result.error && (
        <div className="cv-stats-grid">
          <Stat label="Fichiers"    value={result.total_files} />
          <Stat label="Lignes"      value={result.total_lines?.toLocaleString()} />
          <Stat label="Langages"    value={result.languages?.join(', ') || '—'} />
          <Stat label="Frameworks"  value={result.frameworks?.join(', ') || '—'} />
        </div>
      )}
      {result?.error && <div className="cv-error">{result.error}</div>}
      {tree && <pre className="cv-tree">{tree}</pre>}
    </div>
  )
}

function TerminalTab() {
  const [cmd,     setCmd]     = useState('')
  const [cwd,     setCwd]     = useState('/home/kali/eye-of-god')
  const [output,  setOutput]  = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])

  const run = async () => {
    if (!cmd.trim()) return
    setLoading(true)
    try {
      const res = await api('/code/run', { method:'POST', body: JSON.stringify({ command: cmd, cwd, timeout: 30 }) })
      const entry = { cmd, stdout: res.stdout||'', stderr: res.stderr||'', code: res.exit_code }
      setHistory(h => [...h.slice(-19), entry])
      setOutput(res.stdout || res.stderr || '(pas de sortie)')
      setCmd('')
    } catch { setOutput('Erreur réseau') }
    finally { setLoading(false) }
  }

  return (
    <div className="cv-section">
      <div className="cv-row">
        <input className="cv-input cv-input-sm" value={cwd} onChange={e => setCwd(e.target.value)}
          placeholder="Répertoire" style={{ flex: '0 0 220px' }} />
        <input className="cv-input" value={cmd} onChange={e => setCmd(e.target.value)}
          placeholder="Commande…" onKeyDown={e => e.key==='Enter' && run()} />
        <button className="cv-btn" onClick={run} disabled={loading || !cmd.trim()}>
          {loading ? '…' : '▶'}
        </button>
      </div>
      <div className="cv-terminal">
        {history.length === 0 && <span className="cv-hint">Entre une commande et appuie sur Entrée.</span>}
        {history.map((h, i) => (
          <div key={i} className="cv-term-entry">
            <div className="cv-term-cmd">$ {h.cmd}</div>
            {h.stdout && <pre className="cv-term-out">{h.stdout}</pre>}
            {h.stderr && <pre className="cv-term-err">{h.stderr}</pre>}
            <span className="cv-exit-code" style={{ color: h.code===0 ? '#34d399' : '#f87171' }}>
              exit {h.code}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function GitTab() {
  const [path,    setPath]    = useState('/home/kali/eye-of-god')
  const [status,  setStatus]  = useState(null)
  const [log,     setLog]     = useState([])
  const [msg,     setMsg]     = useState('')
  const [loading, setLoading] = useState(false)
  const [info,    setInfo]    = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [s, l] = await Promise.all([
        api('/code/git/status',  { method:'POST', body: JSON.stringify({ path }) }),
        api('/code/git/log',     { method:'POST', body: JSON.stringify({ path }) }),
      ])
      setStatus(s); setLog(l.commits || [])
    } finally { setLoading(false) }
  }

  const commit = async () => {
    if (!msg.trim()) return
    setLoading(true)
    try {
      const res = await api('/code/git/commit', { method:'POST', body: JSON.stringify({ path, message: msg, add_all: true }) })
      setInfo(res.message || res.error || 'Commit OK')
      setMsg(''); load()
    } finally { setLoading(false) }
  }

  return (
    <div className="cv-section">
      <div className="cv-row">
        <input className="cv-input" value={path} onChange={e => setPath(e.target.value)}
          placeholder="/chemin/du/repo" onKeyDown={e => e.key==='Enter' && load()} />
        <button className="cv-btn" onClick={load} disabled={loading}>{loading ? '…' : 'Charger'}</button>
      </div>
      {status && (
        <div className="cv-git-status">
          <span className="cv-tag">branche: {status.branch || '?'}</span>
          <span className="cv-tag">{status.modified?.length || 0} modifiés</span>
          <span className="cv-tag">{status.untracked?.length || 0} non suivis</span>
        </div>
      )}
      {log.length > 0 && (
        <div className="cv-log">
          {log.slice(0,8).map((c, i) => (
            <div key={i} className="cv-log-entry">
              <code className="cv-hash">{c.hash?.slice(0,7)}</code>
              <span className="cv-log-msg">{c.message}</span>
              <span className="cv-log-date">{c.date ? new Date(c.date).toLocaleDateString('fr-FR') : ''}</span>
            </div>
          ))}
        </div>
      )}
      <div className="cv-row" style={{ marginTop: 8 }}>
        <input className="cv-input" value={msg} onChange={e => setMsg(e.target.value)}
          placeholder="Message de commit…" onKeyDown={e => e.key==='Enter' && commit()} />
        <button className="cv-btn cv-btn-green" onClick={commit} disabled={loading || !msg.trim()}>Commit</button>
      </div>
      {info && <div className="cv-info">{info}</div>}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="cv-stat">
      <div className="cv-stat-val">{value || '—'}</div>
      <div className="cv-stat-lbl">{label}</div>
    </div>
  )
}
