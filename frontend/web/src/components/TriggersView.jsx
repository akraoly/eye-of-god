/**
 * TriggersView — Constructeur visuel IF→THEN, liste triggers, timeline
 */
import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../utils/auth'

const CONDITION_TYPES = [
  { id: 'audio_level',    label: '🎤 Niveau audio',    fields: ['threshold_db', 'duration_s'] },
  { id: 'motion',         label: '📷 Mouvement',        fields: ['camera_ip', 'sensitivity'] },
  { id: 'network_device', label: '🌐 Appareil réseau',  fields: ['ip', 'mac'] },
  { id: 'keyword',        label: '🔑 Mot-clé',          fields: ['keyword', 'source'] },
  { id: 'scheduled',      label: '⏰ Planifié',          fields: ['cron', 'timezone'] },
  { id: 'file_change',    label: '📁 Fichier modifié',  fields: ['path', 'event'] },
  { id: 'alert',          label: '🚨 Alerte SOC',       fields: ['severity', 'rule'] },
  { id: 'beacon',         label: '📡 Beacon',           fields: ['beacon_id', 'status'] },
]

const ACTION_TYPES = [
  { id: 'record_audio',   label: '⏺ Enregistrer audio', fields: ['duration', 'quality'] },
  { id: 'screenshot',     label: '📸 Capture écran',     fields: ['count', 'interval'] },
  { id: 'run_scan',       label: '🔍 Scanner réseau',    fields: ['target'] },
  { id: 'send_alert',     label: '🚨 Envoyer alerte',    fields: ['severity', 'message'] },
  { id: 'exfil_data',     label: '📤 Exfiltrer données', fields: ['channel', 'data_source'] },
  { id: 'webhook',        label: '🌐 Webhook',           fields: ['url', 'method'] },
  { id: 'telegram',       label: '✈ Telegram',           fields: ['message'] },
  { id: 'run_command',    label: '💻 Commande',          fields: ['command'] },
]

function FieldInput({ field, value, onChange }) {
  const labels = {
    threshold_db: 'Seuil dB', duration_s: 'Durée (s)', camera_ip: 'IP Caméra',
    sensitivity: 'Sensibilité', ip: 'Adresse IP', mac: 'MAC', keyword: 'Mot-clé',
    source: 'Source', cron: 'CRON', timezone: 'Fuseau', path: 'Chemin',
    event: 'Événement', severity: 'Sévérité', rule: 'Règle', beacon_id: 'Beacon ID',
    status: 'Statut', duration: 'Durée', quality: 'Qualité', count: 'Nombre',
    interval: 'Intervalle', target: 'Cible', message: 'Message', channel: 'Canal',
    data_source: 'Source', url: 'URL', method: 'Méthode', command: 'Commande',
  }
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 3 }}>{labels[field] || field}</div>
      <input
        value={value || ''}
        onChange={e => onChange(field, e.target.value)}
        placeholder={labels[field] || field}
        style={{
          width: '100%', padding: '6px 10px', background: '#000820',
          border: '1px solid var(--border2)', borderRadius: 6,
          color: 'var(--text)', fontSize: '0.76rem',
        }}
      />
    </div>
  )
}

