from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.anonymization.anonymizer_service import anonymizer_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class TorReq(AuthReq):
    country: Optional[str] = None


class VPNReq(AuthReq):
    config_path: str
    username: Optional[str] = None
    password: Optional[str] = None


class MACReq(AuthReq):
    interface: str = "eth0"
    mac_address: Optional[str] = None


class ProxyReq(AuthReq):
    proxies: List[str]
    protocol: str = "socks5"


class DNSReq(AuthReq):
    provider: str = "cloudflare"


class UAReq(AuthReq):
    agent: Optional[str] = None


@router.get("/status")
async def get_status():
    return await anonymizer_service.get_anonymity_status()


@router.get("/score")
async def get_score():
    status = await anonymizer_service.get_anonymity_status()
    return {"score": status.get("anonymity_score", 0), "grade": status.get("grade", "F"), "active_layers": status.get("active_layers", [])}


@router.post("/tor/start")
async def start_tor(req: TorReq):
    _req_auth(req.authorization_confirmed, "start_tor")
    return await anonymizer_service.start_tor(req.country)


@router.post("/tor/stop")
async def stop_tor(req: AuthReq):
    _req_auth(req.authorization_confirmed, "stop_tor")
    return await anonymizer_service.stop_tor()


@router.post("/tor/new_identity")
async def new_tor_identity(req: AuthReq):
    _req_auth(req.authorization_confirmed, "new_tor_identity")
    return await anonymizer_service.new_tor_identity()


@router.post("/vpn/start")
async def start_vpn(req: VPNReq):
    _req_auth(req.authorization_confirmed, "start_vpn")
    return await anonymizer_service.start_vpn(req.config_path, req.username, req.password)


@router.post("/vpn/stop")
async def stop_vpn(req: AuthReq):
    _req_auth(req.authorization_confirmed, "stop_vpn")
    return await anonymizer_service.stop_vpn()


@router.post("/mac/spoof")
async def spoof_mac(req: MACReq):
    _req_auth(req.authorization_confirmed, "spoof_mac")
    return await anonymizer_service.spoof_mac(req.interface, req.mac_address)


@router.post("/proxy/configure")
async def configure_proxy(req: ProxyReq):
    _req_auth(req.authorization_confirmed, "configure_proxies")
    return await anonymizer_service.configure_proxy_chain(req.proxies, req.protocol)


@router.post("/dns/doh")
async def configure_doh(req: DNSReq):
    _req_auth(req.authorization_confirmed, "configure_doh")
    return await anonymizer_service.configure_dns_over_https(req.provider)


@router.post("/useragent/rotate")
async def rotate_ua(req: UAReq):
    _req_auth(req.authorization_confirmed, "rotate_useragent")
    return await anonymizer_service.rotate_user_agent(req.agent)


@router.post("/leak/check")
async def check_leaks(req: AuthReq):
    _req_auth(req.authorization_confirmed, "check_ip_leak")
    return await anonymizer_service.check_ip_leak()


@router.post("/activate/all")
async def activate_all(req: AuthReq):
    _req_auth(req.authorization_confirmed, "activate_all_layers")
    return await anonymizer_service.activate_all_layers()


@router.post("/deactivate/all")
async def deactivate_all(req: AuthReq):
    _req_auth(req.authorization_confirmed, "deactivate_all_layers")
    return await anonymizer_service.deactivate_all_layers()
