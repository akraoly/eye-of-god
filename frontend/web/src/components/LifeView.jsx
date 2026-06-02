import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

const api = (path, opts) => apiFetch(path, opts).then(r => r.json())

const PRIORITY_LABEL = { 1: '🔴 Critique', 2: '🟠 Haute', 3: '🟡 Moyenne', 4: '🟢 Basse' }
const FREQ_LABEL     = { daily: 'Quotidien', weekly: 'Hebdo', monthly: 'Mensuel' }

export default function LifeView() {
  const [tab,    setTab]    = useState('goals')
  const [dash,   setDash]   = useState(null)
  const [loading,setLoading]= useState(false)

  const load = async () => {
    setLoading(true)
    try { setDash(await api('/life/dashboard')) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const goals  = dash?.goals?.active  || []
  const habits = dash?.habits?.active || []
  const done   = dash?.goals?.done    || 0
  const total  = dash?.goals?.total   || 0
  const rate   = total > 0 ? Math.round((done / total) * 100) : 0
  const topStreak = dash?.habits?.top_streak

  return (
    <div className="panel-view">
      {/* Stats rapides */}
      <div className="lv-stats-bar">
        <StatPill icon="🎯" label="Objectifs actifs"  value={goals.length} />
        <StatPill icon="✅" label="Complétés"         value={`${done}/${total} (${rate}%)`} />
        <StatPill icon="🔥" label="Meilleure série"   value={topStreak ? `${topStreak.name} — ${topStreak.streak}j` : '—'} />
        <StatPill icon="🌀" label="Habitudes actives" value={habits.length} />
      </div>

      {/* Onglets */}
      <div className="panel-tabs">
        <button className={`panel-tab ${tab==='goals'?'active':''}`}  onClick={() => setTab('goals')}>🎯 Objectifs</button>
        <button className={`panel-tab ${tab==='habits'?'active':''}`} onClick={() => setTab('habits')}>🔥 Habitudes</button>
      </div>

      <div className="panel-body">
        {loading && <div className="cv-hint">Chargement…</div>}
        {!loading && tab === 'goals'  && <GoalsTab  goals={goals}  onRefresh={load} />}
        {!loading && tab === 'habits' && <HabitsTab habits={habits} onRefresh={load} />}
      </div>
    </div>
  )
}

function GoalsTab({ goals, onRefresh }) {
  const [showAdd, setShowAdd] = useState(false)

  const updateProgress = async (id, progress) => {
    await api(`/life/goals/${id}`, { method:'PUT', body: JSON.stringify({ progress: parseInt(progress) }) })
    onRefresh()
  }

  const del = async (id) => {
    await api(`/life/goals/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <div className="lv-section">
      <button className="cv-btn lv-add-btn" onClick={() => setShowAdd(v => !v)}>
        {showAdd ? '✕ Annuler' : '+ Nouvel objectif'}
      </button>
      {showAdd && <GoalForm onSaved={() => { setShowAdd(false); onRefresh() }} />}

      {goals.length === 0 && <div className="cv-hint">Aucun objectif actif. Crée-en un !</div>}
      {goals.map(g => (
        <div key={g.id} className="lv-goal-card">
          <div className="lv-goal-header">
            <span className="lv-goal-title">{g.title}</span>
            <span className="lv-priority-badge">{PRIORITY_LABEL[g.priority] || g.priority}</span>
            <button className="kv-del-btn" onClick={() => del(g.id)} title="Supprimer">✕</button>
          </div>
          {g.description && <div className="lv-goal-desc">{g.description}</div>}
          <div className="lv-progress-row">
            <div className="lv-progress-track">
              <div className="lv-progress-fill" style={{ width: `${g.progress}%` }} />
            </div>
            <span className="lv-progress-pct">{g.progress}%</span>
            <input type="range" min="0" max="100" value={g.progress}
              onChange={e => updateProgress(g.id, e.target.value)}
              className="lv-slider" title="Glisse pour mettre à jour" />
          </div>
          {g.deadline && (
            <div className="lv-deadline">
              📅 {new Date(g.deadline).toLocaleDateString('fr-FR', { day:'numeric', month:'long', year:'numeric' })}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function GoalForm({ onSaved }) {
  const [title,    setTitle]    = useState('')
  const [desc,     setDesc]     = useState('')
  const [category, setCategory] = useState('general')
  const [priority, setPriority] = useState(3)
  const [deadline, setDeadline] = useState('')
  const [loading,  setLoading]  = useState(false)

  const save = async () => {
    if (!title.trim()) return
    setLoading(true)
    try {
      await api('/life/goals', { method:'POST', body: JSON.stringify({ title, description: desc, category, priority: Number(priority), deadline: deadline || undefined }) })
      onSaved()
    } finally { setLoading(false) }
  }

  return (
    <div className="lv-add-form">
      <input className="cv-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="Titre de l'objectif *" />
      <textarea className="cv-textarea" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Description (optionnel)" rows={2} />
      <div className="cv-row">
        <input className="cv-input cv-input-sm" value={category} onChange={e => setCategory(e.target.value)} placeholder="Catégorie" />
        <select className="cv-select" value={priority} onChange={e => setPriority(e.target.value)}>
          <option value={1}>🔴 Critique</option>
          <option value={2}>🟠 Haute</option>
          <option value={3}>🟡 Moyenne</option>
          <option value={4}>🟢 Basse</option>
        </select>
        <input type="date" className="cv-input cv-input-sm" value={deadline} onChange={e => setDeadline(e.target.value)} />
        <button className="cv-btn cv-btn-green" onClick={save} disabled={loading || !title.trim()}>
          {loading ? '…' : 'Créer'}
        </button>
      </div>
    </div>
  )
}

function HabitsTab({ habits, onRefresh }) {
  const [showAdd, setShowAdd] = useState(false)

  const done = async (id) => {
    await api(`/life/habits/${id}/done`, { method: 'POST' })
    onRefresh()
  }

  const del = async (id) => {
    await api(`/life/habits/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <div className="lv-section">
      <button className="cv-btn lv-add-btn" onClick={() => setShowAdd(v => !v)}>
        {showAdd ? '✕ Annuler' : '+ Nouvelle habitude'}
      </button>
      {showAdd && <HabitForm onSaved={() => { setShowAdd(false); onRefresh() }} />}

      {habits.length === 0 && <div className="cv-hint">Aucune habitude. Commence par en créer une !</div>}
      {habits.map(h => (
        <div key={h.id} className="lv-habit-card">
          <div className="lv-habit-info">
            <span className="lv-habit-name">{h.name}</span>
            <span className="lv-freq-badge">{FREQ_LABEL[h.frequency] || h.frequency}</span>
          </div>
          <div className="lv-habit-footer">
            <div className="lv-streak">
              🔥 <strong>{h.streak}</strong> jours consécutifs
            </div>
            {h.last_done && (
              <span className="lv-last-done">
                dernière fois {new Date(h.last_done).toLocaleDateString('fr-FR')}
              </span>
            )}
            <div className="lv-habit-actions">
              <button className="cv-btn cv-btn-green lv-done-btn" onClick={() => done(h.id)}>✓ Fait</button>
              <button className="kv-del-btn" onClick={() => del(h.id)} title="Supprimer">✕</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function HabitForm({ onSaved }) {
  const [name,    setName]    = useState('')
  const [freq,    setFreq]    = useState('daily')
  const [desc,    setDesc]    = useState('')
  const [loading, setLoading] = useState(false)

  const save = async () => {
    if (!name.trim()) return
    setLoading(true)
    try {
      await api('/life/habits', { method:'POST', body: JSON.stringify({ name, description: desc, frequency: freq }) })
      onSaved()
    } finally { setLoading(false) }
  }

  return (
    <div className="lv-add-form">
      <div className="cv-row">
        <input className="cv-input" value={name} onChange={e => setName(e.target.value)} placeholder="Nom de l'habitude *" />
        <select className="cv-select" value={freq} onChange={e => setFreq(e.target.value)}>
          <option value="daily">Quotidien</option>
          <option value="weekly">Hebdo</option>
          <option value="monthly">Mensuel</option>
        </select>
        <button className="cv-btn cv-btn-green" onClick={save} disabled={loading || !name.trim()}>
          {loading ? '…' : 'Créer'}
        </button>
      </div>
      <input className="cv-input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Description (optionnel)" />
    </div>
  )
}

function StatPill({ icon, label, value }) {
  return (
    <div className="lv-stat-pill">
      <span className="lv-stat-icon">{icon}</span>
      <div>
        <div className="lv-stat-val">{value}</div>
        <div className="lv-stat-lbl">{label}</div>
      </div>
    </div>
  )
}