function TypeSelector({ types, selected, onSelect }) {
  return (
    <select
      value={selected}
      onChange={e => onSelect(e.target.value)}
      style={{
        width: '100%', padding: '8px 10px', background: '#000820',
        border: '1px solid var(--border2)', borderRadius: 8,
        color: 'var(--text)', fontSize: '0.78rem', marginBottom: 12,
      }}
    >
      <option value="">— Sélectionner —</option>
      {types.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
    </select>
  )
}

// ── Trigger Card ──────────────────────────────────────────────────────────────
function TriggerCard({ trigger, onDelete, onTest, onToggle }) {
  const condType = CONDITION_TYPES.find(c => c.id === trigger.condition_type)
  const actType  = ACTION_TYPES.find(a => a.id === trigger.action_type)

  return (
    <div style={{
      background: 'var(--glass)', border: `1px solid ${trigger.enabled ? 'var(--border2)' : 'var(--border)'}`,
      borderRadius: 12, padding: 14,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)' }}>
            {trigger.name || `Trigger #${trigger.id?.slice(0, 6)}`}
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginTop: 2 }}>
            {trigger.execution_count || 0} exécution(s)
            {trigger.last_fired && ` · Dernière: ${trigger.last_fired?.slice(11, 19)}`}
          </div>
        </div>
        <div onClick={() => onToggle(trigger.id)} style={{
          width: 36, height: 20, borderRadius: 10, cursor: 'pointer',
          background: trigger.enabled ? '#4ade80' : '#ffffff20', position: 'relative', transition: 'background 0.2s',
        }}>
          <div style={{
            position: 'absolute', top: 2, left: trigger.enabled ? 18 : 2, width: 16, height: 16,
            borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
          }} />
        </div>
      </div>

      {/* IF → THEN */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{ background: '#38bdf815', border: '1px solid #38bdf830', borderRadius: 6, padding: '4px 10px', fontSize: '0.7rem', color: '#38bdf8' }}>
          IF: {condType?.label || trigger.condition_type}
        </div>
        <span style={{ color: 'var(--accent)', fontWeight: 800 }}>→</span>
        <div style={{ background: '#a78bfa15', border: '1px solid #a78bfa30', borderRadius: 6, padding: '4px 10px', fontSize: '0.7rem', color: '#a78bfa' }}>
          THEN: {actType?.label || trigger.action_type}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={() => onTest(trigger.id)} style={{
          flex: 1, padding: '5px 0', background: '#fbbf2420', border: '1px solid #fbbf2440',
          borderRadius: 6, color: '#fbbf24', cursor: 'pointer', fontSize: '0.7rem', fontWeight: 600,
        }}>⚡ Tester</button>
        <button onClick={() => onDelete(trigger.id)} style={{
          padding: '5px 12px', background: '#ef444415', border: '1px solid #ef444430',
          borderRadius: 6, color: '#ef4444', cursor: 'pointer', fontSize: '0.7rem',
        }}>✕</button>
      </div>
    </div>
  )
}

