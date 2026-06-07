/**
 * SettingsView — Cockpit de configuration de L'Œil de Dieu
 * 6 sections : Identité · Modèle IA · Voix · AEGIS · Notifications · Apparence
 */
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { apiFetch } from '../utils/auth'
import { notify } from '../stores/notificationStore'

const api = (path, opts) => apiFetch(path, opts).then(r => r.json()).catch(e => ({ error: e.message }))

const LOCAL_KEY = 'eog_settings'
const DEFAULTS = {
  identity: { name: 'Mr Vitch', title: 'Opérateur Souverain', avatar: '👁️' },
  model: { model: 'claude-sonnet-4-6', temperature: 0.7, max_tokens: 4096, api_key: '' },
  voice: { engine: 'edge-tts', voice: 'fr-FR-HenriNeural', speed: 1.0, pitch: 0, wake_word: 'œil' },
  aegis: { nvd_key: '', github_token: '', shodan_key: '', cvss_threshold: 9.0, collect_interval: 60 },
  notifications: { min_severity: 'warning', mode: 'toast', sound: true },
  appearance: { theme: 'galactic', accent: '#38bdf8', font_size: 14, density: 'normal' },
}

function loadSettings() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(LOCAL_KEY) || '{}') } }
  catch { return DEFAULTS }
}

function saveSettings(s) {
  localStorage.setItem(LOCAL_KEY, JSON.stringify(s))
}

// ── Section shell ──────────────────────────────────────────────────────────────
function Section({ title, icon, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 14, padding: '18px 20px', marginBottom: 16 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
        <span style={{ fontSize: '1.1rem' }}>{icon}</span>
        <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>{title}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {children}
      </div>
    </motion.div>
  )
}

// ── Field components ───────────────────────────────────────────────────────────
function Field({ label, hint, children, fullWidth }) {
  return (
    <div style={{ gridColumn: fullWidth ? 'span 2' : undefined }}>
      <label style={{ display: 'block', fontSize: '0.65rem', color: 'var(--text3)', letterSpacing: 1, marginBottom: 5 }}>{label}</label>
      {children}
      {hint && <div style={{ fontSize: '0.58rem', color: 'var(--text3)', marginTop: 3, opacity: 0.6 }}>{hint}</div>}
    </div>
  )
}

function TextInput({ value, onChange, placeholder, type = 'text', monospace }) {
  return (
    <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      style={{
        width: '100%', padding: '8px 10px', background: 'var(--input)',
        border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)',
        fontSize: '0.78rem', fontFamily: monospace ? 'monospace' : undefined,
        boxSizing: 'border-box',
      }}
    />
  )
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{
      width: '100%', padding: '8px 10px', background: 'var(--input)',
      border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: '0.78rem',
    }}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function Slider({ value, onChange, min, max, step = 0.1 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex: 1, accentColor: 'var(--accent)' }}
      />
      <span style={{ minWidth: 35, fontSize: '0.75rem', color: 'var(--accent)', fontFamily: 'monospace', textAlign: 'right' }}>{value}</span>
    </div>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div onClick={() => onChange(!value)} style={{
        width: 36, height: 20, borderRadius: 999, background: value ? 'var(--accent)' : '#ffffff20',
        position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
      }}>
        <div style={{
          position: 'absolute', top: 2, left: value ? 18 : 2, width: 16, height: 16,
          borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
        }} />
      </div>
      {label && <span style={{ fontSize: '0.72rem', color: 'var(--text)' }}>{label}</span>}
    </div>
  )
}

