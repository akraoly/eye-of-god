import { useState, useEffect } from 'react'
import { apiFetch } from '../utils/auth'

export default function DeepfakeVishing() {
  const [tab, setTab] = useState('voices')
  const [auth, setAuth] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [voices, setVoices] = useState([])
  const [scenarios, setScenarios] = useState([])
  const [campaigns, setCampaigns] = useState([])
  const [selectedVoice, setSelectedVoice] = useState(null)
  const [selectedScenario, setSelectedScenario] = useState('IT_URGENT')

  // Clone state
  const [audioPath, setAudioPath] = useState('')
  const [voiceName, setVoiceName] = useState('')

  // Script state
  const [targetName, setTargetName] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [context, setContext] = useState('')
  const [generatedScript, setGeneratedScript] = useState('')

  // Call state
  const [targetNumber, setTargetNumber] = useState('+33600000000')
  const [callerId, setCallerId] = useState('')

  // Speech state
  const [speechText, setSpeechText] = useState('')

  useEffect(() => {
    loadVoices(); loadScenarios(); loadCampaigns()
  }, [])

  const loadVoices = async () => { const r = await apiFetch('/deepfake/voices'); if (Array.isArray(r)) setVoices(r) }
  const loadScenarios = async () => { const r = await apiFetch('/deepfake/scenarios'); if (Array.isArray(r)) setScenarios(r) }
  const loadCampaigns = async () => { const r = await apiFetch('/deepfake/campaigns'); if (Array.isArray(r)) setCampaigns(r) }

  const act = async (fn) => { setLoading(true); setResult(null); try { await fn() } finally { setLoading(false) } }

  const cloneVoice = () => act(async () => {
    const r = await apiFetch('/deepfake/voice/clone/file', { method: 'POST', body: { audio_path: audioPath, voice_name: voiceName, authorization_confirmed: auth } })
    setResult(r); if (!r.error) { loadVoices(); setSelectedVoice(r) }
  })

  const generateScript = () => act(async () => {
    const r = await apiFetch('/deepfake/script/generate', { method: 'POST', body: { context, target_name: targetName, target_role: targetRole, scenario: selectedScenario, authorization_confirmed: auth } })
    setResult(r); if (r.script) setGeneratedScript(r.script)
  })

  const generateCall = () => act(async () => {
    if (!selectedVoice || !generatedScript) return
    const r = await apiFetch('/deepfake/call/generate', { method: 'POST', body: { voice_id: selectedVoice.voice_id, script: generatedScript, target_number: targetNumber, caller_id: callerId || null, authorization_confirmed: auth } })
    setResult(r); loadCampaigns()
  })

  const interactiveCall = () => act(async () => {
    if (!selectedVoice) return
    const r = await apiFetch('/deepfake/call/interactive', { method: 'POST', body: { voice_id: selectedVoice.voice_id, scenario: selectedScenario, target_number: targetNumber, caller_id: callerId || null, authorization_confirmed: auth } })
    setResult(r); loadCampaigns()
  })

  const generateSpeech = () => act(async () => {
    if (!selectedVoice || !speechText) return
    const r = await apiFetch('/deepfake/speech/generate', { method: 'POST', body: { voice_id: selectedVoice.voice_id, text: speechText, language: 'fr', emotion: 'normal', authorization_confirmed: auth } })
    setResult(r)
  })

  const deleteVoice = (vid) => act(async () => {
    const r = await apiFetch('/deepfake/voice/delete', { method: 'POST', body: { voice_id: vid, authorization_confirmed: auth } })
    setResult(r); loadVoices()
  })

  const scenarioColors = { IT_URGENT: '#ff6b35', HR_OFFER: '#4fc3f7', BANK_FRAUD: '#ff4444', SUPPORT: '#7fff7f', CEO_FRAUD: '#ffa500' }

  return (
    <div style={{ color: '#e0e0e0', fontFamily: 'monospace', padding: 20 }}>
      <h2 style={{ color: '#ff6b35', marginBottom: 8 }}>🎭 Deepfake Voice — Vishing Automatisé</h2>
      <p style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>Coqui TTS XTTS v2 · Clonage vocal · Scripts vishing</p>
      <div style={{ background: '#1a0a0a', border: '1px solid #5d2e2e', borderRadius: 4, padding: '6px 12px', marginBottom: 16, fontSize: 12, color: '#ff7070' }}>
        ⚠ Usage strictement réservé aux simulations de phishing autorisées et tests de sensibilisation (Red Team). Tout audio reste local.
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} />
        <span style={{ color: auth ? '#4fc3f7' : '#888', fontSize: 13 }}>Campagne Red Team autorisée confirmée</span>
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {['voices', 'clone', 'script', 'call', 'campaigns'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '6px 14px', background: tab === t ? '#ff6b35' : '#1e1e1e', color: '#fff', border: '1px solid #333', borderRadius: 4, cursor: 'pointer', fontSize: 12, textTransform: 'capitalize' }}>{t}</button>
        ))}
      </div>

      {tab === 'voices' && (
        <div>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Bibliothèque de Voix Clonées ({voices.length})</h4>
          {voices.map(v => (
            <div key={v.voice_id} onClick={() => setSelectedVoice(v)} style={{ background: selectedVoice?.voice_id === v.voice_id ? '#1e2a1e' : '#111', border: `1px solid ${selectedVoice?.voice_id === v.voice_id ? '#4caf50' : '#222'}`, borderRadius: 6, padding: 16, marginBottom: 10, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 700, color: '#fff', marginBottom: 4 }}>{v.name}</div>
                <div style={{ fontSize: 12, color: '#888' }}>{v.language?.toUpperCase()} · Qualité: <span style={{ color: '#7fff7f' }}>{Math.round((v.quality_score || 0) * 100)}%</span> · {v.samples_duration}s d'échantillons</div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#888' }}>Utilisé {v.used_count}x</span>
                <button onClick={e => { e.stopPropagation(); generateSpeech(); setSpeechText('Test vocal de synthèse.'); setSelectedVoice(v) }} disabled={!auth} style={{ padding: '4px 10px', background: '#1e2a3e', color: '#7fc4ff', border: '1px solid #2d4a6e', borderRadius: 3, cursor: 'pointer', fontSize: 11 }}>🔊 Test</button>
                <button onClick={e => { e.stopPropagation(); deleteVoice(v.voice_id) }} disabled={!auth} style={{ padding: '4px 10px', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 3, cursor: 'pointer', fontSize: 11 }}>🗑</button>
              </div>
            </div>
          ))}
          {selectedVoice && (
            <div style={{ background: '#0d1a0d', border: '1px solid #2d5a2d', borderRadius: 4, padding: 12, marginTop: 8 }}>
              <b style={{ color: '#7fff7f', fontSize: 12 }}>✓ Voix sélectionnée: {selectedVoice.name}</b>
            </div>
          )}
        </div>
      )}

      {tab === 'clone' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Cloner depuis Fichier Audio</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Chemin fichier audio (WAV/MP3)</label>
              <input value={audioPath} onChange={e => setAudioPath(e.target.value)} placeholder="./data/audio/target_voice.wav" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Nom de la voix</label>
              <input value={voiceName} onChange={e => setVoiceName(e.target.value)} placeholder="Ex: Jean-Pierre DG" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={cloneVoice} disabled={loading || !auth || !audioPath || !voiceName} style={{ marginTop: 8, padding: '8px 0', background: '#ff6b35', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>🎤 Cloner Voix (XTTS v2)</button>
            </div>
          </div>

          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Synthèse Vocale</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Voix: {selectedVoice?.name || 'Aucune sélectionnée'}</label>
              <textarea value={speechText} onChange={e => setSpeechText(e.target.value)} placeholder="Texte à synthétiser..." rows={5} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, resize: 'vertical', fontFamily: 'inherit' }} />
              <button onClick={generateSpeech} disabled={loading || !auth || !selectedVoice || !speechText} style={{ padding: '8px 0', background: '#1e3a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer' }}>🔊 Synthétiser</button>
            </div>
          </div>
        </div>
      )}

      {tab === 'script' && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
              <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Paramètres Script</h4>
              <label style={{ fontSize: 12, color: '#aaa' }}>Scénario</label>
              <select value={selectedScenario} onChange={e => setSelectedScenario(e.target.value)} style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginBottom: 8, marginTop: 4 }}>
                {scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <label style={{ fontSize: 12, color: '#aaa' }}>Nom cible</label>
              <input value={targetName} onChange={e => setTargetName(e.target.value)} placeholder="Jean Dupont" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginBottom: 8, marginTop: 4, boxSizing: 'border-box' }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Rôle cible</label>
              <input value={targetRole} onChange={e => setTargetRole(e.target.value)} placeholder="Comptable" style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginBottom: 8, marginTop: 4, boxSizing: 'border-box' }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Contexte opération</label>
              <input value={context} onChange={e => setContext(e.target.value)} placeholder="Entreprise XYZ, secteur finance..." style={{ width: '100%', background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4, marginBottom: 8, marginTop: 4, boxSizing: 'border-box' }} />
              <button onClick={generateScript} disabled={loading || !auth || !targetName} style={{ width: '100%', padding: '8px 0', background: '#ff6b35', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>📝 Générer Script</button>
            </div>
            {scenarios.map(s => (
              <div key={s.id} onClick={() => setSelectedScenario(s.id)} style={{ background: selectedScenario === s.id ? '#1e1e0d' : '#111', border: `1px solid ${selectedScenario === s.id ? '#ffa500' : '#222'}`, borderRadius: 4, padding: 10, cursor: 'pointer' }}>
                <div style={{ fontSize: 13, color: scenarioColors[s.id] || '#fff', fontWeight: 600 }}>{s.name}</div>
                <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{s.description}</div>
              </div>
            ))}
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Script Généré</h4>
            <textarea value={generatedScript} onChange={e => setGeneratedScript(e.target.value)} rows={22} style={{ width: '100%', background: '#0d0d0d', color: '#7fff7f', border: '1px solid #2d5a2d', padding: 12, borderRadius: 4, fontFamily: 'monospace', fontSize: 12, boxSizing: 'border-box', resize: 'vertical' }} />
          </div>
        </div>
      )}

      {tab === 'call' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Paramètres Appel</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#aaa' }}>Voix: {selectedVoice?.name || '— Sélectionner dans Voix'}</label>
              <label style={{ fontSize: 12, color: '#aaa' }}>Numéro cible</label>
              <input value={targetNumber} onChange={e => setTargetNumber(e.target.value)} style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <label style={{ fontSize: 12, color: '#aaa' }}>Caller ID spoofé (optionnel)</label>
              <input value={callerId} onChange={e => setCallerId(e.target.value)} placeholder="+33144556677 (IT support)" style={{ background: '#1a1a1a', color: '#fff', border: '1px solid #333', padding: '6px 8px', borderRadius: 4 }} />
              <button onClick={generateCall} disabled={loading || !auth || !selectedVoice || !generatedScript} style={{ marginTop: 8, padding: '10px 0', background: '#2d1e1e', color: '#ff7070', border: '1px solid #5d2e2e', borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>📞 Lancer Appel (Script)</button>
              <button onClick={interactiveCall} disabled={loading || !auth || !selectedVoice} style={{ padding: '10px 0', background: '#1e2a1e', color: '#7fff7f', border: '1px solid #2d5a2d', borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>🤖 Appel Interactif IA</button>
            </div>
          </div>
          <div style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 16 }}>
            <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Résultat Appel</h4>
            {result?.transcript ? (
              <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 300 }}>{result.transcript}</pre>
            ) : result?.recording_path ? (
              <div>
                <p style={{ color: '#888', fontSize: 13 }}>Enregistrement: {result.recording_path}</p>
                <p style={{ color: '#888', fontSize: 13 }}>Durée: {result.duration}s</p>
                <p style={{ color: result.objectives_met ? '#7fff7f' : '#ff7070', fontSize: 13 }}>Objectifs: {result.objectives_met ? '✅ Atteints' : '❌ Non atteints'}</p>
              </div>
            ) : <p style={{ color: '#555', fontSize: 13 }}>Aucun appel effectué.</p>}
          </div>
        </div>
      )}

      {tab === 'campaigns' && (
        <div>
          <h4 style={{ color: '#ff6b35', marginBottom: 12 }}>Historique Campagnes ({campaigns.length})</h4>
          {campaigns.map((c, i) => (
            <div key={i} style={{ background: '#111', border: '1px solid #222', borderRadius: 6, padding: 14, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, color: '#fff', fontSize: 13 }}>{c.id}</div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>Scénario: <span style={{ color: scenarioColors[c.scenario] || '#fff' }}>{c.scenario}</span> · Cible: {c.target_name || c.target_phone}</div>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#aaa' }}>{c.duration}s</span>
                <span style={{ fontSize: 12, color: c.objectives_met ? '#7fff7f' : '#ff7070', background: c.objectives_met ? '#0d1a0d' : '#1a0d0d', padding: '3px 8px', borderRadius: 3 }}>{c.objectives_met ? '✅ Succès' : '❌ Échec'}</span>
                <span style={{ fontSize: 11, color: '#666' }}>{c.created_at}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {(loading || result) && (
        <div style={{ marginTop: 16, background: '#0d0d0d', border: '1px solid #333', borderRadius: 6, padding: 16 }}>
          {loading ? <p style={{ color: '#ffa500' }}>⟳ Opération en cours...</p> : !result?.transcript && <pre style={{ color: '#7fff7f', fontSize: 12, whiteSpace: 'pre-wrap', overflow: 'auto', maxHeight: 300 }}>{JSON.stringify(result, null, 2)}</pre>}
        </div>
      )}
    </div>
  )
}
