import { useState, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { auth } from '../utils/auth'

const BASE = '/api'

async function apiFetch(path, opts = {}) {
  const token = auth.getToken()
  const headers = { ...opts.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) { auth.clear(); window.location.reload() }
  return res
}

export default function VisionView() {
  const [mode,      setMode]     = useState('upload')   // 'upload' | 'screenshot'
  const [prompt,    setPrompt]   = useState('')
  const [preview,   setPreview]  = useState(null)       // { src, b64, mediaType, name }
  const [analysis,  setAnalysis] = useState('')
  const [loading,   setLoading]  = useState(false)
  const [error,     setError]    = useState('')
  const [history,   setHistory]  = useState([])
  const [dragOver,  setDragOver] = useState(false)
  const fileRef = useRef(null)

  const DEFAULT_PROMPTS = [
    'Décris ce que tu vois en détail.',
    "C'est quel outil de sécurité ? Explique.",
    'Analyse ce code ou terminal. Que se passe-t-il ?',
    'Y a-t-il des vulnérabilités ou problèmes visibles ?',
    'Résume ce document ou cette interface.',
  ]

  const effectivePrompt = prompt.trim() || DEFAULT_PROMPTS[0]

  // ── Chargement fichier ──────────────────────────────────────────────────────
  const loadFile = (file) => {
    if (!file) return
    if (!file.type.startsWith('image/')) { setError('Fichier non supporté — PNG, JPEG, WEBP, GIF uniquement.'); return }
    setError('')
    const reader = new FileReader()
    reader.onload = (e) => {
      setPreview({ src: e.target.result, name: file.name, file })
      setAnalysis('')
    }
    reader.readAsDataURL(file)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false)
    loadFile(e.dataTransfer.files[0])
  }, [])

  // ── Analyse upload ──────────────────────────────────────────────────────────
  const analyzeUpload = async () => {
    if (!preview?.file) return
    setLoading(true); setError(''); setAnalysis('')
    try {
      const form = new FormData()
      form.append('file', preview.file)
      form.append('prompt', effectivePrompt)
      const res = await apiFetch('/vision/upload', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Erreur analyse'); return }
      setAnalysis(data.analysis)
      pushHistory({ src: preview.src, name: preview.name, analysis: data.analysis, prompt: effectivePrompt })
    } catch (e) { setError('Erreur réseau : ' + e.message) }
    finally { setLoading(false) }
  }

  // ── Capture écran ───────────────────────────────────────────────────────────
  const takeScreenshot = async () => {
    setLoading(true); setError(''); setAnalysis(''); setPreview(null)
    try {
      const params = effectivePrompt !== DEFAULT_PROMPTS[0] ? `?prompt=${encodeURIComponent(effectivePrompt)}` : ''
      const res = await apiFetch(`/vision/screenshot${params}`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Capture échouée'); return }
      const src = `data:${data.media_type};base64,${data.image_b64}`
      setPreview({ src, name: 'screenshot.png' })
      setAnalysis(data.analysis)
      pushHistory({ src, name: 'Capture écran', analysis: data.analysis, prompt: effectivePrompt })
    } catch (e) { setError('Erreur réseau : ' + e.message) }
    finally { setLoading(false) }
  }

  const pushHistory = (item) =>
    setHistory(h => [{ ...item, ts: new Date() }, ...h].slice(0, 10))

  const loadFromHistory = (item) => {
    setPreview({ src: item.src, name: item.name })
    setAnalysis(item.analysis)
    setPrompt(item.prompt)
    setError('')
  }

  return (
    <div className="vis-layout">
      {/* ── Colonne gauche : contrôles ─────────────────────────────────────── */}
      <div className="vis-left">
        {/* Mode selector */}
        <div className="vis-mode-row">
          <button className={`vis-mode-btn ${mode==='upload'?'active':''}`} onClick={() => setMode('upload')}>
            📁 Upload
          </button>
          <button className={`vis-mode-btn ${mode==='screenshot'?'active':''}`} onClick={() => setMode('screenshot')}>
            🖥️ Capture écran
          </button>
        </div>

        {/* Zone upload */}
        {mode === 'upload' && (
          <div
            className={`vis-drop-zone ${dragOver ? 'drag-over' : ''} ${preview ? 'has-file' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
          >
            <input ref={fileRef} type="file" accept="image/*" style={{ display:'none' }}
              onChange={e => loadFile(e.target.files[0])} />
            {preview ? (
              <div className="vis-preview-thumb">
                <img src={preview.src} alt={preview.name} />
                <div className="vis-preview-name">{preview.name}</div>
              </div>
            ) : (
              <>
                <div className="vis-drop-icon">🖼️</div>
                <div className="vis-drop-text">Glisse une image ici<br /><span>ou clique pour choisir</span></div>
                <div className="vis-drop-hint">PNG · JPEG · WEBP · GIF — max 20 MB</div>
              </>
            )}
          </div>
        )}

        {/* Zone screenshot */}
        {mode === 'screenshot' && (
          <div className="vis-screenshot-zone">
            <div className="vis-screen-icon">🖥️</div>
            <div className="vis-screen-text">Capture l'écran complet<br /><span>via ImageMagick (DISPLAY={window._display || ':0.0'})</span></div>
          </div>
        )}

        {/* Prompt */}
        <div className="vis-prompt-section">
          <label className="vis-label">Question / Instructions</label>
          <textarea
            className="cv-textarea vis-prompt-ta"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder={DEFAULT_PROMPTS[0]}
            rows={3}
          />
          <div className="vis-quick-prompts">
            {DEFAULT_PROMPTS.slice(1).map((p, i) => (
              <button key={i} className="vis-quick-btn" onClick={() => setPrompt(p)}>{p}</button>
            ))}
          </div>
        </div>

        {/* Bouton analyser */}
        {mode === 'upload' && (
          <button className="vis-analyze-btn" onClick={analyzeUpload}
            disabled={loading || !preview}>
            {loading ? <><span className="login-spinner" /> Analyse en cours…</> : '🔍 Analyser'}
          </button>
        )}
        {mode === 'screenshot' && (
          <button className="vis-analyze-btn" onClick={takeScreenshot} disabled={loading}>
            {loading ? <><span className="login-spinner" /> Capture + analyse…</> : '📸 Capturer & analyser'}
          </button>
        )}

        {error && <div className="cv-error vis-error">{error}</div>}

        {/* Historique */}
        {history.length > 0 && (
          <div className="vis-history">
            <div className="vis-label" style={{ marginBottom: 6 }}>Historique</div>
            {history.map((item, i) => (
              <button key={i} className="vis-hist-entry" onClick={() => loadFromHistory(item)}>
                <img src={item.src} alt="" className="vis-hist-thumb" />
                <div className="vis-hist-info">
                  <div className="vis-hist-name">{item.name}</div>
                  <div className="vis-hist-time">{item.ts.toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' })}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Colonne droite : résultat ──────────────────────────────────────── */}
      <div className="vis-right">
        {preview && (
          <div className="vis-result-image">
            <img src={preview.src} alt={preview.name} />
          </div>
        )}
        {!analysis && !loading && (
          <div className="vis-placeholder">
            <div className="vis-placeholder-icon">👁️</div>
            <div>L'analyse apparaîtra ici</div>
          </div>
        )}
        {loading && (
          <div className="vis-placeholder">
            <div className="vis-thinking-eye">
              <svg viewBox="0 0 120 80" width="90" height="60">
                <defs>
                  <radialGradient id="iris-v" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#a78bfa" />
                    <stop offset="100%" stopColor="#1e1b4b" />
                  </radialGradient>
                </defs>
                <ellipse cx="60" cy="40" rx="55" ry="28" fill="none" stroke="#7c3aed" strokeWidth="1.5" opacity="0.6"/>
                <circle cx="60" cy="40" r="18" fill="url(#iris-v)"/>
                <circle cx="60" cy="40" r="9" fill="#0a0a1a"/>
                <circle cx="65" cy="35" r="3" fill="white" opacity="0.8"/>
              </svg>
            </div>
            <div style={{ color: 'var(--text2)', fontSize: '0.85rem' }}>Vision en cours…</div>
          </div>
        )}
        {analysis && (
          <div className="vis-analysis">
            <div className="vis-analysis-header">
              <span className="vis-analysis-icon">👁️</span>
              <span>Analyse Claude Vision</span>
            </div>
            <div className="vis-analysis-body">
              <ReactMarkdown>{analysis}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
