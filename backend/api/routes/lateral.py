"""
Routes /api/lateral — Lateral movement, pivoting, and Active Directory attacks.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.agents.lateral_agent import LateralAgent

router = APIRouter()
_agent = LateralAgent()


# ── Request models ────────────────────────────────────────────────────────────

class SocksProxyRequest(BaseModel):
    target_ip: str
    port: int = 1080
    method: str = "chisel"  # chisel | ssh | ligolo
    ssh_creds: Optional[dict] = None  # {username, password, key_path}


class DiscoverNetworkRequest(BaseModel):
    pivot_host: str
    subnet: str  # e.g. "192.168.1.0/24"


class PassTheHashRequest(BaseModel):
    target: str
    username: str
    ntlm_hash: str


class KerberoastRequest(BaseModel):
    domain: str
    dc_ip: str
    username: str
    password: str


class AsreproastRequest(BaseModel):
    domain: str
    dc_ip: str
    userlist: Optional[str] = None


class DcsyncRequest(BaseModel):
    domain: str
    dc_ip: str
    username: str
    password: str
    target_user: str = "Administrator"


class BloodhoundRequest(BaseModel):
    domain: str
    dc_ip: str
    username: str
    password: str


class GoldenTicketRequest(BaseModel):
    domain: str
    domain_sid: str
    krbtgt_hash: str


class SmbSharesRequest(BaseModel):
    target: str
    credentials: Optional[dict] = None  # {username, password, ntlm_hash, null_session}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/socks")
async def setup_socks_proxy(req: SocksProxyRequest):
    """Setup SOCKS5 proxy via chisel, ligolo-ng, or SSH tunneling."""
    if req.port < 1 or req.port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port number")

    result = await _agent.setup_socks_proxy(
        target_ip=req.target_ip,
        port=req.port,
        method=req.method,
        ssh_creds=req.ssh_creds,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/discover")
async def discover_network(req: DiscoverNetworkRequest):
    """Discover internal network via SOCKS proxy + nmap."""
    result = await _agent.discover_internal_network(
        pivot_host=req.pivot_host,
        subnet=req.subnet,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/pth")
async def pass_the_hash(req: PassTheHashRequest):
    """Pass-the-Hash attack via crackmapexec/netexec."""
    if len(req.ntlm_hash) not in (32, 65) and ":" not in req.ntlm_hash:
        raise HTTPException(status_code=400, detail="ntlm_hash must be a valid NT hash (32 hex chars) or LM:NT format")

    result = await _agent.pass_the_hash(
        target=req.target,
        username=req.username,
        ntlm_hash=req.ntlm_hash,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/kerberoast")
async def kerberoast(req: KerberoastRequest):
    """Kerberoasting — request service tickets and crack offline."""
    result = await _agent.kerberoast(
        domain=req.domain,
        dc_ip=req.dc_ip,
        username=req.username,
        password=req.password,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/asreproast")
async def asreproast(req: AsreproastRequest):
    """AS-REP Roasting — attack accounts with pre-auth disabled."""
    result = await _agent.asreproast(
        domain=req.domain,
        dc_ip=req.dc_ip,
        userlist=req.userlist,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/dcsync")
async def dcsync(req: DcsyncRequest):
    """DCSync attack — dump hashes via domain replication."""
    result = await _agent.dcsync(
        domain=req.domain,
        dc_ip=req.dc_ip,
        username=req.username,
        password=req.password,
        target_user=req.target_user,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/bloodhound")
async def bloodhound_collect(req: BloodhoundRequest):
    """Run BloodHound collector against a domain."""
    result = await _agent.bloodhound_collect(
        domain=req.domain,
        dc_ip=req.dc_ip,
        username=req.username,
        password=req.password,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/golden-ticket")
async def golden_ticket(req: GoldenTicketRequest):
    """Generate a Kerberos golden ticket."""
    result = await _agent.golden_ticket(
        domain=req.domain,
        domain_sid=req.domain_sid,
        krbtgt_hash=req.krbtgt_hash,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/smb-shares")
async def smb_shares(req: SmbSharesRequest):
    """Enumerate SMB shares on target."""
    result = await _agent.smb_shares_enum(
        target=req.target,
        credentials=req.credentials,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.get("/history")
async def get_history(limit: int = Query(50, ge=1, le=500)):
    """Get lateral movement operation history."""
    ops = await _agent.get_history(limit=limit)
    return {"operations": ops, "count": len(ops)}
