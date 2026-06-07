/**
 * SELF-IMPROVE — Apprentissage continu, gaps de compétences, recommandations.
 */
import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

function SkillBar({ skill, value, max = 10 }) {
  const pct = Math.min(100, (value / max) * 100)
  const color = pct < 30 ? '#ef4444' : pct < 60 ? '#fbbf24' : '#4ade80'
  return (
    <div className="skill-bar-row">
      <span className="skill-bar-label">{skill}</span>
      <div className="skill-bar-track">
        <div className="skill-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="skill-bar-score" style={{ color }}>{value}/{max}</span>
    </div>
  )
}

function SkillGapsPanel({ gaps }) {
  if (!gaps?.length) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📊</span>Skill Gaps</div>
      <div className="aegis-feed-empty">Aucune donnée de compétences disponible</div>
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📊</span>Skill Gaps Radar</div>
      <div style={{ padding: '8px 0' }}>
        {gaps.map((g, i) => (
          <SkillBar
            key={i}
            skill={g.skill || g.name || g.category}
            value={g.score || g.level || g.value || 0}
            max={g.max || 10}
          />
        ))}
      </div>
    </div>
  )
}

function LearningsFeed({ techniques }) {
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">📚</span>
        <span>Apprentissages récents</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text3)' }}>
          {techniques?.length || 0}
        </span>
      </div>
      <div className="aegis-feed">
        {!techniques?.length ? (
          <div className="aegis-feed-empty">Aucune technique apprise récemment</div>
        ) : techniques.slice(0, 20).map((t, i) => (
          <div key={i} className="aegis-feed-row">
            <span style={{ fontSize: '0.8rem' }}>{t.icon || '▸'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text)' }}>
                {t.name || t.technique || t.title || '—'}
              </div>
              {(t.category || t.domain) && (
                <div style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                  {t.category || t.domain}
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right' }}>
              {t.success_rate !== undefined && (
                <div style={{
                  fontSize: '0.65rem', fontWeight: 700,
                  color: t.success_rate > 70 ? '#4ade80' : t.success_rate > 40 ? '#fbbf24' : '#ef4444',
                }}>
                  {t.success_rate}%
                </div>
              )}
              {t.learned_at && (
                <div style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
                  {new Date(t.learned_at).toLocaleDateString('fr-FR')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RecommendationsPanel({ recs }) {
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header">
        <span className="aegis-panel-icon">💡</span>
        <span>Recommandations</span>
      </div>
      {!recs?.length ? (
        <div className="aegis-feed-empty">Aucune recommandation disponible</div>
      ) : recs.map((r, i) => (
        <div key={i} className="self-improve-rec">
          <div className="self-improve-rec-title">
            {r.priority === 'high' && <span style={{ color: '#ef4444' }}>⚡ </span>}
            {r.title || r.name || r.recommendation || '—'}
          </div>
          {(r.description || r.reason) && (
            <div className="self-improve-rec-desc">{r.description || r.reason}</div>
          )}
          {r.resources?.length > 0 && (
            <div style={{ marginTop: 4, fontSize: '0.65rem', color: 'var(--text3)' }}>
              Ressources : {r.resources.join(' · ')}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function WeeklyDigest({ digest }) {
  if (!digest) return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📅</span>Digest hebdomadaire</div>
      <div className="aegis-feed-empty">Aucun digest disponible</div>
    </div>
  )
  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📅</span>Digest hebdomadaire</div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text2)', lineHeight: 1.6, padding: '4px 0' }}>
        {typeof digest === 'string' ? digest : (
          <>
            {digest.summary && <p>{digest.summary}</p>}
            {digest.stats && (
              <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
                {Object.entries(digest.stats).map(([k, v]) => (
                  <div key={k} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent)' }}>{v}</div>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>{k}</div>
                  </div>
                ))}
              </div>
            )}
            {digest.highlights?.length > 0 && (
              <ul style={{ marginTop: 8, paddingLeft: 16 }}>
                {digest.highlights.map((h, i) => <li key={i}>{h}</li>)}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function OutcomeForm() {
  const [form, setForm] = useState({
    target: '', technique: '', success: true, notes: ''
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState(null)
  const [saved, setSaved]   = useState(false)

  const submit = async () => {
    if (!form.target || !form.technique) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await apiFetch('/self-improve/outcome', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(`Erreur ${res.status}`)
      setSaved(true)
      setForm({ target: '', technique: '', success: true, notes: '' })
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="aegis-panel">
      <div className="aegis-panel-header"><span className="aegis-panel-icon">📝</span>Enregistrer un résultat</div>

      <div className="creds-form-grid">
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Cible</div>
          <input className="aegis-target-input" style={{ width: '100%' }} placeholder="192.168.1.10 / lab-name"
            value={form.target} onChange={e => setForm(p => ({ ...p, target: e.target.value }))} />
        </div>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Technique</div>
          <input className="aegis-target-input" style={{ width: '100%' }} placeholder="ex: SQLi, PTH, Kerberoast…"
            value={form.technique} onChange={e => setForm(p => ({ ...p, technique: e.target.value }))} />
        </div>
      </div>

      <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>Résultat :</span>
        {[true, false].map(s => (
          <button
            key={String(s)}
            onClick={() => setForm(p => ({ ...p, success: s }))}
            style={{
              padding: '3px 12px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
              background: form.success === s ? (s ? '#4ade8022' : '#ef444422') : 'transparent',
              border: `1px solid ${form.success === s ? (s ? '#4ade80' : '#ef4444') : 'var(--border)'}`,
              color: form.success === s ? (s ? '#4ade80' : '#ef4444') : 'var(--text3)',
            }}
          >
            {s ? '✓ Succès' : '✗ Échec'}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>Notes</div>
        <textarea
          className="forensics-ps-input"
          rows={3}
          style={{ width: '100%' }}
          placeholder="Observations, difficultés, apprentissages…"
          value={form.notes}
          onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
        />
      </div>

      {error && <div className="osint-error-banner">{error}</div>}
      {saved  && <div className="osint-success-banner">Résultat enregistré.</div>}

      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="aegis-launch-btn" onClick={submit} disabled={saving || !form.target || !form.technique}>
          {saving ? '⏳ Sauvegarde…' : '▶ Enregistrer'}
        </button>
      </div>
    </div>
  )
}

export default function SelfImproveView() {
  const [gaps,    setGaps]    = useState(null)
  const [techniques, setTechniques] = useState(null)
  const [recs,    setRecs]    = useState(null)
  const [digest,  setDigest]  = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.allSettled([
        apiFetch('/self-improve/gaps').then(r => r.json()).then(d => setGaps(d.gaps || d || [])).catch(() => {}),
        apiFetch('/self-improve/techniques').then(r => r.json()).then(d => setTechniques(d.techniques || d || [])).catch(() => {}),
        apiFetch('/self-improve/recommend/general').then(r => r.json()).then(d => setRecs(d.recommendations || d || [])).catch(() => {}),
        apiFetch('/self-improve/digest').then(r => r.json()).then(d => setDigest(d.digest || d || null)).catch(() => {}),
      ])
      setLoading(false)
    }
    load()
    const t = setInterval(load, 5 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  if (loading) return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🧠</span>
          <div><div className="aegis-title">SELF-IMPROVE</div></div>
        </div>
      </div>
      <div className="aegis-panel"><div className="aegis-feed-empty">Chargement…</div></div>
    </div>
  )

  return (
    <div className="osint-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">🧠</span>
          <div>
            <div className="aegis-title">SELF-IMPROVE</div>
            <div className="aegis-subtitle">Skill Gaps · Apprentissages · Recommandations · Digest</div>
          </div>
        </div>
      </div>

      <div className="osint-grid">
        <SkillGapsPanel gaps={Array.isArray(gaps) ? gaps : []} />
        <LearningsFeed techniques={Array.isArray(techniques) ? techniques : []} />
        <RecommendationsPanel recs={Array.isArray(recs) ? recs : []} />
        <WeeklyDigest digest={digest} />
        <OutcomeForm />
      </div>
    </div>
  )
}
