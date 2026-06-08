"""Routes Mobile — Android & iOS enumeration / exploitation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.routes.auth import get_current_user
from services.mobile.mobile_service import mobile_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ADBRequest(BaseModel):
    serial: str
    authorization_confirmed: bool = False


class ADBFileRequest(BaseModel):
    serial: str
    remote_path: str
    authorization_confirmed: bool = False


class ADBShellRequest(BaseModel):
    serial: str
    command: str
    authorization_confirmed: bool = False


class AndroidRATRequest(BaseModel):
    lhost: str
    lport: int
    app_name: str = "Calculator"
    authorization_confirmed: bool = False


class FridaRequest(BaseModel):
    device_serial: str
    package: str
    script_type: str = "ssl_bypass"
    authorization_confirmed: bool = False


class PhishingRequest(BaseModel):
    target_app: str
    lhost: str
    lport: int
    authorization_confirmed: bool = False


class APKRequest(BaseModel):
    apk_path: str
    authorization_confirmed: bool = False


class IPARequest(BaseModel):
    ipa_path: str
    authorization_confirmed: bool = False


class iOSBackupRequest(BaseModel):
    device_id: str = ""
    authorization_confirmed: bool = False


# ── Guard ─────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/android/devices")
async def list_devices(authorization_confirmed: bool = False, current_user=Depends(get_current_user)):
    _require_auth(authorization_confirmed, "Liste appareils ADB")
    return await mobile_service.list_adb_devices()


@router.post("/android/enumerate")
async def enumerate_device(req: ADBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération device Android")
    return await mobile_service.adb_enumerate_device(req.serial)


@router.post("/android/sms")
async def dump_sms(req: ADBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Extraction SMS")
    messages = await mobile_service.adb_dump_sms(req.serial)
    return {"messages": messages, "count": len(messages)}


@router.post("/android/pull")
async def pull_file(req: ADBFileRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Pull fichier ADB")
    local_path = await mobile_service.adb_pull_file(req.serial, req.remote_path)
    return {"local_path": local_path, "remote_path": req.remote_path}


@router.post("/android/shell")
async def adb_shell(req: ADBShellRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Shell ADB")
    output = await mobile_service.adb_shell_command(req.serial, req.command)
    return {"output": output, "command": req.command}


@router.post("/android/rat/generate")
async def generate_rat(req: AndroidRATRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération Android RAT")
    return await mobile_service.generate_android_rat(req.lhost, req.lport, req.app_name)


@router.post("/android/apk/analyze")
async def analyze_apk(req: APKRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Analyse APK")
    return await mobile_service.analyze_apk(req.apk_path)


@router.post("/android/frida")
async def frida_hook(req: FridaRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Frida Hook")
    return await mobile_service.frida_hook(req.device_serial, req.package, req.script_type)


@router.post("/android/phishing")
async def create_phishing(req: PhishingRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Création page phishing mobile")
    return await mobile_service.create_phishing_page(req.target_app, req.lhost, req.lport)


@router.post("/ios/backup")
async def ios_backup(req: iOSBackupRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Extraction backup iOS")
    return await mobile_service.extract_ios_backup(req.device_id)


@router.post("/ios/ipa/analyze")
async def analyze_ipa(req: IPARequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Analyse IPA")
    return await mobile_service.analyze_ipa(req.ipa_path)
