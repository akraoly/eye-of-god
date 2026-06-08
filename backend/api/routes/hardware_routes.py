"""Routes Hardware Implants — BadUSB / Rubber Ducky / Bash Bunny / O.MG / PoisonTap / Lan Turtle."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from api.routes.auth import get_current_user
from services.hardware.hardware_implant_service import hardware_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ImplantBase(BaseModel):
    lhost: str
    lport: int
    target: str = "target"
    authorization_confirmed: bool = False


class DuckyRequest(ImplantBase):
    payload_type: str = "credentials_exfil"
    os_target: str = "windows"


class BashBunnyRequest(ImplantBase):
    attack_mode: str = "HID_STORAGE"


class LanTurtleRequest(ImplantBase):
    modules: List[str] = ["autossh", "responder"]


class BadUSBRequest(ImplantBase):
    target_os: str = "windows"
    payload_type: str = "reverse_shell"


# ── Guard ─────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/rubber-ducky/generate")
async def rubber_ducky(req: DuckyRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération Rubber Ducky payload")
    return await hardware_service.generate_rubber_ducky_payload(req.lhost, req.lport, req.payload_type, req.target, req.os_target)


@router.post("/bash-bunny/generate")
async def bash_bunny(req: BashBunnyRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération Bash Bunny payload")
    return await hardware_service.generate_bash_bunny_payload(req.lhost, req.lport, req.attack_mode, req.target)


@router.post("/omg-cable/generate")
async def omg_cable(req: ImplantBase, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération O.MG Cable payload")
    return await hardware_service.generate_omg_cable_payload(req.lhost, req.lport, req.target)


@router.post("/poisontap/generate")
async def poisontap(req: ImplantBase, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération PoisonTap payload")
    return await hardware_service.generate_poisontap_payload(req.lhost, req.lport, req.target)


@router.post("/lan-turtle/configure")
async def lan_turtle(req: LanTurtleRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Configuration Lan Turtle")
    return await hardware_service.generate_lan_turtle_config(req.lhost, req.lport, req.modules)


@router.post("/badusb/generate")
async def badusb(req: BadUSBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération BadUSB payload")
    return await hardware_service.generate_badusb_payload(req.lhost, req.lport, req.target_os, req.payload_type)


@router.get("/payloads/list")
async def list_payloads(current_user=Depends(get_current_user)):
    payloads = await hardware_service.list_generated_payloads()
    return {"payloads": payloads, "count": len(payloads)}
