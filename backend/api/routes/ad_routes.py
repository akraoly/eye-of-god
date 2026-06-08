"""Routes Active Directory — Pentest / Red Team."""
from __future__ import annotations

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List

from api.routes.auth import get_current_user
from services.ad.ad_attack_service import ad_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ADCredentials(BaseModel):
    dc_ip: str
    domain: str
    username: str
    password: str
    authorization_confirmed: bool = False


class ADDetectRequest(BaseModel):
    target_ip: str
    authorization_confirmed: bool = False


class PTHRequest(BaseModel):
    target_ip: str
    username: str
    domain: str
    ntlm_hash: str
    command: str = "whoami"
    authorization_confirmed: bool = False


class GoldenTicketRequest(BaseModel):
    domain: str
    dc_ip: str
    krbtgt_hash: str
    target_user: str = "Administrator"
    authorization_confirmed: bool = False


class SilverTicketRequest(BaseModel):
    domain: str
    dc_ip: str
    target_service: str
    service_hash: str
    target_user: str = "Administrator"
    authorization_confirmed: bool = False


class DCSyncRequest(BaseModel):
    dc_ip: str
    domain: str
    username: str
    password: str
    target_user: str = "krbtgt"
    authorization_confirmed: bool = False


class ESC1Request(BaseModel):
    dc_ip: str
    domain: str
    ca_name: str
    target_user: str
    authorization_confirmed: bool = False


class SMBRequest(BaseModel):
    target_ip: str
    username: Optional[str] = ""
    password: Optional[str] = ""
    authorization_confirmed: bool = False


class SMBFileRequest(BaseModel):
    target_ip: str
    share: str
    file_path: str
    username: str
    password: str
    authorization_confirmed: bool = False


class BloodHoundAnalyzeRequest(BaseModel):
    zip_path: str
    authorization_confirmed: bool = False


# ── Guard ────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        from fastapi import HTTPException
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true (pentest autorisé explicite)")


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/detect")
async def detect_dc(req: ADDetectRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Détection DC")
    return await ad_service.detect_domain_controller(req.target_ip)


@router.post("/enumerate/users")
async def enumerate_users(req: ADCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération utilisateurs AD")
    users = await ad_service.enumerate_users_ldap(req.dc_ip, req.domain, req.username, req.password)
    return {"users": users, "count": len(users), "domain": req.domain}


@router.post("/enumerate/shares")
async def enumerate_shares(req: SMBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération SMB")
    shares = await ad_service.enumerate_smb_shares(req.target_ip, req.username, req.password)
    return {"shares": shares, "count": len(shares), "target": req.target_ip}


@router.post("/smb/read-file")
async def read_smb_file(req: SMBFileRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Lecture fichier SMB")
    content = await ad_service.read_smb_file(req.target_ip, req.share, req.file_path, req.username, req.password)
    return {"content": content, "path": f"\\\\{req.target_ip}\\{req.share}\\{req.file_path}"}


@router.post("/enumerate/gpo")
async def enumerate_gpo(req: ADCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération GPO")
    gpos = await ad_service.enumerate_gpo(req.dc_ip, req.domain, req.username, req.password)
    return {"gpos": gpos, "count": len(gpos)}


@router.post("/kerberoast")
async def kerberoast(req: ADCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Kerberoasting")
    tickets = await ad_service.kerberoast(req.dc_ip, req.domain, req.username, req.password)
    return {"tickets": tickets, "count": len(tickets), "crack_hint": "hashcat -m 13100 hash.txt rockyou.txt"}


@router.post("/asrep-roast")
async def asrep_roast(req: ADDetectRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "AS-REP Roasting")
    hashes = await ad_service.asrep_roast(req.target_ip, "corp.local")
    return {"hashes": hashes, "count": len(hashes), "crack_hint": "hashcat -m 18200 hash.txt rockyou.txt"}


@router.post("/dcsync")
async def dcsync(req: DCSyncRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "DCSync")
    result = await ad_service.dcsync(req.dc_ip, req.domain, req.username, req.password, req.target_user)
    return result


@router.post("/golden-ticket")
async def golden_ticket(req: GoldenTicketRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Golden Ticket")
    ticket_path = await ad_service.golden_ticket(req.domain, req.dc_ip, req.krbtgt_hash, req.target_user)
    return {"ticket_path": ticket_path, "target_user": req.target_user, "domain": req.domain}


@router.post("/silver-ticket")
async def silver_ticket(req: SilverTicketRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Silver Ticket")
    ticket_path = await ad_service.silver_ticket(req.domain, req.dc_ip, req.target_service, req.service_hash, req.target_user)
    return {"ticket_path": ticket_path, "target_service": req.target_service}


@router.post("/adcs/enumerate")
async def adcs_enumerate(req: ADCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération AD CS")
    result = await ad_service.enumerate_adcs(req.dc_ip, req.domain, req.username, req.password)
    return result


@router.post("/adcs/esc1-exploit")
async def adcs_esc1(req: ESC1Request, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "ESC1 Exploit")
    result = await ad_service.esc1_exploit(req.dc_ip, req.domain, req.ca_name, req.target_user)
    return result


@router.post("/bloodhound/ingest")
async def bloodhound_ingest(req: ADCredentials, background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "BloodHound Ingest")
    zip_path = await ad_service.bloodhound_ingest(req.dc_ip, req.domain, req.username, req.password)
    return {"zip_path": zip_path, "status": "completed"}


@router.post("/bloodhound/analyze")
async def bloodhound_analyze(req: BloodHoundAnalyzeRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "BloodHound Analyze")
    return await ad_service.bloodhound_analyze(req.zip_path)


@router.post("/pass-the-hash")
async def pass_the_hash(req: PTHRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Pass-the-Hash")
    return await ad_service.pass_the_hash(req.target_ip, req.username, req.domain, req.ntlm_hash, req.command)


@router.get("/domain/sid")
async def get_domain_sid(dc_ip: str, domain: str, username: str, password: str, authorization_confirmed: bool = False, current_user=Depends(get_current_user)):
    _require_auth(authorization_confirmed, "Récupération Domain SID")
    sid = await ad_service.get_domain_sid(dc_ip, domain, username, password)
    return {"domain_sid": sid, "domain": domain}


@router.post("/defender/check")
async def check_defender(req: ADCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Vérification Defender")
    return await ad_service.check_defender_status(req.dc_ip, req.username, req.password, req.domain)