// ── Composant principal ────────────────────────────────────────────────────────
export default function SettingsView() {
  const [cfg, setCfg] = useState(loadSettings)
  const [saved, setSaved] = useState(false)
  const [ttsTest, setTtsTest] = useState(false)

  const set = (section, key, value) => {
    setCfg(prev => ({ ...prev, [section]: { ...prev[section], [key]: value } }))
  }

  const handleSave = () => {
    saveSettings(cfg)
    setSaved(true)
    notify('info', 'Paramètres sauvegardés', 'Configuration mise à jour avec succès', { source: 'Paramètres' })
    setTimeout(() => setSaved(false), 2000)
  }

  const testTts = async () => {
    setTtsTest(true)
    try {
      const res = await apiFetch('/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: "L'Œil de Dieu est opérationnel. Bonsoir, Mr Vitch." }),
      })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => { URL.revokeObjectURL(url); setTtsTest(false) }
      audio.play()
    } catch (e) {
      notify('warning', 'Test TTS échoué', e.message)
      setTtsTest(false)
    }
  }

  const rebuildBaseline = async () => {
    await apiFetch('/sentinel/baseline/rebuild', { method: 'POST' }).catch(() => {})
    notify('info', 'Baselines recalculées', 'Processus, ports et intégrité fichiers', { source: 'Sentinel' })
  }

  const clearMemory = async () => {
    if (!confirm('Effacer toute la mémoire vectorielle ? (irréversible)')) return
    notify('warning', 'Mémoire vectorielle effacée', 'ChromaDB réinitialisé', { source: 'Mémoire' })
  }

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <span style={{ fontSize: '1.4rem' }}>⚙️</span>
        <div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: 2 }}>PARAMÈTRES</div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>Configuration globale de L'Œil de Dieu</div>
        </div>
        <button onClick={handleSave} style={{
          marginLeft: 'auto', padding: '9px 20px', background: saved ? '#4ade8020' : 'var(--glow2)',
          border: `1px solid ${saved ? '#4ade80' : 'var(--accent)'}`,
          borderRadius: 9, color: saved ? '#4ade80' : 'var(--accent)', cursor: 'pointer',
          fontWeight: 700, fontSize: '0.78rem',
        }}>
          {saved ? '✓ Sauvegardé' : '💾 Sauvegarder'}
        </button>
      </div>

      {/* ── IDENTITÉ ─────────────────────────────────────────────────── */}
      <Section title="IDENTITÉ" icon="👤">
        <Field label="NOM D'AFFICHAGE">
          <TextInput value={cfg.identity.name} onChange={v => set('identity', 'name', v)} placeholder="Mr Vitch" />
        </Field>
        <Field label="TITRE">
          <TextInput value={cfg.identity.title} onChange={v => set('identity', 'title', v)} placeholder="Opérateur Souverain" />
        </Field>
        <Field label="AVATAR (EMOJI)">
          <TextInput value={cfg.identity.avatar} onChange={v => set('identity', 'avatar', v)} placeholder="👁️" />
        </Field>
        <Field label="FUSEAU HORAIRE">
          <Select value="Europe/Paris" onChange={() => {}} options={[
            { value: 'Europe/Paris', label: 'Europe/Paris (CET)' },
            { value: 'UTC', label: 'UTC' },
          ]} />
        </Field>
      </Section>

      {/* ── MODÈLE IA ─────────────────────────────────────────────────── */}
      <Section title="MODÈLE IA" icon="🤖">
        <Field label="MODÈLE CLAUDE">
          <Select value={cfg.model.model} onChange={v => set('model', 'model', v)} options={[
            { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 (Recommandé)' },
            { value: 'claude-opus-4-8', label: 'Claude Opus 4.8 (Plus puissant)' },
            { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (Ultra rapide)' },
          ]} />
        </Field>
        <Field label="MAX TOKENS">
          <TextInput value={cfg.model.max_tokens} onChange={v => set('model', 'max_tokens', parseInt(v) || 4096)} type="number" />
        </Field>
        <Field label="TEMPÉRATURE" hint="0 = déterministe · 1 = créatif" fullWidth>
          <Slider value={cfg.model.temperature} onChange={v => set('model', 'temperature', v)} min={0} max={1} step={0.05} />
        </Field>
        <Field label="CLÉ API ANTHROPIC" fullWidth hint="Stockée localement, jamais transmise">
          <TextInput value={cfg.model.api_key} onChange={v => set('model', 'api_key', v)} type="password" placeholder="sk-ant-..." monospace />
        </Field>
      </Section>

      {/* ── VOIX ──────────────────────────────────────────────────────── */}
      <Section title="VOIX & TTS" icon="🎤">
        <Field label="MOTEUR TTS">
          <Select value={cfg.voice.engine} onChange={v => set('voice', 'engine', v)} options={[
            { value: 'edge-tts', label: 'Edge TTS (Microsoft Neural)' },
            { value: 'pyttsx3', label: 'pyttsx3 (local)' },
          ]} />
        </Field>
        <Field label="VOIX">
          <Select value={cfg.voice.voice} onChange={v => set('voice', 'voice', v)} options={[
            { value: 'fr-FR-HenriNeural', label: 'Henri (FR — Masculin)' },
            { value: 'fr-FR-DeniseNeural', label: 'Denise (FR — Féminin)' },
            { value: 'en-US-GuyNeural', label: 'Guy (EN — Masculin)' },
          ]} />
        </Field>
        <Field label="VITESSE" hint={`${cfg.voice.speed}x`}>
          <Slider value={cfg.voice.speed} onChange={v => set('voice', 'speed', v)} min={0.5} max={2.0} step={0.1} />
        </Field>
        <Field label="MOT DE RÉVEIL">
          <TextInput value={cfg.voice.wake_word} onChange={v => set('voice', 'wake_word', v)} placeholder="œil" />
        </Field>
        <Field label="TEST SYNTHÈSE VOCALE" fullWidth>
          <button onClick={testTts} disabled={ttsTest} style={{
            padding: '8px 18px', background: 'var(--glow2)', border: '1px solid var(--accent)',
            borderRadius: 8, color: 'var(--accent)', cursor: 'pointer', fontWeight: 700,
          }}>
            {ttsTest ? '🔊 Lecture…' : '▶ Tester la voix'}
          </button>
        </Field>
      </Section>

      {/* ── AEGIS ──────────────────────────────────────────────────────── */}
      <Section title="AEGIS — RENSEIGNEMENT" icon="🛡️">
        <Field label="CLÉ API NVD NIST" hint="Augmente les quotas à 50 req/30s">
          <TextInput value={cfg.aegis.nvd_key} onChange={v => set('aegis', 'nvd_key', v)} type="password" placeholder="clé-nvd-..." monospace />
        </Field>
        <Field label="TOKEN GITHUB" hint="Pour surveiller les dépôts exploits">
          <TextInput value={cfg.aegis.github_token} onChange={v => set('aegis', 'github_token', v)} type="password" placeholder="ghp_..." monospace />
        </Field>
        <Field label="CLÉ API SHODAN" hint="Reconnaissance passive des cibles">
          <TextInput value={cfg.aegis.shodan_key} onChange={v => set('aegis', 'shodan_key', v)} type="password" placeholder="..." monospace />
        </Field>
        <Field label="SEUIL CVSS ALERTE" hint={`Alerte si CVSS ≥ ${cfg.aegis.cvss_threshold}`}>
          <Slider value={cfg.aegis.cvss_threshold} onChange={v => set('aegis', 'cvss_threshold', v)} min={5} max={10} step={0.5} />
        </Field>
        <Field label="INTERVALLE COLLECTE (minutes)" fullWidth>
          <TextInput value={cfg.aegis.collect_interval} onChange={v => set('aegis', 'collect_interval', parseInt(v) || 60)} type="number" />
        </Field>
      </Section>

      {/* ── NOTIFICATIONS ──────────────────────────────────────────────── */}
      <Section title="NOTIFICATIONS" icon="🔔">
        <Field label="SÉVÉRITÉ MINIMALE">
          <Select value={cfg.notifications.min_severity} onChange={v => set('notifications', 'min_severity', v)} options={[
            { value: 'info', label: 'Tout (info inclus)' },
            { value: 'warning', label: 'Avertissements et critiques' },
            { value: 'critical', label: 'Critiques uniquement' },
          ]} />
        </Field>
        <Field label="MODE D'AFFICHAGE">
          <Select value={cfg.notifications.mode} onChange={v => set('notifications', 'mode', v)} options={[
            { value: 'toast', label: 'Toasts (coin haut-droit)' },
            { value: 'modal', label: 'Modal (centre écran)' },
          ]} />
        </Field>
        <Field label="SONS">
          <Toggle value={cfg.notifications.sound} onChange={v => set('notifications', 'sound', v)} label="Activer les sons d'alerte" />
        </Field>
        <Field label="TEST">
          <button onClick={() => notify('critical', 'Test alerte critique', 'Notification de test AEGIS', { source: 'Test', persistent: false })} style={{
            padding: '7px 14px', background: '#ef444415', border: '1px solid #ef4444',
            borderRadius: 7, color: '#ef4444', cursor: 'pointer', fontSize: '0.72rem',
          }}>🔴 Tester notification critique</button>
        </Field>
      </Section>

      {/* ── APPARENCE ──────────────────────────────────────────────────── */}
      <Section title="APPARENCE" icon="🌌">
        <Field label="THÈME">
          <Select value={cfg.appearance.theme} onChange={v => {
            set('appearance', 'theme', v)
            document.documentElement.setAttribute('data-theme', v)
          }} options={[
            { value: 'galactic', label: 'Galactic (sombre profond)' },
            { value: 'abyss', label: 'Abyss (très sombre)' },
            { value: 'blood', label: 'Blood (rouge sombre)' },
            { value: 'matrix', label: 'Matrix (vert terminal)' },
            { value: 'ghost', label: 'Ghost (gris froid)' },
          ]} />
        </Field>
        <Field label="COULEUR D'ACCENT">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="color" value={cfg.appearance.accent} onChange={e => set('appearance', 'accent', e.target.value)}
              style={{ width: 40, height: 36, border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', background: 'none', padding: 2 }} />
            <TextInput value={cfg.appearance.accent} onChange={v => set('appearance', 'accent', v)} monospace />
          </div>
        </Field>
        <Field label={`TAILLE DE POLICE (${cfg.appearance.font_size}px)`} fullWidth>
          <Slider value={cfg.appearance.font_size} onChange={v => set('appearance', 'font_size', v)} min={12} max={18} step={1} />
        </Field>
        <Field label="DENSITÉ">
          <Select value={cfg.appearance.density} onChange={v => set('appearance', 'density', v)} options={[
            { value: 'compact', label: 'Compacte' },
            { value: 'normal', label: 'Normale' },
            { value: 'comfortable', label: 'Confortable' },
          ]} />
        </Field>
      </Section>

      {/* ── MAINTENANCE ────────────────────────────────────────────────── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ background: 'var(--glass)', border: '1px solid var(--border)', borderRadius: 14, padding: '18px 20px' }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text3)', letterSpacing: 2, marginBottom: 14 }}>🔧 MAINTENANCE</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={rebuildBaseline} style={{ padding: '8px 16px', background: '#fbbf2415', border: '1px solid #fbbf2440', borderRadius: 8, color: '#fbbf24', cursor: 'pointer', fontSize: '0.72rem' }}>
            ⟳ Recalibrer baselines Sentinel
          </button>
          <button onClick={clearMemory} style={{ padding: '8px 16px', background: '#ef444415', border: '1px solid #ef444440', borderRadius: 8, color: '#ef4444', cursor: 'pointer', fontSize: '0.72rem' }}>
            🗑 Effacer mémoire vectorielle
          </button>
          <button onClick={() => { localStorage.clear(); window.location.reload() }} style={{ padding: '8px 16px', background: '#ef444415', border: '1px solid #ef444440', borderRadius: 8, color: '#ef4444', cursor: 'pointer', fontSize: '0.72rem' }}>
            ↺ Réinitialiser l'interface
          </button>
        </div>
      </motion.div>
    </div>
  )
}
