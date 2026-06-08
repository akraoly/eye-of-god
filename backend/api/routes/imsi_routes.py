from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.radio.imsi_catcher_service import imsi_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class StartBTSReq(AuthReq):
    band: str = "900"
    operator_mcc: str = "208"
    operator_mnc: str = "01"


class StopBTSReq(AuthReq):
    bts_id: str


class SMSCaptureReq(AuthReq):
    bts_id: str
    target_imsi: str
    duration: int = 60


class SMSInjectReq(AuthReq):
    bts_id: str
    target_imsi: str
    message: str
    spoof_from: Optional[str] = None


class CallMetaReq(AuthReq):
    bts_id: str
    target_imsi: str
    duration: int = 120


class LocateReq(AuthReq):
    target_imsi: str
    bts_id: str


@router.get("/hardware")
async def check_hardware():
    return await imsi_service.check_hardware()


@router.get("/sessions")
async def get_sessions():
    return await imsi_service.get_sessions()


@router.post("/bts/start")
async def start_bts(req: StartBTSReq):
    _req_auth(req.authorization_confirmed, "start_fake_bts")
    return await imsi_service.start_fake_bts(req.band, req.operator_mcc, req.operator_mnc)


@router.post("/bts/stop")
async def stop_bts(req: StopBTSReq):
    _req_auth(req.authorization_confirmed, "stop_fake_bts")
    return await imsi_service.stop_fake_bts(req.bts_id)


@router.get("/phones/{bts_id}")
async def get_phones(bts_id: str):
    return await imsi_service.get_connected_phones(bts_id)


@router.post("/sms/capture")
async def capture_sms(req: SMSCaptureReq):
    _req_auth(req.authorization_confirmed, "capture_sms")
    return await imsi_service.capture_sms(req.bts_id, req.target_imsi, req.duration)


@router.post("/sms/inject")
async def inject_sms(req: SMSInjectReq):
    _req_auth(req.authorization_confirmed, "inject_sms")
    return await imsi_service.inject_sms(req.bts_id, req.target_imsi, req.message, req.spoof_from)


@router.post("/calls/metadata")
async def call_metadata(req: CallMetaReq):
    _req_auth(req.authorization_confirmed, "call_metadata")
    return await imsi_service.capture_call_metadata(req.bts_id, req.target_imsi, req.duration)


@router.post("/locate")
async def locate_phone(req: LocateReq):
    _req_auth(req.authorization_confirmed, "locate_phone")
    return await imsi_service.locate_phone(req.target_imsi, req.bts_id)


@router.post("/stingray/detect")
async def detect_stingray(req: AuthReq):
    _req_auth(req.authorization_confirmed, "detect_stingray")
    return await imsi_service.detect_stingray()
