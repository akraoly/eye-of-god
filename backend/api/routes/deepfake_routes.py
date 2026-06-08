from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.social.deepfake_service import deepfake_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class CloneFileReq(AuthReq):
    audio_path: str
    voice_name: str


class CloneYTReq(AuthReq):
    youtube_url: str
    voice_name: str


class SpeechReq(AuthReq):
    voice_id: str
    text: str
    language: str = "fr"
    emotion: str = "normal"


class ScriptReq(AuthReq):
    context: str
    target_name: str
    target_role: str
    scenario: str = "IT_URGENT"


class CallReq(AuthReq):
    voice_id: str
    script: str
    target_number: str
    caller_id: Optional[str] = None


class InteractiveCallReq(AuthReq):
    voice_id: str
    scenario: str
    target_number: str
    caller_id: Optional[str] = None


class AnalyzeReq(AuthReq):
    recording_url: str


class DeleteVoiceReq(AuthReq):
    voice_id: str


class PhishingEmailReq(AuthReq):
    context: str
    target_name: str
    target_email: str
    company: str


@router.get("/voices")
async def list_voices():
    return await deepfake_service.list_voices()


@router.get("/scenarios")
async def get_scenarios():
    return await deepfake_service.get_available_scenarios()


@router.get("/campaigns")
async def get_campaigns():
    return await deepfake_service.get_campaigns()


@router.post("/voice/clone/file")
async def clone_from_file(req: CloneFileReq):
    _req_auth(req.authorization_confirmed, "clone_voice_file")
    return await deepfake_service.clone_voice_from_file(req.audio_path, req.voice_name)


@router.post("/voice/clone/youtube")
async def clone_from_youtube(req: CloneYTReq):
    _req_auth(req.authorization_confirmed, "clone_voice_youtube")
    return await deepfake_service.clone_voice_from_youtube(req.youtube_url, req.voice_name)


@router.post("/speech/generate")
async def generate_speech(req: SpeechReq):
    _req_auth(req.authorization_confirmed, "generate_speech")
    path = await deepfake_service.generate_speech(req.voice_id, req.text, req.language, req.emotion)
    return {"audio_path": path}


@router.post("/script/generate")
async def generate_script(req: ScriptReq):
    _req_auth(req.authorization_confirmed, "generate_script")
    script = await deepfake_service.generate_script(req.context, req.target_name, req.target_role, req.scenario)
    return {"script": script}


@router.post("/call/generate")
async def generate_call(req: CallReq):
    _req_auth(req.authorization_confirmed, "generate_call")
    return await deepfake_service.generate_call(req.voice_id, req.script, req.target_number, req.caller_id)


@router.post("/call/interactive")
async def interactive_call(req: InteractiveCallReq):
    _req_auth(req.authorization_confirmed, "interactive_call")
    return await deepfake_service.generate_interactive_call(req.voice_id, req.scenario, req.target_number, req.caller_id)


@router.post("/call/analyze")
async def analyze_recording(req: AnalyzeReq):
    _req_auth(req.authorization_confirmed, "analyze_recording")
    return await deepfake_service.analyze_call_recording(req.recording_url)


@router.post("/voice/delete")
async def delete_voice(req: DeleteVoiceReq):
    _req_auth(req.authorization_confirmed, "delete_voice")
    ok = await deepfake_service.delete_voice(req.voice_id)
    return {"deleted": ok}


@router.post("/phishing/email")
async def phishing_email(req: PhishingEmailReq):
    _req_auth(req.authorization_confirmed, "phishing_email")
    return await deepfake_service.generate_phishing_email(req.context, req.target_name, req.target_email, req.company)


# ─── Bloc 5 — Deepfake Vidéo Temps Réel ──────────────────────────────────────

from services.deepfake.face_swap_service      import FaceSwapService
from services.deepfake.video_deepfake_service import VideoDeepfakeService
from services.deepfake.lipsync_service        import LipSyncService
from services.deepfake.live_inject_service    import LiveInjectService
from services.deepfake.detection_evade_service import DetectionEvadeService

_fswap  = FaceSwapService()
_vid    = VideoDeepfakeService()
_lip    = LipSyncService()
_inject = LiveInjectService()
_evade  = DetectionEvadeService()


# ── Face Swap ──────────────────────────────────────────────────────────────────

class FaceSwapImageReq(AuthReq):
    source_face_path:  str = "source.jpg"
    target_image_path: str = "target.jpg"
    engine:            str = "insightface_roop"
    face_enhance:      str = "gfpgan"
    face_index:        int = 0

class FaceSwapVideoReq(AuthReq):
    source_face_path:  str = "source.jpg"
    target_video_path: str = "target.mp4"
    engine:            str = "insightface_roop"
    face_enhance:      str = "gfpgan"
    keep_fps:          bool = True
    many_faces:        bool = False

class RealtimeSwapReq(AuthReq):
    source_face_path: str = "source.jpg"
    webcam_id:        int = 0
    engine:           str = "ghost"
    output_v4l2:      int = 20

