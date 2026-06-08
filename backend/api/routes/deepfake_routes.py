from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
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
