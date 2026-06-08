import { useState } from 'react'

const BASE = 'http://localhost:8001'

function useApi() {
  const token = localStorage.getItem('token') || ''
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
  const call = (path, body) =>
    fetch(`${BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) }).then(r => r.json())
  const get = (path) =>
    fetch(`${BASE}${path}`, { headers }).then(r => r.json())
  return { call, get }
}

function ResultBox({ data }) {
  if (!data) return null
  return (
    <pre style={{ background: '#0a0a0a', border: '1px solid #1a3a1a', borderRadius: 6,
      padding: 12, fontSize: 11, color: '#00ff41', maxHeight: 400, overflow: 'auto',
      whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 10 }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function Warn() {
  return (
    <div style={{ background: '#1a0a00', border: '1px solid #ff6600', borderRadius: 6,
      padding: '8px 14px', marginBottom: 12, fontSize: 12, color: '#ff9944' }}>
      ⚠️ Usage exclusivement légal — red team IO autorisé / recherche défensive uniquement
    </div>
  )
}

// ── IO Ops Panel ──────────────────────────────────────────────────────────────
function IOOpsPanel() {
  const { call, get } = useApi()
  const [auth, setAuth] = useState(false)
  const [res, setRes] = useState(null)
  const [name, setName] = useState('Op Influence Test')
  const [obj, setObj]   = useState('Amplification narratif défensif')
  const [audience, setAudience] = useState('décideurs politiques')
  const [platforms, setPlatforms] = useState('twitter_x,telegram')
  const [tactics, setTactics]   = useState('narrative_seeding,amplification_network')
  const [accounts, setAccounts] = useState(20)
  const [profType, setProfType] = useState('authentic_citizen')
  const [count, setCount]       = useState(5)

  return (
    <div>
      <Warn />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => get('/influence/io-ops/platforms').then(setRes)}>Plateformes</button>
        <button style={btnStyle} onClick={() => get('/influence/io-ops/sockpuppet-profiles').then(setRes)}>Profils Sockpuppet</button>
        <button style={btnStyle} onClick={() => get('/influence/io-ops/tactics').then(setRes)}>Tactiques IO</button>
        <button style={btnStyle} onClick={() => get('/influence/io-ops/detection-indicators').then(setRes)}>Indicateurs Détection</button>
        <button style={btnStyle} onClick={() => get('/influence/io-ops/campaigns').then(setRes)}>Campagnes</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Concevoir une Campagne IO</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <input style={inputStyle} placeholder="Nom opération" value={name} onChange={e => setName(e.target.value)} />
          <input style={inputStyle} placeholder="Objectif" value={obj} onChange={e => setObj(e.target.value)} />
          <input style={inputStyle} placeholder="Audience cible" value={audience} onChange={e => setAudience(e.target.value)} />
          <input style={inputStyle} placeholder="Plateformes (csv)" value={platforms} onChange={e => setPlatforms(e.target.value)} />
          <input style={inputStyle} placeholder="Tactiques (csv)" value={tactics} onChange={e => setTactics(e.target.value)} />
          <input style={inputStyle} type="number" placeholder="Nb comptes" value={accounts} onChange={e => setAccounts(+e.target.value)} />
        </div>
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/io-ops/design-campaign', {
          authorization_confirmed: auth, name, objective: obj, target_audience: audience,
          platforms: platforms.split(',').map(s => s.trim()), tactics: tactics.split(',').map(s => s.trim()),
          budget_accounts: accounts, duration_days: 30,
        }).then(setRes)}>Concevoir Campagne</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Générer Réseau Sockpuppets</h4>
        <div style={{ display: 'flex', gap: 8 }}>
          <select style={inputStyle} value={profType} onChange={e => setProfType(e.target.value)}>
            <option value="authentic_citizen">Citoyen authentique</option>
            <option value="journalist_blogger">Journaliste/Blogueur</option>
            <option value="expert_analyst">Expert/Analyste</option>
            <option value="activist">Activiste</option>
            <option value="bot_amplifier">Bot amplificateur</option>
          </select>
          <input style={{ ...inputStyle, width: 80 }} type="number" value={count} onChange={e => setCount(+e.target.value)} placeholder="Nb" />
        </div>
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/io-ops/sockpuppet-network', {
          authorization_confirmed: auth, profile_type: profType, count, language: 'fr', country: 'France',
        }).then(setRes)}>Générer Réseau</button>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ── Disinfo Panel ─────────────────────────────────────────────────────────────
function DisinfoPanel() {
  const { call, get } = useApi()
  const [auth, setAuth]     = useState(false)
  const [res, setRes]       = useState(null)
  const [fileType, setFileType] = useState('image_exif')
  const [targetDate, setDate]   = useState('')
  const [targetLoc, setLoc]     = useState('Paris')
  const [targetAuthor, setAuthor] = useState('')
  const [metaJson, setMetaJson]   = useState('{"Author":"Admin","Creator":"Word","CreationDate":"2025-01-01","ModDate":"2024-12-01"}')
  const [contentType, setCtype]   = useState('image')
  const [indicators, setIndicators] = useState('image manipulée,deepfake')

  return (
    <div>
      <Warn />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => get('/influence/disinfo/archetypes').then(setRes)}>Archétypes Disinfo</button>
        <button style={btnStyle} onClick={() => get('/influence/disinfo/detection-methods').then(setRes)}>Méthodes Détection</button>
        <button style={btnStyle} onClick={() => get(`/influence/disinfo/metadata-fields?file_type=${fileType}`).then(setRes)}>Champs Métadonnées</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Simulation Forgerie Métadonnées</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <select style={inputStyle} value={fileType} onChange={e => setFileType(e.target.value)}>
            <option value="image_exif">Image EXIF</option>
            <option value="pdf_metadata">PDF</option>
            <option value="office_metadata">Office (Word/Excel)</option>
            <option value="video_metadata">Vidéo</option>
          </select>
          <input style={inputStyle} placeholder="Date cible (YYYY:MM:DD HH:MM:SS)" value={targetDate} onChange={e => setDate(e.target.value)} />
          <input style={inputStyle} placeholder="Localisation (Paris, London...)" value={targetLoc} onChange={e => setLoc(e.target.value)} />
          <input style={inputStyle} placeholder="Auteur cible" value={targetAuthor} onChange={e => setAuthor(e.target.value)} />
        </div>
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/disinfo/forge-metadata', {
          authorization_confirmed: auth, file_type: fileType,
          target_date: targetDate || null, target_location: targetLoc || null, target_author: targetAuthor || null,
        }).then(setRes)}>Simuler Forgerie</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Analyser Authenticité Document</h4>
        <textarea style={{ ...inputStyle, width: '100%', height: 80, fontFamily: 'monospace' }}
          value={metaJson} onChange={e => setMetaJson(e.target.value)} />
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/disinfo/analyze-authenticity', {
          authorization_confirmed: auth, metadata_json: metaJson,
        }).then(setRes)}>Analyser</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Détecter Contenu Synthétique</h4>
        <input style={inputStyle} placeholder="Type de contenu" value={contentType} onChange={e => setCtype(e.target.value)} />
        <input style={inputStyle} placeholder="Indicateurs (csv)" value={indicators} onChange={e => setIndicators(e.target.value)} />
        <button style={{ ...btnStyle, marginTop: 8 }} onClick={() => call('/influence/disinfo/detect-synthetic', {
          content_type: contentType, indicators: indicators.split(',').map(s => s.trim()),
        }).then(setRes)}>Détecter</button>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ── PSYOP Panel ───────────────────────────────────────────────────────────────
function PsyopPanel() {
  const { call, get } = useApi()
  const [auth, setAuth]     = useState(false)
  const [res, setRes]       = useState(null)
  const [segment, setSegment] = useState('casual_news_follower')
  const [context, setContext] = useState('Campagne électorale 2027')
  const [framework, setFw]    = useState('SCAME')
  const [objective, setObj]   = useState('Réduire la crédibilité d\'un adversaire')
  const [narrative, setNarr]  = useState('L\'adversaire a menti sur son bilan')
  const [org, setOrg]         = useState('Organisation Test')

  return (
    <div>
      <Warn />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => get('/influence/psyop/cognitive-biases').then(setRes)}>Biais Cognitifs</button>
        <button style={btnStyle} onClick={() => get('/influence/psyop/frameworks').then(setRes)}>Frameworks PSYOP</button>
        <button style={btnStyle} onClick={() => get('/influence/psyop/target-segments').then(setRes)}>Segments Cibles</button>
        <button style={btnStyle} onClick={() => get('/influence/psyop/countermeasures').then(setRes)}>Contre-mesures IO</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Profiler Segment Cible</h4>
        <select style={inputStyle} value={segment} onChange={e => setSegment(e.target.value)}>
          <option value="casual_news_follower">Suiveur casual</option>
          <option value="high_information_consumer">Consommateur info élevé</option>
          <option value="conspiracy_prone">Enclin théories complot</option>
          <option value="professional_expert">Professionnel/Expert</option>
          <option value="politically_polarized">Fortement polarisé</option>
        </select>
        <input style={inputStyle} placeholder="Contexte" value={context} onChange={e => setContext(e.target.value)} />
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/psyop/profile-segment', {
          authorization_confirmed: auth, segment, context,
        }).then(setRes)}>Profiler</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Concevoir Message PSYOP</h4>
        <select style={inputStyle} value={framework} onChange={e => setFw(e.target.value)}>
          <option value="SCAME">SCAME (NATO)</option>
          <option value="JIPOE">JIPOE (US Military)</option>
          <option value="SMICE">SMICE (Intel)</option>
          <option value="IOTA">IOTA (Modern IO)</option>
          <option value="4D_doctrine">4D Doctrine</option>
        </select>
        <input style={inputStyle} placeholder="Objectif" value={objective} onChange={e => setObj(e.target.value)} />
        <input style={inputStyle} placeholder="Narratif central" value={narrative} onChange={e => setNarr(e.target.value)} />
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/psyop/design-message', {
          authorization_confirmed: auth, framework, target_segment: segment,
          objective, core_narrative: narrative,
        }).then(setRes)}>Concevoir Message</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Évaluer Résilience IO</h4>
        <input style={inputStyle} placeholder="Organisation" value={org} onChange={e => setOrg(e.target.value)} />
        <button style={{ ...btnStyle, marginTop: 8 }} onClick={() => call('/influence/psyop/io-resilience', { organization: org }).then(setRes)}>Évaluer</button>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ── Attribution Panel ─────────────────────────────────────────────────────────
function AttributionPanel() {
  const { call, get } = useApi()
  const [auth, setAuth]     = useState(false)
  const [res, setRes]       = useState(null)
  const [platforms, setPlatforms] = useState('Facebook,Twitter')
  const [narratives, setNarratives] = useState('anti-OTAN,désinformation électorale')
  const [docName, setDocName]       = useState('Rapport_Confidentiel.pdf')
  const [suspects, setSuspects]     = useState('Alice,Bob,Charlie')
  const [varType, setVarType]       = useState('timestamp')
  const [orgName, setOrgName]       = useState('ACME Corp')

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => get('/influence/attribution/actors').then(setRes)}>Acteurs IO Connus</button>
        <button style={btnStyle} onClick={() => get('/influence/attribution/indicators').then(setRes)}>Indicateurs Attribution</button>
        <button style={btnStyle} onClick={() => get('/influence/attribution/counterintel-frameworks').then(setRes)}>Frameworks Contre-Intel</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Analyser Campagne IO (Attribution)</h4>
        <input style={inputStyle} placeholder="Plateformes (csv)" value={platforms} onChange={e => setPlatforms(e.target.value)} />
        <input style={inputStyle} placeholder="Narratifs observés (csv)" value={narratives} onChange={e => setNarratives(e.target.value)} />
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/attribution/analyze-campaign', {
          authorization_confirmed: auth,
          campaign_indicators: {},
          platforms: platforms.split(',').map(s => s.trim()),
          narratives: narratives.split(',').map(s => s.trim()),
        }).then(setRes)}>Analyser</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Canary Trap (Détection Taupe)</h4>
        <input style={inputStyle} placeholder="Nom document" value={docName} onChange={e => setDocName(e.target.value)} />
        <input style={inputStyle} placeholder="Suspects (csv)" value={suspects} onChange={e => setSuspects(e.target.value)} />
        <select style={inputStyle} value={varType} onChange={e => setVarType(e.target.value)}>
          <option value="timestamp">Timestamp</option>
          <option value="word_swap">Swap de mot</option>
          <option value="unique_id">ID unique</option>
        </select>
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/attribution/canary-trap', {
          authorization_confirmed: auth, document_name: docName,
          suspects: suspects.split(',').map(s => s.trim()), variation_type: varType,
        }).then(setRes)}>Créer Piège</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Bilan Contre-Intelligence</h4>
        <input style={inputStyle} placeholder="Organisation" value={orgName} onChange={e => setOrgName(e.target.value)} />
        <button style={{ ...btnStyle, marginTop: 8 }} onClick={() => call('/influence/attribution/counterintel-check', { org_name: orgName }).then(setRes)}>Évaluer</button>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ── Narrative Monitor Panel ───────────────────────────────────────────────────
function MonitorPanel() {
  const { call, get } = useApi()
  const [auth, setAuth]     = useState(false)
  const [res, setRes]       = useState(null)
  const [keywords, setKeywords] = useState('fraude,election,manipulation')
  const [falseClaim, setClaim]  = useState('Le gouvernement cache des informations sur X')
  const [strategy, setStrategy] = useState('prebunking')

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => get('/influence/monitor/categories').then(setRes)}>Catégories Narratifs</button>
        <button style={btnStyle} onClick={() => get('/influence/monitor/fact-check-orgs').then(setRes)}>Orgs Fact-Check</button>
        <button style={btnStyle} onClick={() => get('/influence/monitor/counter-strategies').then(setRes)}>Stratégies Contre-Narratif</button>
        <button style={btnStyle} onClick={() => get('/influence/monitor/sources').then(setRes)}>Sources Monitoring</button>
        <button style={btnStyle} onClick={() => get('/influence/monitor/monitors').then(setRes)}>Moniteurs Actifs</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Démarrer Surveillance Narrative</h4>
        <input style={inputStyle} placeholder="Mots-clés (csv)" value={keywords} onChange={e => setKeywords(e.target.value)} />
        <button style={{ ...btnStyle, marginTop: 8 }} onClick={() => call('/influence/monitor/start', {
          keywords: keywords.split(',').map(s => s.trim()),
          platforms: ['twitter_x','telegram','facebook'],
        }).then(setRes)}>Démarrer</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Détecter Comportement Coordonné (CIB)</h4>
        <input style={inputStyle} placeholder="Mots-clés (csv)" value={keywords} onChange={e => setKeywords(e.target.value)} />
        <button style={{ ...btnStyle, marginTop: 8 }} onClick={() => call('/influence/monitor/detect-cib', {
          keywords: keywords.split(',').map(s => s.trim()), time_window_hours: 24,
        }).then(setRes)}>Détecter CIB</button>
      </div>

      <div style={sectionStyle}>
        <h4 style={h4}>Générer Contre-Narratif</h4>
        <textarea style={{ ...inputStyle, width: '100%', height: 60 }}
          placeholder="Affirmation à réfuter" value={falseClaim} onChange={e => setClaim(e.target.value)} />
        <select style={inputStyle} value={strategy} onChange={e => setStrategy(e.target.value)}>
          <option value="prebunking">Prebunking (inoculation)</option>
          <option value="debunking">Debunking (réfutation)</option>
          <option value="narrative_bridge">Pont narratif</option>
          <option value="trusted_voices">Voix de confiance</option>
          <option value="systemic_reporting">Signalement systématique</option>
          <option value="media_literacy_campaign">Éducation aux médias</option>
        </select>
        <label style={labelStyle}><input type="checkbox" checked={auth} onChange={e => setAuth(e.target.checked)} /> authorization_confirmed</label>
        <button style={{ ...btnStyle, background: '#1a3a1a', marginTop: 8 }} onClick={() => call('/influence/monitor/counter-narrative', {
          authorization_confirmed: auth, false_claim: falseClaim, strategy,
        }).then(setRes)}>Générer</button>
      </div>

      <ResultBox data={res} />
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
const TABS = [
  { id: 'io-ops',      label: '🕸️ IO Ops',        component: IOOpsPanel },
  { id: 'disinfo',     label: '🖼️ Disinfo',        component: DisinfoPanel },
  { id: 'psyop',       label: '🧠 PSYOP',           component: PsyopPanel },
  { id: 'attribution', label: '🔍 Attribution',     component: AttributionPanel },
  { id: 'monitor',     label: '📡 Monitoring',      component: MonitorPanel },
]

export default function InfluenceBloc9() {
  const [tab, setTab] = useState('io-ops')
  const ActiveTab = TABS.find(t => t.id === tab)?.component || IOOpsPanel

  return (
    <div style={{ padding: 20, fontFamily: 'monospace', color: '#ccc', maxWidth: 1000 }}>
      <h2 style={{ color: '#00ff41', marginBottom: 4, fontSize: 18 }}>
        🌐 Bloc 9 — Influence Stratégique & Guerre de l'Information
      </h2>
      <p style={{ color: '#666', fontSize: 12, marginBottom: 16 }}>
        IO Ops · Désinformation · PSYOP · Attribution · Monitoring — Simulation défensive
      </p>

      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ ...tabStyle, ...(tab === t.id ? activeTab : {}) }}>
            {t.label}
          </button>
        ))}
      </div>

      <ActiveTab />
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const btnStyle = {
  background: '#111', border: '1px solid #333', color: '#00ff41',
  padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
}
const tabStyle = {
  background: '#111', border: '1px solid #333', color: '#888',
  padding: '7px 14px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
}
const activeTab = { borderColor: '#00ff41', color: '#00ff41', background: '#0a1a0a' }
const sectionStyle = {
  background: '#0d0d0d', border: '1px solid #1a2a1a', borderRadius: 6,
  padding: 12, marginBottom: 12,
}
const h4 = { color: '#00cc33', margin: '0 0 8px 0', fontSize: 13 }
const inputStyle = {
  background: '#0a0a0a', border: '1px solid #333', color: '#ccc',
  padding: '5px 8px', borderRadius: 4, fontSize: 12, width: '100%',
  marginBottom: 6, boxSizing: 'border-box',
}
const labelStyle = { fontSize: 12, color: '#888', display: 'block', marginTop: 4 }