class DetectFacesReq(AuthReq):
    image_path: str = "image.jpg"


@router.get("/faceswap/engines")
async def faceswap_engines():
    return _fswap.list_engines()

@router.post("/faceswap/image")
async def faceswap_image(req: FaceSwapImageReq):
    _req_auth(req.authorization_confirmed, "faceswap_image")
    return _fswap.swap_image(req.source_face_path, req.target_image_path, req.engine, req.face_enhance, req.face_index)

@router.post("/faceswap/video")
async def faceswap_video(req: FaceSwapVideoReq):
    _req_auth(req.authorization_confirmed, "faceswap_video")
    return _fswap.swap_video(req.source_face_path, req.target_video_path, req.engine, req.face_enhance, req.keep_fps, req.many_faces)

@router.post("/faceswap/realtime")
async def faceswap_realtime(req: RealtimeSwapReq):
    _req_auth(req.authorization_confirmed, "faceswap_realtime")
    return _fswap.realtime_swap(req.source_face_path, req.webcam_id, req.engine, req.output_v4l2)

@router.post("/faceswap/detect")
async def faceswap_detect(req: DetectFacesReq):
    _req_auth(req.authorization_confirmed, "detect_faces")
    return _fswap.detect_faces(req.image_path)

@router.get("/faceswap/job/{job_id}")
async def faceswap_job(job_id: str):
    return _fswap.get_job(job_id)


# ── Video Deepfake ─────────────────────────────────────────────────────────────

class TalkingHeadReq(AuthReq):
    source_image:       str  = "portrait.jpg"
    audio_path:         str  = "speech.wav"
    model:              str  = "sadtalker"
    enhance_face:       bool = True
    background_enhance: bool = False

class AnimatePortraitReq(AuthReq):
    source_image:   str  = "portrait.jpg"
    driver_video:   str  = "driver.mp4"
    model:          str  = "fomm"
    relative_motion: bool = True

class CreateAvatarReq(AuthReq):
    preset:              str  = "ceo_male_eu"
    custom_description:  str  = ""
    generate_voice:      bool = True

class Vid2VidReq(AuthReq):
    source_video:     str  = "video.mp4"
    target_style:     str  = "professional_news_anchor"
    preserve_motion:  bool = True

class FullSceneReq(AuthReq):
    script:       str = "Bonjour, je suis le PDG..."
    avatar_id:    str = ""
    background:   str = "office"
    duration_sec: int = 30


@router.get("/video/models")
async def video_models():
    return _vid.list_models()

@router.get("/video/avatar-presets")
async def video_avatar_presets():
    return _vid.list_avatar_presets()

@router.post("/video/talking-head")
async def video_talking_head(req: TalkingHeadReq):
    _req_auth(req.authorization_confirmed, "generate_talking_head")
    return _vid.generate_talking_head(req.source_image, req.audio_path, req.model, req.enhance_face, req.background_enhance)

@router.post("/video/animate-portrait")
async def video_animate(req: AnimatePortraitReq):
    _req_auth(req.authorization_confirmed, "animate_portrait")
    return _vid.animate_portrait(req.source_image, req.driver_video, req.model, req.relative_motion)

@router.post("/video/avatar/create")
async def video_avatar_create(req: CreateAvatarReq):
    _req_auth(req.authorization_confirmed, "create_avatar")
    return _vid.create_avatar(req.preset, req.custom_description, req.generate_voice)

@router.post("/video/vid2vid")
async def video_vid2vid(req: Vid2VidReq):
    _req_auth(req.authorization_confirmed, "vid2vid_transform")
    return _vid.vid2vid_transform(req.source_video, req.target_style, req.preserve_motion)

@router.post("/video/scene/generate")
async def video_scene(req: FullSceneReq):
    _req_auth(req.authorization_confirmed, "generate_scene")
    return _vid.generate_full_scene(req.script, req.avatar_id, req.background, req.duration_sec)

@router.get("/video/job/{job_id}")
async def video_job(job_id: str):
    return _vid.get_job(job_id)


# ── Lip Sync ──────────────────────────────────────────────────────────────────

class LipSyncReq(AuthReq):
    video_path:        str = "video.mp4"
    audio_path:        str = "audio.wav"
    model:             str = "wav2lip"
    face_det_batch:    int = 16
    wav2lip_batch:     int = 128
    resize_factor:     int = 1

class LipSyncRealtimeReq(AuthReq):
    webcam_id:     int = 0
    audio_source:  str = "cloned_voice"
    model:         str = "musetalk"
    output_v4l2:   int = 20

class LipSyncReplaceVoiceReq(AuthReq):
    video_path:                  str  = "video.mp4"
    new_audio_path:              str  = "cloned.wav"
    preserve_background_audio:   bool = False

class AssessSyncReq(AuthReq):
    video_path: str = "video.mp4"


@router.get("/lipsync/models")
async def lipsync_models():
    return _lip.list_models()

