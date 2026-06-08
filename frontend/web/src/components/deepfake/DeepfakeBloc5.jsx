import { useState } from 'react'
import { apiFetch } from '../../utils/api'

const TABS = [
  { id: 'faceswap',  label: '🎭 Face Swap',       color: '#ff4466' },
  { id: 'video',     label: '🎬 Vidéo Deepfake',  color: '#ff8800' },
  { id: 'lipsync',   label: '👄 Lip Sync',         color: '#ffcc00' },
  { id: 'inject',    label: '📡 Live Injection',   color: '#44ccff' },
  { id: 'evasion',   label: '🛡️ Anti-Détection',  color: '#aa44ff' },
]

function ResultBox({ data }) {
  if (!data) return null
  return (
    <pre style={{
      background: '#0a0f1a', color: '#7affb2', border: '1px solid #1a3a1a',
      borderRadius: 8, padding: 12, marginTop: 10, fontSize: 11,
      maxHeight: 300, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
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
  return { res, loading, call, get, setRes }
}

const S = {
  panel: { background: '#0a1520', border: '1px solid #1a2a3a', borderRadius: 12, padding: 20 },
  h3: (c) => ({ color: c, margin: '0 0 14px', fontSize: 15 }),
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 },
  label: { display: 'block', fontSize: 11, color: '#667', marginBottom: 4 },
  inp: { width: '100%', background: '#060b14', border: '1px solid #1a2a3a', color: '#ccc', padding: '6px 10px', borderRadius: 6, fontSize: 12, boxSizing: 'border-box' },
  btns: { display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0' },
  btn: { background: '#1a2a3a', border: '1px solid #2a3a4a', color: '#aaccff', padding: '7px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  auth: { display: 'flex', alignItems: 'center', gap: 6, color: '#ff4444', fontSize: 12, margin: '10px 0', cursor: 'pointer' },
}

function F({ label, children }) {
  return <div><label style={S.label}>{label}</label>{children}</div>
}
function I({ value, onChange, type = 'text', placeholder = '' }) {
  return <input type={type} value={value} onChange={e => onChange(type === 'number' ? +e.target.value : e.target.value)} placeholder={placeholder} style={S.inp} />
}
function Sl({ value, onChange, opts }) {
  return <select value={value} onChange={e => onChange(e.target.value)} style={S.inp}>{opts.map(o => <option key={o}>{o}</option>)}</select>
}
function Btn({ onClick, children }) {
  return <button onClick={onClick} style={S.btn}>{children}</button>
}
function Auth({ v, set }) {
  return <label style={S.auth}><input type="checkbox" checked={v} onChange={e => set(e.target.checked)} /> authorization_confirmed — Pentest autorisé</label>
}

// ─── FACE SWAP ────────────────────────────────────────────────────────────────
function FaceSwapPanel() {
  const [srcFace, setSrc]     = useState('source.jpg')
  const [tgtImg, setTgtImg]   = useState('target.jpg')
  const [tgtVid, setTgtVid]   = useState('target.mp4')
  const [engine, setEngine]   = useState('insightface_roop')
  const [enhance, setEnhance] = useState('gfpgan')
  const [webcam, setWebcam]   = useState(0)
  const [v4l2, setV4l2]       = useState(20)
  const [auth, setAuth]       = useState(false)
  const { res, loading, call, get } = useApi()

  const engines = ['insightface_roop','simswap','deepfacelab','ghost','hififace']
  const enhancers = ['gfpgan','codeformer','restoreformer','none']

  return (
    <div style={S.panel}>
      <h3 style={S.h3('#ff4466')}>🎭 Face Swap — InsightFace / SimSwap / DeepFaceLab{loading && <Sp />}</h3>
      <div style={S.grid}>
        <F label="Source (visage à injecter)"><I value={srcFace} onChange={setSrc} placeholder="source.jpg" /></F>
        <F label="Moteur"><Sl value={engine} onChange={setEngine} opts={engines} /></F>
        <F label="Face Enhancement"><Sl value={enhance} onChange={setEnhance} opts={enhancers} /></F>
        <F label="Target image (swap image)"><I value={tgtImg} onChange={setTgtImg} placeholder="target.jpg" /></F>
        <F label="Target vidéo (swap vidéo)"><I value={tgtVid} onChange={setTgtVid} placeholder="target.mp4" /></F>
        <F label="Webcam ID (temps réel)"><I type="number" value={webcam} onChange={setWebcam} /></F>
        <F label="V4L2 output (no. /dev/videoX)"><I type="number" value={v4l2} onChange={setV4l2} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={S.btns}>
        <Btn onClick={() => get('/deepfake/faceswap/engines')}>📋 Moteurs</Btn>
        <Btn onClick={() => call('/deepfake/faceswap/detect', { authorization_confirmed: auth, image_path: tgtImg })}>🔍 Détecter visages</Btn>
        <Btn onClick={() => call('/deepfake/faceswap/image', { authorization_confirmed: auth, source_face_path: srcFace, target_image_path: tgtImg, engine, face_enhance: enhance, face_index: 0 })}>🖼️ Swap Image</Btn>
        <Btn onClick={() => call('/deepfake/faceswap/video', { authorization_confirmed: auth, source_face_path: srcFace, target_video_path: tgtVid, engine, face_enhance: enhance, keep_fps: true, many_faces: false })}>🎬 Swap Vidéo</Btn>
        <Btn onClick={() => call('/deepfake/faceswap/realtime', { authorization_confirmed: auth, source_face_path: srcFace, webcam_id: webcam, engine: 'ghost', output_v4l2: v4l2 })}>⚡ Temps Réel</Btn>
      </div>
      {res?.job_id && <div style={{ fontSize: 11, color: '#667', marginTop: 4 }}>Job ID : {res.job_id}</div>}
      <ResultBox data={res} />
    </div>
  )
}

// ─── VIDEO DEEPFAKE ───────────────────────────────────────────────────────────
function VideoPanel() {
  const [srcImg, setSrcImg]   = useState('portrait.jpg')
  const [audio, setAudio]     = useState('speech.wav')
  const [drvVid, setDrvVid]   = useState('driver.mp4')
  const [model, setModel]     = useState('sadtalker')
  const [preset, setPreset]   = useState('ceo_male_eu')
  const [style, setStyle]     = useState('professional_news_anchor')
  const [script, setScript]   = useState('Bonjour, je suis le PDG de la société...')
  const [avatarId, setAvatarId] = useState('')
  const [bg, setBg]           = useState('office')
  const [auth, setAuth]       = useState(false)
  const { res, loading, call, get, setRes } = useApi()

  const models = ['sadtalker','fomm','wav2lip','ditto','echomimic','vid2vid']
  const presets = ['ceo_male_eu','ceo_female_eu','it_tech_young','banker_formal','journalist_neutral','politician_authoritative']
  const styles = ['professional_news_anchor','cgi_animated','aged_10years','gender_swap','ethnic_shift','lighting_studio']
  const bgs = ['office','tv_studio','home','outdoor_city','green_screen']

  return (
    <div style={S.panel}>
      <h3 style={S.h3('#ff8800')}>🎬 Génération Vidéo Deepfake — Talking Head / Avatar{loading && <Sp />}</h3>

      <div style={{ fontSize: 11, color: '#ff880066', fontWeight: 700, marginBottom: 8 }}>— TALKING HEAD —</div>
      <div style={S.grid}>
        <F label="Image source (portrait)"><I value={srcImg} onChange={setSrcImg} /></F>
        <F label="Audio (discours)"><I value={audio} onChange={setAudio} /></F>
        <F label="Modèle"><Sl value={model} onChange={setModel} opts={models} /></F>
        <F label="Vidéo driver (FOMM)"><I value={drvVid} onChange={setDrvVid} /></F>
      </div>
      <div style={S.btns}>
        <Btn onClick={() => get('/deepfake/video/models')}>📋 Modèles</Btn>
        <Btn onClick={() => call('/deepfake/video/talking-head', { authorization_confirmed: auth, source_image: srcImg, audio_path: audio, model, enhance_face: true, background_enhance: false })}>🗣️ Talking Head</Btn>
        <Btn onClick={() => call('/deepfake/video/animate-portrait', { authorization_confirmed: auth, source_image: srcImg, driver_video: drvVid, model: 'fomm', relative_motion: true })}>💃 Animer Portrait</Btn>
      </div>

      <div style={{ fontSize: 11, color: '#ff880066', fontWeight: 700, margin: '12px 0 8px' }}>— AVATAR & SCÈNE —</div>
      <div style={S.grid}>
        <F label="Preset avatar"><Sl value={preset} onChange={setPreset} opts={presets} /></F>
        <F label="Décor scène"><Sl value={bg} onChange={setBg} opts={bgs} /></F>
        <F label="Style (Vid2Vid)"><Sl value={style} onChange={setStyle} opts={styles} /></F>
        <F label="Avatar ID (scène)"><I value={avatarId} onChange={setAvatarId} placeholder="auto-filled après création" /></F>
      </div>
      <F label="Script (scène)">
        <textarea value={script} onChange={e => setScript(e.target.value)} rows={2}
          style={{ ...S.inp, resize: 'vertical' }} />
      </F>
      <Auth v={auth} set={setAuth} />
      <div style={S.btns}>
        <Btn onClick={() => call('/deepfake/video/avatar/create', { authorization_confirmed: auth, preset, custom_description: '', generate_voice: true }).then(r => r?.avatar_id && setAvatarId(r.avatar_id))}>🧑 Créer Avatar</Btn>
        <Btn onClick={() => call('/deepfake/video/vid2vid', { authorization_confirmed: auth, source_video: 'source.mp4', target_style: style, preserve_motion: true })}>🎨 Vid2Vid</Btn>
        <Btn onClick={() => call('/deepfake/video/scene/generate', { authorization_confirmed: auth, script, avatar_id: avatarId, background: bg, duration_sec: 30 })}>🎥 Générer Scène</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── LIP SYNC ────────────────────────────────────────────────────────────────
function LipSyncPanel() {
  const [vid, setVid]     = useState('video.mp4')
  const [aud, setAud]     = useState('audio.wav')
  const [model, setModel] = useState('wav2lip')
  const [webcam, setWcm]  = useState(0)
  const [v4l2, setV4l2]   = useState(20)
  const [auth, setAuth]   = useState(false)
  const { res, loading, call, get } = useApi()

  return (
    <div style={S.panel}>
      <h3 style={S.h3('#ffcc00')}>👄 Lip Sync — Wav2Lip / MuseTalk / VideoReTalking{loading && <Sp />}</h3>
      <div style={S.grid}>
        <F label="Vidéo source"><I value={vid} onChange={setVid} /></F>
        <F label="Audio de remplacement"><I value={aud} onChange={setAud} /></F>
        <F label="Modèle lipsync"><Sl value={model} onChange={setModel} opts={['wav2lip','musetalk','videoretalk','difftalk']} /></F>
        <F label="Webcam ID (temps réel)"><I type="number" value={webcam} onChange={setWcm} /></F>
        <F label="V4L2 sortie (temps réel)"><I type="number" value={v4l2} onChange={setV4l2} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={S.btns}>
        <Btn onClick={() => get('/deepfake/lipsync/models')}>📋 Modèles</Btn>
        <Btn onClick={() => call('/deepfake/lipsync/sync', { authorization_confirmed: auth, video_path: vid, audio_path: aud, model, face_det_batch: 16, wav2lip_batch: 128, resize_factor: 1 })}>🔄 Sync Audio/Vidéo</Btn>
        <Btn onClick={() => call('/deepfake/lipsync/replace-voice', { authorization_confirmed: auth, video_path: vid, new_audio_path: aud, preserve_background_audio: false })}>🔊 Remplacer Voix</Btn>
        <Btn onClick={() => call('/deepfake/lipsync/realtime', { authorization_confirmed: auth, webcam_id: webcam, audio_source: 'cloned_voice', model: 'musetalk', output_v4l2: v4l2 })}>⚡ Temps Réel</Btn>
        <Btn onClick={() => call('/deepfake/lipsync/assess', { authorization_confirmed: auth, video_path: vid })}>📊 Évaluer Sync</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── LIVE INJECTION ───────────────────────────────────────────────────────────
function InjectPanel() {
  const [devNum, setDevNum]   = useState(20)
  const [label, setLabel]     = useState('Deepfake Camera')
  const [src, setSrc]         = useState('/dev/video0')
  const [tgt, setTgt]         = useState('/dev/video20')
  const [fps, setFps]         = useState(25)
  const [audSrc, setAudSrc]   = useState('deepfake_audio.wav')
  const [sink, setSink]       = useState('deepfake_mic')
  const [targetApp, setApp]   = useState('zoom')
  const [rtspUrl, setRtsp]    = useState('rtsp://192.168.1.100/stream')
  const [replVid, setReplVid] = useState('deepfake.mp4')
  const [auth, setAuth]       = useState(false)
  const { res, loading, call, get } = useApi()

  return (
    <div style={S.panel}>
      <h3 style={S.h3('#44ccff')}>📡 Live Injection — V4L2 / Zoom / Teams / RTSP{loading && <Sp />}</h3>

      <div style={{ fontSize: 11, color: '#44ccff44', fontWeight: 700, marginBottom: 8 }}>— SETUP V4L2 LOOPBACK —</div>
      <div style={S.grid}>
        <F label="Numéro device (/dev/videoX)"><I type="number" value={devNum} onChange={setDevNum} /></F>
        <F label="Label caméra virtuelle"><I value={label} onChange={setLabel} /></F>
        <F label="Source vidéo (inject)"><I value={src} onChange={setSrc} /></F>
        <F label="Target V4L2"><I value={tgt} onChange={setTgt} /></F>
        <F label="FPS"><I type="number" value={fps} onChange={setFps} /></F>
      </div>

      <div style={{ fontSize: 11, color: '#44ccff44', fontWeight: 700, margin: '12px 0 8px' }}>— INJECTION APPEL VIDÉO —</div>
      <div style={S.grid}>
        <F label="Application cible"><Sl value={targetApp} onChange={setApp} opts={['zoom','teams','meet','webex','rtsp_stream','webrtc_hijack']} /></F>
        <F label="Source audio (PulseAudio)"><I value={audSrc} onChange={setAudSrc} /></F>
        <F label="Nom sink PulseAudio"><I value={sink} onChange={setSink} /></F>
        <F label="URL RTSP (hijack)"><I value={rtspUrl} onChange={setRtsp} /></F>
        <F label="Vidéo de remplacement (RTSP)"><I value={replVid} onChange={setReplVid} /></F>
      </div>

      <Auth v={auth} set={setAuth} />
      <div style={S.btns}>
        <Btn onClick={() => get('/deepfake/inject/targets')}>📋 Cibles</Btn>
        <Btn onClick={() => call('/deepfake/inject/v4l2/setup', { authorization_confirmed: auth, device_num: devNum, label })}>⚙️ Setup V4L2</Btn>
        <Btn onClick={() => call('/deepfake/inject/video/stream', { authorization_confirmed: auth, source: src, target_device: tgt, fps, loop: true })}>▶ Injecter Vidéo</Btn>
        <Btn onClick={() => call('/deepfake/inject/audio/pulse', { authorization_confirmed: auth, audio_source: audSrc, sink_name: sink })}>🎙️ Injecter Audio</Btn>
        <Btn onClick={() => call('/deepfake/inject/call/start', { authorization_confirmed: auth, target_app: targetApp, video_source: tgt, audio_source: sink, face_swap_active: true, lipsync_active: true })}>📞 Démarrer Appel</Btn>
        <Btn onClick={() => call('/deepfake/inject/rtsp/hijack', { authorization_confirmed: auth, rtsp_url: rtspUrl, replacement_video: replVid, mitm_mode: 'arp_spoof' })}>🎯 RTSP Hijack</Btn>
      </div>
      <ResultBox data={res} />
    </div>
  )
}

// ─── DETECTION EVASION ────────────────────────────────────────────────────────
function EvasionPanel() {
  const [videoPath, setVideoPath] = useState('deepfake.mp4')
  const [technique, setTech]      = useState('adversarial_perturbation')
  const [detector, setDet]        = useState('faceforensics')
  const [intensity, setIntensity] = useState(1.0)
  const [auth, setAuth]           = useState(false)
  const { res, loading, call, get } = useApi()

  const techniques = [
    'adversarial_perturbation','temporal_smoothing','jpeg_compression',
    'rppg_overlay','facial_geometry_norm','style_transfer_blend',
    'gan_discriminator_finetune','compression_artifacts_sim',
  ]
  const detectors = ['faceforensics','deepware','ms_authenticator','intel_fakecatcher','grad_cam_cnn','temporally_aware']

  return (
    <div style={S.panel}>
      <h3 style={S.h3('#aa44ff')}>🛡️ Anti-Détection — Adversarial / rPPG / GAN Bypass{loading && <Sp />}</h3>

      <div style={{ background: '#1a0a2a', border: '1px solid #aa44ff33', borderRadius: 8, padding: 10, marginBottom: 14, fontSize: 12, color: '#aa88cc' }}>
        <strong>Détecteurs ciblés :</strong> FaceForensics++ (XceptionNet) · Deepware Scanner · Microsoft Video Authenticator · Intel FakeCatcher (rPPG) · GradCAM CNN · Temporal LSTM
      </div>

      <div style={S.grid}>
        <F label="Vidéo à traiter"><I value={videoPath} onChange={setVideoPath} /></F>
        <F label="Technique de bypass"><Sl value={technique} onChange={setTech} opts={techniques} /></F>
        <F label="Détecteur cible"><Sl value={detector} onChange={setDet} opts={detectors} /></F>
        <F label="Intensité (0.1 - 2.0)"><I type="number" value={intensity} onChange={setIntensity} /></F>
      </div>
      <Auth v={auth} set={setAuth} />
      <div style={S.btns}>
        <Btn onClick={() => get('/deepfake/evasion/detectors')}>📋 Détecteurs</Btn>
        <Btn onClick={() => get('/deepfake/evasion/techniques')}>🔧 Techniques</Btn>
        <Btn onClick={() => call('/deepfake/evasion/analyze', { authorization_confirmed: auth, video_path: videoPath, detectors: null })}>🔍 Analyser Risque</Btn>
        <Btn onClick={() => call('/deepfake/evasion/bypass/apply', { authorization_confirmed: auth, video_path: videoPath, technique, target_detector: detector, intensity })}>⚡ Appliquer Bypass</Btn>
        <Btn onClick={() => call('/deepfake/evasion/bypass/full-pipeline', { authorization_confirmed: auth, video_path: videoPath, target_detectors: detectors })}>🚀 Pipeline Complet</Btn>
      </div>
      {res && !res.error && res.final_bypass_rate && (
        <div style={{ marginTop: 10, padding: 10, background: res.final_bypass_rate > 0.75 ? '#0a2a0a' : '#2a1a0a', borderRadius: 8, fontSize: 12 }}>
          <strong style={{ color: res.final_bypass_rate > 0.75 ? '#44ff88' : '#ff8800' }}>
            Bypass rate : {(res.final_bypass_rate * 100).toFixed(1)}% — {res.verdict}
          </strong>
        </div>
      )}
      <ResultBox data={res} />
    </div>
  )
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function DeepfakeBloc5() {
  const [tab, setTab] = useState('faceswap')

  return (
    <div style={{ padding: 20, minHeight: '100vh', background: '#060b14' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#fff', margin: 0, fontSize: 20 }}>
          🎭 Deepfake Vidéo Temps Réel — Bloc 5
          <span style={{ marginLeft: 12, fontSize: 12, color: '#ff4444', fontWeight: 700 }}>SIMULATION MODE</span>
        </h2>
        <p style={{ color: '#667', fontSize: 12, margin: '4px 0 0' }}>
          Face Swap (roop/SimSwap) · Talking Head (SadTalker) · Lip Sync (Wav2Lip/MuseTalk) · V4L2 Injection · Anti-Détection
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
          }}>{t.label}</button>
        ))}
      </div>

      {tab === 'faceswap' && <FaceSwapPanel />}
      {tab === 'video'    && <VideoPanel />}
      {tab === 'lipsync'  && <LipSyncPanel />}
      {tab === 'inject'   && <InjectPanel />}
      {tab === 'evasion'  && <EvasionPanel />}
    </div>
  )
}
