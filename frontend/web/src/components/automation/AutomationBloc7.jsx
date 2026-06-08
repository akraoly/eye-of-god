import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'planner',       label: '🗺️ Attack Planner',   color: '#ff6644' },
  { id: 'campaign',      label: '🎯 Campaign Manager',  color: '#ff9900' },
  { id: 'antiforensics', label: '🧹 Anti-Forensics',    color: '#44ccff' },
  { id: 'payload',       label: '💣 Payload Builder',   color: '#cc44ff' },
  { id: 'opsec',         label: '🥷 OPSEC',             color: '#44ff88' },
]

function ResultBox({ data }) {
  if (!data) return null
  const isErr = data?.error
  return (
    <pre style={{
      background: '#0a0f1a', color: isErr ? '#ff6666' : '#7affb2',
      border: `1px solid ${isErr ? '#3a1a1a' : '#1a3a1a'}`,
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 360, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

const Sp = () => <span style={{ color: '#44ccff', marginLeft: 6 }}>⏳</span>

function useApi() {
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)
  const call = async (path, body) => {
    setLoading(true)
    try { setRes(await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }
  const get = async (path) => {
    setLoading(true)
    try { setRes(await apiFetch(path)) }
    catch(e) { setRes({ error: e.message }) }
    finally { setLoading(false) }
  }
  return { res, loading, call, get }
}

const css = {
  panel: { background: '#0a1520', border: '1px solid #1a2a3a', borderRadius: 12, padding: 20 },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 },
  grid3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 },
  lbl: { display: 'block', fontSize: 11, color: '#667', marginBottom: 3 },
  inp: { width: '100%', background: '#060b14', border: '1px solid #1a2a3a', color: '#ccc', padding: '6px 9px', borderRadius: 6, fontSize: 12, boxSizing: 'border-box' },
  btns: { display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0' },
  btn: { background: '#1a2a3a', border: '1px solid #2a3a4a', color: '#aaccff', padding: '6px 13px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  auth: { display: 'flex', alignItems: 'center', gap: 6, color: '#ff4444', fontSize: 12, margin: '10px 0', cursor: 'pointer' },
  warn: { background: '#1a0a00', border: '1px solid #3a1a00', borderRadius: 6, padding: '8px 12px', color: '#ffaa44', fontSize: 11, marginBottom: 10 },
}

function F({ label, children }) { return <div><label style={css.lbl}>{label}</label>{children}</div> }
function I({ value, onChange, type = 'text', placeholder = '' }) {
  return <input type={type} value={value} onChange={e => onChange(type === 'number' ? +e.target.value : e.target.value)} placeholder={placeholder} style={css.inp} />
}
function Sl({ value, onChange, opts }) {
  return <select value={value} onChange={e => onChange(e.target.value)} style={css.inp}>{opts.map(o => <option key={o}>{o}</option>)}</select>
}
function Btn({ onClick, children }) { return <button onClick={onClick} style={css.btn}>{children}</button> }
function Auth({ v, set }) {
  return <label style={css.auth}><input type="checkbox" checked={v} onChange={e => set(e.target.checked)} /> authorization_confirmed</label>
}
function H3({ color, children }) { return <h3 style={{ color, margin: '0 0 14px', fontSize: 15 }}>{children}</h3> }

// ─── ATTACK PLANNER ──────────────────────────────────────────────────────────
function PlannerPanel() {
  const [profile, setProfile]   = useState('corporate_windows')
  const [objective, setObj]     = useState('intelligence_gathering')
  const [skill, setSkill]       = useState('expert')
  const [budget, setBudget]     = useState(90)
  const [stealth, setStealth]   = useState('high')
  const [planId, setPlanId]     = useState('')
  const [auth, setAuth]         = useState(false)
  const { res, loading, call, get, setRes } = useApi() || { res:null, loading:false, call:()=>{}, get:()=>{} }
  const api = useApi()

  const profiles   = ['corporate_windows','government_network','critical_infrastructure','financial_institution','telecom_operator','cloud_saas']
  const objectives = ['intelligence_gathering','ransomware_deployment','sabotage_ics','supply_chain_compromise','destructive_wiper','financial_fraud']
  const skills     = ['beginner','intermediate','advanced','expert']

  const extractPlanId = (data) => {
    if (data?.plan_id) setPlanId(data.plan_id)
  }

  return (
    <div style={css.panel}>
      <H3 color="#ff6644">🗺️ Attack Planner — Kill Chain ATT&CK automatisé{api.loading && <Sp />}</H3>
      <div style={css.warn}>⚠️ Usage exclusivement légal — pentest autorisé / red team contractuel uniquement</div>
      <div style={css.grid3}>
        <F label="Profil cible"><Sl value={profile} onChange={setProfile} opts={profiles} /></F>
        <F label="Objectif stratégique"><Sl value={objective} onChange={setObj} opts={objectives} /></F>
        <F label="Compétence opérateur"><Sl value={skill} onChange={setSkill} opts={skills} /></F>
        <F label="Budget temps (jours)"><I type="number" value={budget} onChange={setBudget} /></F>
        <F label="Priorité furtivité"><Sl value={stealth} onChange={setStealth} opts={['low','medium','high','maximum']} /></F>
        <F label="Plan ID (pour graphe/risque)"><I value={planId} onChange={setPlanId} placeholder="généré auto" /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/automation/planner/profiles')}>🎯 Profils cibles</Btn>
        <Btn onClick={() => api.get('/automation/planner/objectives')}>📋 Objectifs</Btn>
        <Btn onClick={() => api.get('/automation/planner/kill-chain')}>⛓️ Kill Chain</Btn>
        <Btn onClick={async () => {
          const data = await apiFetch('/automation/planner/generate', {
            method: 'POST',
            body: JSON.stringify({ authorization_confirmed: auth, target_profile: profile,
              objective, operator_skill: skill, time_budget_days: budget, stealth_priority: stealth })
          }).catch(e => ({ error: e.message }))
          if (data?.plan_id) setPlanId(data.plan_id)
          api.get('/automation/planner/plans')
        }}>⚡ Générer Plan</Btn>
        <Btn onClick={() => api.get(`/automation/planner/plan/${planId}`)}>📄 Détail plan</Btn>
        <Btn onClick={() => api.get(`/automation/planner/graph/${planId}`)}>🕸️ Graphe ATT&CK</Btn>
        <Btn onClick={() => api.get(`/automation/planner/detection-risk/${planId}`)}>🔎 Risque détection</Btn>
        <Btn onClick={() => api.get('/automation/planner/plans')}>📋 Tous les plans</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── CAMPAIGN MANAGER ────────────────────────────────────────────────────────
function CampaignPanel() {
  const [name, setName]         = useState('Operation BlackSun')
  const [opType, setOpType]     = useState('apt_espionage')
  const [targets, setTargets]   = useState('{"name":"Acme Corp","sector":"energy"}')
  const [operator, setOperator] = useState('operator_1')
  const [startDate, setStart]   = useState('')
  const [campaignId, setCid]    = useState('')
  const [phase, setPhase]       = useState('reconnaissance')
  const [progress, setProgress] = useState(100)
  const [hostname, setHost]     = useState('WORKSTATION-001')
  const [access, setAccess]     = useState('user')
  const [status, setStatus]     = useState('active')
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const opTypes = ['apt_espionage','ransomware_campaign','strategic_disruption','supply_chain_op','financial_operation','hacktivist_campaign']
  const phases  = ['setup','reconnaissance','weaponization','delivery','exploitation','expansion','collection','exfiltration','impact']

  const parseTargets = () => {
    try { return [JSON.parse(targets)] } catch { return [{ name: targets }] }
  }

  return (
    <div style={css.panel}>
      <H3 color="#ff9900">🎯 Campaign Manager — Orchestration multi-cibles{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Nom de campagne"><I value={name} onChange={setName} /></F>
        <F label="Type d'opération"><Sl value={opType} onChange={setOpType} opts={opTypes} /></F>
        <F label="Opérateur"><I value={operator} onChange={setOperator} /></F>
        <F label="Cibles (JSON)"><I value={targets} onChange={setTargets} /></F>
        <F label="Date de début"><I type="date" value={startDate} onChange={setStart} /></F>
        <F label="Campaign ID"><I value={campaignId} onChange={setCid} placeholder="auto" /></F>
        <F label="Phase à avancer"><Sl value={phase} onChange={setPhase} opts={phases} /></F>
        <F label="Progression (%)"><I type="number" value={progress} onChange={setProgress} /></F>
        <F label="Hôte compromis"><I value={hostname} onChange={setHost} /></F>
        <F label="Niveau accès"><Sl value={access} onChange={setAccess} opts={['user','admin','domain_admin','system']} /></F>
        <F label="Nouveau statut"><Sl value={status} onChange={setStatus} opts={['planning','active','paused','completed','aborted']} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/automation/campaign/operation-types')}>📋 Types ops</Btn>
        <Btn onClick={async () => {
          const data = await apiFetch('/automation/campaign/create', {
            method: 'POST',
            body: JSON.stringify({ authorization_confirmed: auth, name, operation_type: opType,
              targets: parseTargets(), operator, start_date: startDate || null })
          }).catch(e => ({ error: e.message }))
          if (data?.campaign_id) setCid(data.campaign_id)
          else api.get('/automation/campaign/list')
        }}>🚀 Créer Campagne</Btn>
        <Btn onClick={() => api.get('/automation/campaign/list')}>📋 Toutes campagnes</Btn>
        <Btn onClick={() => api.get(`/automation/campaign/${campaignId}`)}>🔍 Détail campagne</Btn>
        <Btn onClick={() => api.call(`/automation/campaign/${campaignId}/advance-phase`, { authorization_confirmed: auth, phase_name: phase, progress_pct: progress })}>⏩ Avancer phase</Btn>
        <Btn onClick={() => api.call(`/automation/campaign/${campaignId}/add-host`, { authorization_confirmed: auth, hostname, access_level: access })}>💻 Ajouter hôte</Btn>
        <Btn onClick={() => api.call(`/automation/campaign/${campaignId}/status`, { authorization_confirmed: auth, status })}>🔄 Changer statut</Btn>
        <Btn onClick={() => api.get(`/automation/campaign/${campaignId}/report`)}>📊 Rapport</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── ANTI-FORENSICS ──────────────────────────────────────────────────────────
function AntiForensicsPanel() {
  const [osType, setOs]         = useState('linux')
  const [logTargets, setLogs]   = useState('bash_history,auth_log,wtmp_utmp')
  const [dryRun, setDryRun]     = useState(true)
  const [targetPath, setPath]   = useState('/tmp/test_file')
  const [technique, setTech]    = useState('mace_clone')
  const [refFile, setRef]       = useState('/bin/ls')
  const [memTechs, setMem]      = useState('dll_unhooking,beacon_sleep_obfuscation')
  const [files, setFiles]       = useState('/tmp/stager,/tmp/beacon')
  const [deleteMethod, setDel]  = useState('random_overwrite')
  const [scenario, setScenario] = useState('post_exfil')
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const timestompTechs = ['mace_clone','epoch_zero','custom_date','ntfs_extended']
  const deleteMethods  = ['shred_dod','gutmann','random_overwrite','crypto_erase']
  const scenarios      = ['post_exfil','post_lateral','full_wipe']

  return (
    <div style={css.panel}>
      <H3 color="#44ccff">🧹 Anti-Forensics — Effacement traces & artefacts{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="OS cible"><Sl value={osType} onChange={setOs} opts={['linux','windows']} /></F>
        <F label="Logs à effacer (virgule)"><I value={logTargets} onChange={setLogs} /></F>
        <F label="Mode dry-run"><Sl value={String(dryRun)} onChange={v => setDryRun(v === 'true')} opts={['true','false']} /></F>
        <F label="Fichier cible (timestomp)"><I value={targetPath} onChange={setPath} /></F>
        <F label="Technique timestomp"><Sl value={technique} onChange={setTech} opts={timestompTechs} /></F>
        <F label="Fichier référence"><I value={refFile} onChange={setRef} /></F>
        <F label="Techniques mémoire (virgule)"><I value={memTechs} onChange={setMem} /></F>
        <F label="Fichiers à supprimer (virgule)"><I value={files} onChange={setFiles} /></F>
        <F label="Méthode suppression"><Sl value={deleteMethod} onChange={setDel} opts={deleteMethods} /></F>
        <F label="Scénario nettoyage"><Sl value={scenario} onChange={setScenario} opts={scenarios} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get(`/automation/antiforensics/log-targets?os=${osType}`)}>📋 Cibles logs</Btn>
        <Btn onClick={() => api.get('/automation/antiforensics/timestomp-techniques')}>🕐 Techniques timestomp</Btn>
        <Btn onClick={() => api.get('/automation/antiforensics/memory-evasion-list')}>🧠 Évasion mémoire</Btn>
        <Btn onClick={() => api.get('/automation/antiforensics/secure-delete-methods')}>🗑️ Méthodes suppression</Btn>
        <Btn onClick={() => api.call('/automation/antiforensics/clear-logs', {
          authorization_confirmed: auth, os_type: osType,
          targets: logTargets.split(',').map(s => s.trim()), dry_run: dryRun
        })}>🧹 Effacer logs</Btn>
        <Btn onClick={() => api.call('/automation/antiforensics/timestomp', {
          authorization_confirmed: auth, target_path: targetPath, technique, reference_file: refFile
        })}>🕐 Timestomp</Btn>
        <Btn onClick={() => api.call('/automation/antiforensics/memory-evasion', {
          authorization_confirmed: auth, techniques: memTechs.split(',').map(s => s.trim())
        })}>🧠 Plan évasion mémoire</Btn>
        <Btn onClick={() => api.call('/automation/antiforensics/secure-delete', {
          authorization_confirmed: auth, files: files.split(',').map(s => s.trim()), method: deleteMethod
        })}>🗑️ Suppression sécurisée</Btn>
        <Btn onClick={() => api.call('/automation/antiforensics/full-cleanup', {
          authorization_confirmed: auth, os_type: osType, scenario
        })}>💥 Plan nettoyage complet</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── PAYLOAD BUILDER ─────────────────────────────────────────────────────────
function PayloadPanel() {
  const [payType, setPayType]   = useState('staged_shellcode')
  const [lhost, setLhost]       = useState('192.168.1.100')
  const [lport, setLport]       = useState(443)
  const [lang, setLang]         = useState('csharp')
  const [obfs, setObfs]         = useState('aes_encrypt,syscall_direct,anti_analysis')
  const [c2Profile, setC2]      = useState('domain_fronting')
  const [targetOs, setTargetOs] = useState('windows')
  const [payloadId, setPayId]   = useState('')
  const [stages, setStages]     = useState(3)
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const payTypes   = ['reverse_shell','staged_shellcode','reflective_dll','process_hollow','lolbin_stager','macro_dropper','hta_payload','linux_elf','uefi_implant']
  const langs      = ['c','csharp','nim','rust','go','python','powershell','vba','bash']
  const c2Profiles = ['malleable_c2','dns_c2','https_certificate_pinning','domain_fronting','sleeping_beacon']

  return (
    <div style={css.panel}>
      <H3 color="#cc44ff">💣 Payload Builder — Polymorphique & Obfuscation{api.loading && <Sp />}</H3>
      <div style={css.warn}>⚠️ Usage exclusivement légal — pentest autorisé / simulation uniquement</div>
      <div style={css.grid3}>
        <F label="Type de payload"><Sl value={payType} onChange={setPayType} opts={payTypes} /></F>
        <F label="LHOST"><I value={lhost} onChange={setLhost} /></F>
        <F label="LPORT"><I type="number" value={lport} onChange={setLport} /></F>
        <F label="Langage"><Sl value={lang} onChange={setLang} opts={langs} /></F>
        <F label="Profil C2"><Sl value={c2Profile} onChange={setC2} opts={c2Profiles} /></F>
        <F label="OS cible"><Sl value={targetOs} onChange={setTargetOs} opts={['windows','linux','macos','uefi']} /></F>
        <F label="Obfuscation (virgule)"><I value={obfs} onChange={setObfs} placeholder="aes_encrypt,syscall_direct..." /></F>
        <F label="Payload ID (rebuild)"><I value={payloadId} onChange={setPayId} placeholder="généré auto" /></F>
        <F label="Stages (stager chain)"><I type="number" value={stages} onChange={setStages} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/automation/payload/types')}>📋 Types</Btn>
        <Btn onClick={() => api.get('/automation/payload/obfuscation')}>🔀 Obfuscation</Btn>
        <Btn onClick={() => api.get('/automation/payload/c2-profiles')}>📡 Profils C2</Btn>
        <Btn onClick={() => api.get('/automation/payload/lolbins')}>🛠️ LOLBins</Btn>
        <Btn onClick={async () => {
          const data = await apiFetch('/automation/payload/generate', {
            method: 'POST',
            body: JSON.stringify({ authorization_confirmed: auth, payload_type: payType, lhost, lport,
              lang, obfuscation: obfs.split(',').map(s => s.trim()), c2_profile: c2Profile, target_os: targetOs })
          }).catch(e => ({ error: e.message }))
          if (data?.payload_id) setPayId(data.payload_id)
          else api.get('/automation/payload/list')
        }}>⚡ Générer Payload</Btn>
        <Btn onClick={() => api.get('/automation/payload/list')}>📋 Tous payloads</Btn>
        <Btn onClick={() => api.call(`/automation/payload/${payloadId}/rebuild`, { authorization_confirmed: auth })}>🔄 Rebuild polymorphique</Btn>
        <Btn onClick={() => api.call('/automation/payload/stager-chain', { authorization_confirmed: auth, lhost, lport, stages })}>⛓️ Stager Chain</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── OPSEC ───────────────────────────────────────────────────────────────────
function OpsecPanel() {
  const [opName, setOpName]     = useState('Operation Alpha')
  const [attrTechs, setAttr]    = useState('false_flag,living_off_the_land')
  const [opType, setOpType]     = useState('apt_espionage')
  const [strategy, setStrategy] = useState('phase_based')
  const [duration, setDuration] = useState(90)
  const [assessId, setAssessId] = useState('')
  const [auth, setAuth]         = useState(false)
  const api = useApi()

  const strategies = ['burn_after_use','time_based','detection_triggered','phase_based']
  const opTypes    = ['apt_espionage','ransomware_campaign','strategic_disruption','supply_chain_op']

  return (
    <div style={css.panel}>
      <H3 color="#44ff88">🥷 OPSEC — Operations Security{api.loading && <Sp />}</H3>
      <div style={css.grid3}>
        <F label="Nom d'opération"><I value={opName} onChange={setOpName} /></F>
        <F label="Type d'opération"><Sl value={opType} onChange={setOpType} opts={opTypes} /></F>
        <F label="Stratégie rotation"><Sl value={strategy} onChange={setStrategy} opts={strategies} /></F>
        <F label="Durée campagne (jours)"><I type="number" value={duration} onChange={setDuration} /></F>
        <F label="Techniques attribution (virgule)"><I value={attrTechs} onChange={setAttr} placeholder="false_flag,living_off_the_land" /></F>
        <F label="Assessment ID"><I value={assessId} onChange={setAssessId} placeholder="auto" /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={css.btns}>
        <Btn onClick={() => api.get('/automation/opsec/categories')}>📋 Catégories</Btn>
        <Btn onClick={() => api.get('/automation/opsec/attribution-techniques')}>🎭 Attribution</Btn>
        <Btn onClick={() => api.get('/automation/opsec/rotation-strategies')}>🔄 Rotations</Btn>
        <Btn onClick={() => api.call('/automation/opsec/quick-assess', { authorization_confirmed: auth, operation_name: opName })}>⚡ Quick Assess</Btn>
        <Btn onClick={async () => {
          const data = await apiFetch('/automation/opsec/assess', {
            method: 'POST',
            body: JSON.stringify({ authorization_confirmed: auth, operation_name: opName, checks_passed: {} })
          }).catch(e => ({ error: e.message }))
          if (data?.assessment_id) setAssessId(data.assessment_id)
        }}>🔍 Assess complet</Btn>
        <Btn onClick={() => api.call('/automation/opsec/attribution', {
          authorization_confirmed: auth,
          techniques: attrTechs.split(',').map(s => s.trim()),
          operation_type: opType
        })}>🎭 Plan Attribution</Btn>
        <Btn onClick={() => api.call('/automation/opsec/rotation-plan', {
          authorization_confirmed: auth, strategy, current_assets: [], campaign_duration_days: duration
        })}>🔄 Plan Rotation</Btn>
        <Btn onClick={() => api.get(`/automation/opsec/assessment/${assessId}`)}>📄 Résultat assess</Btn>
      </div>
      <ResultBox data={api.res} />
    </div>
  )
}

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function AutomationBloc7() {
  const [tab, setTab] = useState('planner')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          ⚙️ Automation Stratégique — Bloc 7
          <span style={{ marginLeft: 12, fontSize: 12, color: '#ff4444', fontWeight: 700 }}>SIMULATION — USAGE LÉGAL UNIQUEMENT</span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          Attack Planner (Kill Chain ATT&CK) · Campaign Manager · Anti-Forensics · Payload Builder · OPSEC
        </p>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '8px 18px', borderRadius: 8,
            border: `1px solid ${tab === t.id ? t.color : '#1a2a3a'}`,
            background: tab === t.id ? t.color + '22' : '#0a1520',
            color: tab === t.id ? t.color : '#667',
            cursor: 'pointer', fontSize: 13, fontWeight: tab === t.id ? 700 : 400,
            transition: 'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {tab === 'planner'       && <PlannerPanel />}
      {tab === 'campaign'      && <CampaignPanel />}
      {tab === 'antiforensics' && <AntiForensicsPanel />}
      {tab === 'payload'       && <PayloadPanel />}
      {tab === 'opsec'         && <OpsecPanel />}
    </div>
  )
}