@router.post("/lipsync/sync")
async def lipsync_sync(req: LipSyncReq):
    _req_auth(req.authorization_confirmed, "lipsync_sync")
    return _lip.sync_video_audio(req.video_path, req.audio_path, req.model, req.face_det_batch, req.wav2lip_batch, req.resize_factor)

@router.post("/lipsync/realtime")
async def lipsync_realtime(req: LipSyncRealtimeReq):
    _req_auth(req.authorization_confirmed, "lipsync_realtime")
    return _lip.sync_realtime(req.webcam_id, req.audio_source, req.model, req.output_v4l2)

@router.post("/lipsync/replace-voice")
async def lipsync_replace(req: LipSyncReplaceVoiceReq):
    _req_auth(req.authorization_confirmed, "replace_voice_lipsync")
    return _lip.replace_voice_in_video(req.video_path, req.new_audio_path, req.preserve_background_audio)

@router.post("/lipsync/assess")
async def lipsync_assess(req: AssessSyncReq):
    _req_auth(req.authorization_confirmed, "assess_lipsync")
    return _lip.assess_sync_quality(req.video_path)


# ── Live Injection ─────────────────────────────────────────────────────────────

class V4L2SetupReq(AuthReq):
    device_num: int = 20
    label:      str = "Deepfake Camera"

class InjectStreamReq(AuthReq):
    source:        str  = "/dev/video0"
    target_device: str  = "/dev/video20"
    fps:           int  = 25
    loop:          bool = True

class InjectAudioReq(AuthReq):
    audio_source: str = "deepfake_audio.wav"
    sink_name:    str = "deepfake_mic"

class CallInjectReq(AuthReq):
    target_app:       str  = "zoom"
    video_source:     str  = "/dev/video20"
    audio_source:     str  = "deepfake_mic"
    face_swap_active: bool = True
    lipsync_active:   bool = True

class RTSPHijackReq(AuthReq):
    rtsp_url:          str = "rtsp://192.168.1.100/stream"
    replacement_video: str = "deepfake.mp4"
    mitm_mode:         str = "arp_spoof"


@router.get("/inject/targets")
async def inject_targets():
    return _inject.list_targets()

@router.post("/inject/v4l2/setup")
async def inject_v4l2_setup(req: V4L2SetupReq):
    _req_auth(req.authorization_confirmed, "v4l2_loopback_setup")
    return _inject.setup_v4l2_loopback(req.device_num, req.label)

@router.post("/inject/video/stream")
async def inject_video_stream(req: InjectStreamReq):
    _req_auth(req.authorization_confirmed, "inject_video_stream")
    return _inject.inject_video_stream(req.source, req.target_device, req.fps, req.loop)

@router.post("/inject/audio/pulse")
async def inject_audio_pulse(req: InjectAudioReq):
    _req_auth(req.authorization_confirmed, "inject_audio_pulse")
    return _inject.inject_audio_pulse(req.audio_source, req.sink_name)

@router.post("/inject/call/start")
async def inject_call_start(req: CallInjectReq):
    _req_auth(req.authorization_confirmed, "inject_call_start")
    return _inject.start_call_injection(req.target_app, req.video_source, req.audio_source, req.face_swap_active, req.lipsync_active)

@router.post("/inject/rtsp/hijack")
async def inject_rtsp_hijack(req: RTSPHijackReq):
    _req_auth(req.authorization_confirmed, "rtsp_hijack")
    return _inject.rtsp_hijack(req.rtsp_url, req.replacement_video, req.mitm_mode)


# ── Detection Evasion ──────────────────────────────────────────────────────────

class AnalyzeDetectReq(AuthReq):
    video_path: str
    detectors:  Optional[List[str]] = None

class ApplyBypassReq(AuthReq):
    video_path:       str   = "deepfake.mp4"
    technique:        str   = "adversarial_perturbation"
    target_detector:  str   = "faceforensics"
    intensity:        float = 1.0

class FullBypassReq(AuthReq):
    video_path:         str = "deepfake.mp4"
    target_detectors:   Optional[List[str]] = None


@router.get("/evasion/detectors")
async def evasion_detectors():
    return _evade.list_detectors()

@router.get("/evasion/techniques")
async def evasion_techniques():
    return _evade.list_bypass_techniques()

@router.post("/evasion/analyze")
async def evasion_analyze(req: AnalyzeDetectReq):
    _req_auth(req.authorization_confirmed, "analyze_detectability")
    return _evade.analyze_detectability(req.video_path, req.detectors)

@router.post("/evasion/bypass/apply")
async def evasion_bypass_apply(req: ApplyBypassReq):
    _req_auth(req.authorization_confirmed, "apply_bypass")
    return _evade.apply_bypass(req.video_path, req.technique, req.target_detector, req.intensity)

@router.post("/evasion/bypass/full-pipeline")
async def evasion_full_pipeline(req: FullBypassReq):
    _req_auth(req.authorization_confirmed, "full_bypass_pipeline")
    return _evade.full_bypass_pipeline(req.video_path, req.target_detectors)
