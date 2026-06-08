"""Routes Printer Exploitation — PJL, PrintNightmare, SNMP, Display Hijack."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.routes.auth import get_current_user
from services.network.printer_service import printer_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class NetworkScanRequest(BaseModel):
    network: str = "192.168.1.0/24"
    authorization_confirmed: bool = False


class PrinterTargetRequest(BaseModel):
    target_ip: str
    authorization_confirmed: bool = False


class PrinterAuthRequest(BaseModel):
    target_ip: str
    username: str = "admin"
    password: str = "admin"
    authorization_confirmed: bool = False


class PrintNightmareRequest(BaseModel):
    target_ip: str
    lhost: str
    lport: int
    username: str
    password: str
    domain: str = ""
    authorization_confirmed: bool = False


class SNMPRequest(BaseModel):
    target_ip: str
    community: str = "public"
    authorization_confirmed: bool = False


class DisplayHijackRequest(BaseModel):
    target_ip: str
    message: str
    authorization_confirmed: bool = False


class DownloadJobRequest(BaseModel):
    target_ip: str
    job_id: int
    authorization_confirmed: bool = False


class WebAdminRequest(BaseModel):
    target_ip: str
    port: int = 80
    authorization_confirmed: bool = False


class FTPRequest(BaseModel):
    target_ip: str
    username: str = "anonymous"
    password: str = "anonymous"
    authorization_confirmed: bool = False


# ── Guard ─────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/scan")
async def scan_printers(req: NetworkScanRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Scan imprimantes réseau")
    printers = await printer_service.scan_network_printers(req.network)
    return {"printers": printers, "count": len(printers), "network": req.network}


@router.post("/pjl/info")
async def pjl_info(req: PrinterTargetRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "PJL Info Dump")
    return await printer_service.get_pjl_info(req.target_ip)


@router.post("/jobs/list")
async def list_stored_jobs(req: PrinterAuthRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération jobs d'impression")
    jobs = await printer_service.get_stored_jobs(req.target_ip, req.username, req.password)
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/jobs/download")
async def download_job(req: DownloadJobRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Téléchargement job d'impression")
    local_path = await printer_service.download_stored_job(req.target_ip, req.job_id)
    return {"local_path": local_path, "job_id": req.job_id}


@router.post("/vulnerabilities/printnightmare/check")
async def check_print_nightmare(req: PrinterTargetRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Check PrintNightmare")
    return await printer_service.check_print_nightmare(req.target_ip)


@router.post("/vulnerabilities/printnightmare/exploit")
async def exploit_print_nightmare(req: PrintNightmareRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Exploit PrintNightmare")
    return await printer_service.exploit_print_nightmare(req.target_ip, req.lhost, req.lport, req.username, req.password, req.domain)


@router.post("/snmp/enumerate")
async def snmp_enum(req: SNMPRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "SNMP Printer Enumeration")
    return await printer_service.snmp_enum_printer(req.target_ip, req.community)


@router.post("/display/hijack")
async def display_hijack(req: DisplayHijackRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Display Hijack imprimante")
    return await printer_service.hijack_display(req.target_ip, req.message)


@router.post("/ftp/access")
async def ftp_access(req: FTPRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Accès FTP imprimante")
    return await printer_service.ftp_access_printer(req.target_ip, req.username, req.password)


@router.post("/web-admin/check")
async def web_admin(req: WebAdminRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Check Web Admin imprimante")
    return await printer_service.check_web_admin(req.target_ip, req.port)