export default function TriggersView() {
  const [triggers,    setTriggers]    = useState([])
  const [timeline,    setTimeline]    = useState([])
  const [name,        setName]        = useState('')
  const [condType,    setCondType]    = useState('')
  const [condFields,  setCondFields]  = useState({})
  const [actType,     setActType]     = useState('')
  const [actFields,   setActFields]   = useState({})
  const [saving,      setSaving]      = useState(false)
  const [error,       setError]       = useState('')
  const [success,     setSuccess]     = useState('')
  const timelineRef = useRef(null)

  const loadTriggers = () => {
    apiFetch('/triggers/').then(r => r.json()).then(d => setTriggers(d.triggers || [])).catch(() => {})
  }
  const loadTimeline = () => {
    apiFetch('/triggers/logs/all').then(r => r.json()).then(d => setTimeline(d.logs || d.events || [])).catch(() => {})
  }

  useEffect(() => {
    loadTriggers()
    loadTimeline()
    const t = setInterval(() => { loadTriggers(); loadTimeline() }, 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (timelineRef.current) timelineRef.current.scrollTop = timelineRef.current.scrollHeight
  }, [timeline])

  const selectedCond = CONDITION_TYPES.find(c => c.id === condType)
  const selectedAct  = ACTION_TYPES.find(a => a.id === actType)

  const saveTrigger = async () => {
    if (!condType || !actType) { setError('Sélectionner condition ET action'); return }
    setSaving(true); setError(''); setSuccess('')
    try {
      const r = await apiFetch('/triggers/', {
        method: 'POST',
        body: JSON.stringify({
          name: name || `${condType} → ${actType}`,
          condition_type: condType,
          condition_params: condFields,
          action_type: actType,
          action_params: actFields,
          enabled: true,
        }),
      })
      if (!r.ok) throw new Error('Erreur création')
      setSuccess('Trigger créé !')
      setName(''); setCondType(''); setCondFields({}); setActType(''); setActFields({})
      loadTriggers()
    } catch (e) { setError(e.message) }
    setSaving(false)
  }

  const deleteTrigger = async (id) => {
    await apiFetch(`/triggers/${id}`, { method: 'DELETE' }).catch(() => {})
    setTriggers(prev => prev.filter(t => t.id !== id))
  }

  const testTrigger = async (id) => {
    await apiFetch(`/triggers/${id}/test`, { method: 'POST' }).catch(() => {})
    loadTimeline()
  }

  const toggleTrigger = async (id) => {
    const trigger = triggers.find(t => t.id === id)
    if (!trigger) return
    await apiFetch(`/triggers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !trigger.enabled }),
    }).catch(() => {})
    setTriggers(prev => prev.map(t => t.id === id ? { ...t, enabled: !t.enabled } : t))
  }

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span style={{ fontSize: 28 }}>⚡</span>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>
            TRIGGERS
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1 }}>
            Automatisation · IF→THEN · Événements
          </div>
        </div>
        <span style={{ marginLeft: 'auto', background: '#ffffff10', borderRadius: 8, padding: '4px 12px', color: 'var(--text2)', fontSize: '0.75rem' }}>
          {triggers.filter(t => t.enabled).length}/{triggers.length} actifs
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Builder */}
        <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 14 }}>CRÉER UN TRIGGER</div>

          {/* Name */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text3)', marginBottom: 4 }}>Nom</div>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Ex: Alerte micro cuisine…"
              style={{ width: '100%', padding: '7px 10px', background: '#000820', border: '1px solid var(--border2)', borderRadius: 8, color: 'var(--text)', fontSize: '0.8rem' }}
            />
          </div>

          <div className="trigger-builder" style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 16 }}>
            {/* Condition */}
            <div style={{ flex: 1, background: '#38bdf80a', border: '1px solid #38bdf830', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: '0.65rem', color: '#38bdf8', fontWeight: 700, marginBottom: 8, letterSpacing: 1 }}>SI (CONDITION)</div>
              <TypeSelector types={CONDITION_TYPES} selected={condType} onSelect={t => { setCondType(t); setCondFields({}) }} />
              {selectedCond?.fields.map(f => (
                <FieldInput key={f} field={f} value={condFields[f]} onChange={(k, v) => setCondFields(prev => ({ ...prev, [k]: v }))} />
              ))}
            </div>

            {/* Arrow */}
            <div style={{ display: 'flex', alignItems: 'center', paddingTop: 48 }}>
              <div style={{ fontSize: '1.5rem', color: 'var(--accent)', fontWeight: 900 }}>→</div>
            </div>

            {/* Action */}
            <div style={{ flex: 1, background: '#a78bfa0a', border: '1px solid #a78bfa30', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: '0.65rem', color: '#a78bfa', fontWeight: 700, marginBottom: 8, letterSpacing: 1 }}>ALORS (ACTION)</div>
              <TypeSelector types={ACTION_TYPES} selected={actType} onSelect={t => { setActType(t); setActFields({}) }} />
              {selectedAct?.fields.map(f => (
                <FieldInput key={f} field={f} value={actFields[f]} onChange={(k, v) => setActFields(prev => ({ ...prev, [k]: v }))} />
              ))}
            </div>
          </div>

          {error   && <div style={{ color: '#ef4444', fontSize: '0.75rem', marginBottom: 8 }}>⚠ {error}</div>}
          {success && <div style={{ color: '#4ade80', fontSize: '0.75rem', marginBottom: 8 }}>✓ {success}</div>}

          <button onClick={saveTrigger} disabled={saving} style={{
            width: '100%', padding: '10px 0', background: 'var(--accent2)',
            border: 'none', borderRadius: 8, color: '#000', cursor: 'pointer',
            fontWeight: 800, fontSize: '0.85rem',
          }}>
            {saving ? '⟳ Enregistrement…' : '⚡ Créer le Trigger'}
          </button>
        </div>

        {/* Timeline */}
        <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 14 }}>TIMELINE DES EXÉCUTIONS</div>
          <div ref={timelineRef} style={{ height: 380, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {timeline.length === 0 ? (
              <div style={{ textAlign: 'center', paddingTop: 60, color: 'var(--text3)', fontSize: '0.78rem' }}>
                Aucune exécution récente
              </div>
            ) : timeline.map((evt, i) => (
              <div key={i} style={{
                display: 'flex', gap: 10, padding: '7px 10px', background: '#ffffff06',
                borderRadius: 8, borderLeft: `3px solid ${evt.success ? '#4ade80' : '#ef4444'}`,
                fontSize: '0.72rem',
              }}>
                <span style={{ color: 'var(--text3)', whiteSpace: 'nowrap' }}>{evt.timestamp?.slice(11, 19)}</span>
                <span style={{ color: 'var(--text)', flex: 1 }}>
                  <span style={{ color: '#38bdf8' }}>{evt.trigger_name || evt.trigger_id?.slice(0, 8)}</span>
                  {' · '}
                  <span style={{ color: evt.success ? '#4ade80' : '#ef4444' }}>
                    {evt.success ? '✓' : '✗'} {evt.message || (evt.success ? 'OK' : 'Erreur')}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trigger list */}
      <div style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 12, padding: 18 }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 16 }}>
          TRIGGERS ({triggers.length})
        </div>
        {triggers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text3)', fontSize: '0.78rem' }}>
            Aucun trigger — Créez votre premier trigger ci-dessus
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {triggers.map(t => (
              <TriggerCard key={t.id} trigger={t} onDelete={deleteTrigger} onTest={testTrigger} onToggle={toggleTrigger} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
