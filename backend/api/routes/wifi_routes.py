"""
Routes /api/wifi — Scanner, Cracking, Post-Exploit, Automation, Agent.
30+ routes couvrant toutes les capacités WiFi.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models_wifi import (
    WifiNetwork, WifiClient, WifiScan,
    WifiHandshake, WifiCrackJob, WifiConnection,
)
from services.wifi.wifi_scanner_service import WiFiScannerService
from services.wifi.wifi_crack_service import WiFiCrackService
from services.wifi.wifi_automation_service import WiFiAutomationService

logger = logging.getLogger(__name__)
router = APIRouter()

_scanner    = WiFiScannerService()
_cracker    = WiFiCrackService()
_automation = WiFiAutomationService()

# ── Pydantic models ───────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    interface: str = "wlan0"
    duration: int = 30
    channels: Optional[List[int]] = None

class MonitorRequest(BaseModel):
    interface: str = "wlan0"

class ChannelRequest(BaseModel):
    interface: str = "wlan0"
    channel: int

class HopRequest(BaseModel):
    interface: str = "wlan0"
    channels: List[int] = list(range(1, 14))
    dwell: float = 0.5

class HandshakeRequest(BaseModel):
    interface: str = "wlan0"
    bssid: str
    ssid: str
    channel: int = 6
    timeout: int = 60
    client_mac: Optional[str] = None

class PMKIDRequest(BaseModel):
    interface: str = "wlan0"
    bssid: str
    ssid: str
    timeout: int = 30

class CrackRequest(BaseModel):
    bssid: str
    ssid: str
    hs_id: Optional[str] = None
    hash_str: Optional[str] = None
    wordlist: Optional[str] = None

class WPSRequest(BaseModel):
    interface: str = "wlan0"
    bssid: str
    channel: int = 6

class ConnectRequest(BaseModel):
    ssid: str
    passphrase: str
    interface: str = "wlan0"

class EvilTwinRequest(BaseModel):
    interface: str = "wlan0"
    ssid: str
    bssid_victim: str
    channel: int = 6
    deauth: bool = True

class HostScanRequest(BaseModel):
    ip: str

class SMBRequest(BaseModel):
    ip: str

class AutomationRequest(BaseModel):
    interface: str = "wlan0"
    target_bssid: Optional[str] = None
    scan_duration: int = 30
    wordlist: Optional[str] = None

class AgentRequest(BaseModel):
    message: str
    history: Optional[List[Dict]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INTERFACES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/interfaces")
def get_interfaces(db: Session = Depends(get_db)):
    """Lister les interfaces WiFi disponibles."""
    return {"interfaces": _scanner.get_interfaces()}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SCAN
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/scan")
async def start_scan(req: ScanRequest, db: Session = Depends(get_db)):
    """Scanner les réseaux WiFi environnants."""
    scan = WifiScan(
        interface=req.interface,
        duration=req.duration,
        channels=req.channels or [],
        status="running",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    result = await _scanner.scan(req.interface, req.duration, req.channels)

    # Persister les réseaux découverts
    networks = result.get("networks", [])
    clients = result.get("clients", [])

    for net in networks:
        existing = db.query(WifiNetwork).filter(WifiNetwork.bssid == net["bssid"]).first()
        if existing:
            existing.ssid = net.get("ssid") or existing.ssid
            existing.signal = net.get("signal", existing.signal)
            existing.channel = net.get("channel", existing.channel)
            existing.last_seen = datetime.utcnow()
            existing.wps_enabled = net.get("wps_enabled", existing.wps_enabled)
        else:
            row = WifiNetwork(
                bssid=net["bssid"],
                ssid=net.get("ssid", ""),
                hidden=net.get("hidden", False),
                channel=net.get("channel"),
                frequency=net.get("frequency"),
                signal=net.get("signal", -70),
                quality=net.get("quality", 0),
                encryption=net.get("encryption", "WPA2"),
                cipher=net.get("cipher"),
                auth=net.get("auth"),
                wps_enabled=net.get("wps_enabled", False),
                vendor=net.get("vendor"),
                beacon_count=net.get("beacon_count", 0),
                data_count=net.get("data_count", 0),
                simulated=net.get("simulated", False),
                scan_id=scan.scan_id,
            )
            db.add(row)

    for cli in clients:
        existing = db.query(WifiClient).filter(WifiClient.mac == cli["mac"]).first()
        if not existing:
            row = WifiClient(
                mac=cli["mac"],
                bssid=cli.get("bssid"),
                ssid=cli.get("ssid"),
                signal=cli.get("signal", -70),
                probed_ssids=cli.get("probed_ssids", []),
                vendor=cli.get("vendor"),
            )
            db.add(row)

    scan.status = "done"
    scan.networks_found = len(networks)
    scan.clients_found = len(clients)
    scan.finished_at = datetime.utcnow()
    db.commit()

    return {**result, "scan_db_id": scan.scan_id}


@router.get("/networks")
def get_networks(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Retourner tous les réseaux scannés."""
    rows = db.query(WifiNetwork).order_by(WifiNetwork.last_seen.desc()).limit(limit).all()
    return {"networks": [_net_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/network/{bssid}")
def get_network(bssid: str, db: Session = Depends(get_db)):
    """Détails d'un AP par BSSID."""
    row = db.query(WifiNetwork).filter(WifiNetwork.bssid == bssid.upper()).first()
    if not row:
        raise HTTPException(404, "Réseau non trouvé")
    fp = _scanner.fingerprint_ap(row.bssid, row.ssid or "", row.vendor or "")
    return {**_net_to_dict(row), "fingerprint": fp}


@router.get("/clients")
def get_clients(db: Session = Depends(get_db)):
    """Retourner tous les clients WiFi détectés."""
    rows = db.query(WifiClient).order_by(WifiClient.last_seen.desc()).limit(100).all()
    return {"clients": [_cli_to_dict(r) for r in rows]}


@router.get("/scans")
def get_scans(db: Session = Depends(get_db)):
    """Historique des sessions de scan."""
    rows = db.query(WifiScan).order_by(WifiScan.started_at.desc()).limit(20).all()
    return {"scans": [_scan_to_dict(r) for r in rows]}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MONITOR MODE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/monitor/start")
def start_monitor(req: MonitorRequest):
    """Activer le monitor mode sur l'interface."""
    result = _scanner.start_monitor(req.interface)
    return result


@router.post("/monitor/stop")
def stop_monitor(req: MonitorRequest):
    """Désactiver le monitor mode."""
    result = _scanner.stop_monitor(req.interface)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHANNEL
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/channel/set")
def set_channel(req: ChannelRequest):
    """Changer de canal sur l'interface."""
    return _scanner.set_channel(req.interface, req.channel)


@router.post("/channel/hop")
async def start_hopping(req: HopRequest):
    """Activer le channel hopping (scan automatique des canaux)."""
    return {
        "status": "hopping",
        "interface": req.interface,
        "channels": req.channels,
        "dwell": req.dwell,
        "note": "Channel hopping actif — arrêter avec monitor/stop",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 5. WPS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/wps/detect")
def detect_wps(bssid: str = Query(...), interface: str = Query("wlan0")):
    """Détecter la présence et le statut WPS d'un AP."""
    return _scanner.detect_wps(interface, bssid)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CRACKING
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/crack/handshake")
async def capture_handshake(req: HandshakeRequest, db: Session = Depends(get_db)):
    """Capturer le 4-way handshake via deauth + airodump-ng."""
    result = await _cracker.capture_handshake(
        req.interface, req.bssid, req.ssid,
        channel=req.channel, timeout=req.timeout,
        client_mac=req.client_mac,
    )
    # Persister
    row = WifiHandshake(
        bssid=req.bssid, ssid=req.ssid,
        capture_type="handshake",
        cap_file=result.get("cap_file"),
        hccapx_file=result.get("hccapx_file"),
        status=result.get("status", "captured"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**result, "hs_id": row.hs_id}


@router.post("/crack/pmkid")
async def capture_pmkid(req: PMKIDRequest, db: Session = Depends(get_db)):
    """Capturer le PMKID (pas besoin de client connecté)."""
    result = await _cracker.capture_pmkid(req.interface, req.bssid, req.ssid, req.timeout)
    row = WifiHandshake(
        bssid=req.bssid, ssid=req.ssid,
        capture_type="pmkid",
        cap_file=result.get("cap_file"),
        status=result.get("status", "captured"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**result, "hs_id": row.hs_id}


@router.post("/crack/start")
async def start_crack(req: CrackRequest, db: Session = Depends(get_db)):
    """Lancer le cracking hashcat sur un handshake capturé."""
    # Récupérer le fichier hccapx depuis la DB si hs_id fourni
    hccapx_file = None
    if req.hs_id:
        hs = db.query(WifiHandshake).filter(WifiHandshake.hs_id == req.hs_id).first()
        if hs:
            hccapx_file = hs.hccapx_file

    job = WifiCrackJob(
        bssid=req.bssid, ssid=req.ssid, hs_id=req.hs_id,
        method="dictionary", wordlist=req.wordlist,
        status="running", started_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    result = await _cracker.crack_hashcat(
        req.bssid, req.ssid,
        hccapx_file=hccapx_file,
        hash_str=req.hash_str,
        wordlist=req.wordlist,
    )

    job.status = result.get("status", "failed")
    job.result = result.get("passphrase")
    job.finished_at = datetime.utcnow()
    db.commit()

    return {**result, "job_id": job.job_id}


@router.get("/crack/status")
def crack_status(job_id: str = Query(...), db: Session = Depends(get_db)):
    """Statut d'un job de cracking."""
    job = db.query(WifiCrackJob).filter(WifiCrackJob.job_id == job_id).first()
    if not job:
        raise HTTPException(404, "Job non trouvé")
    return _job_to_dict(job)


@router.get("/crack/jobs")
def list_crack_jobs(db: Session = Depends(get_db)):
    """Lister tous les jobs de cracking."""
    jobs = db.query(WifiCrackJob).order_by(WifiCrackJob.created_at.desc()).limit(50).all()
    return {"jobs": [_job_to_dict(j) for j in jobs]}


@router.post("/wps/attack")
async def wps_attack(req: WPSRequest, db: Session = Depends(get_db)):
    """Attaque WPS Pixie Dust."""
    result = await _cracker.wps_pixiedust(req.interface, req.bssid, req.channel)

    job = WifiCrackJob(
        bssid=req.bssid, method="wps_pixiedust",
        status=result.get("status", "failed"),
        result=result.get("passphrase"),
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    return {**result, "job_id": job.job_id}


@router.get("/handshakes")
def list_handshakes(db: Session = Depends(get_db)):
    """Lister les handshakes capturés."""
    rows = db.query(WifiHandshake).order_by(WifiHandshake.captured_at.desc()).limit(50).all()
    return {"handshakes": [_hs_to_dict(r) for r in rows]}


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CONNEXION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/connect")
def connect_wifi(req: ConnectRequest, db: Session = Depends(get_db)):
    """Se connecter à un réseau WiFi."""
    result = _cracker.connect(req.ssid, req.passphrase, req.interface)
    row = WifiConnection(
        bssid=result.get("bssid", ""),
        ssid=req.ssid,
        passphrase=req.passphrase,
        interface=req.interface,
        local_ip=result.get("local_ip"),
        gateway=result.get("gateway"),
        dns=result.get("dns", []),
        status=result.get("status", "failed"),
        connected_at=datetime.utcnow() if result.get("status") == "connected" else None,
    )
    db.add(row)
    db.commit()
    return {**result, "conn_id": row.conn_id}


@router.get("/connection/status")
def connection_status(db: Session = Depends(get_db)):
    """Statut de la connexion WiFi active."""
    last = db.query(WifiConnection).order_by(WifiConnection.created_at.desc()).first()
    if not last:
        return {"status": "disconnected"}
    return _conn_to_dict(last)


@router.get("/connections")
def list_connections(db: Session = Depends(get_db)):
    """Historique des connexions."""
    rows = db.query(WifiConnection).order_by(WifiConnection.created_at.desc()).limit(20).all()
    return {"connections": [_conn_to_dict(r) for r in rows]}


# ═══════════════════════════════════════════════════════════════════════════════
# 8. EVIL TWIN
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/eviltwin/start")
async def start_evil_twin(req: EvilTwinRequest):
    """Démarrer un Evil Twin / Rogue AP."""
    result = await _cracker.start_evil_twin(
        req.interface, req.ssid, req.bssid_victim, req.channel, req.deauth
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 9. POST-EXPLOITATION RÉSEAU
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/connected/scan")
async def scan_connected_network(gateway: str = Query(...)):
    """Scanner les hôtes du réseau local une fois connecté."""
    return await _automation.scan_connected_network(gateway)


@router.get("/connected/hosts")
def get_connected_hosts(db: Session = Depends(get_db)):
    """Hôtes découverts sur le réseau connecté."""
    last = db.query(WifiConnection).filter(
        WifiConnection.status == "connected"
    ).order_by(WifiConnection.connected_at.desc()).first()
    if not last:
        return {"hosts": []}
    return {"hosts": last.hosts_found or []}


@router.post("/connected/host/{ip}/scan")
async def scan_host_ports(ip: str):
    """Scanner les ports ouverts d'un hôte."""
    return await _automation.scan_host_ports(ip)


@router.post("/connected/host/{ip}/smb")
async def enumerate_smb(ip: str):
    """Enumérer les partages SMB d'un hôte."""
    return await _automation.enumerate_smb(ip)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/automation/run")
async def run_automation(req: AutomationRequest):
    """Lancer le workflow automatisé complet."""
    result = await _automation.run_full_workflow(
        interface=req.interface,
        target_bssid=req.target_bssid,
        scan_duration=req.scan_duration,
        wordlist=req.wordlist,
    )
    return result


@router.get("/automation/status")
def automation_status():
    """Progression des workflows actifs."""
    return {"jobs": _automation.list_jobs()}


@router.post("/automation/target/{bssid}")
async def target_automation(bssid: str, interface: str = Query("wlan0")):
    """Lancer le workflow ciblé sur un BSSID spécifique."""
    result = await _automation.run_full_workflow(
        interface=interface,
        target_bssid=bssid,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 11. AGENT IA WiFi
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/agent")
async def wifi_agent_chat(req: AgentRequest):
    """Interagir avec l'agent IA WiFi (Claude + tools WiFi)."""
    try:
        import anthropic
        from app.config import settings
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        from core.agents.wifi_agent import run_wifi_agent
        result = await run_wifi_agent(
            user_message=req.message,
            llm_client=client,
            model=settings.CLAUDE_MODEL,
            conversation_history=req.history or [],
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Erreur agent WiFi : {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. FINGERPRINTING
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/fingerprint/{bssid}")
def fingerprint(bssid: str, db: Session = Depends(get_db)):
    """Fingerprint d'un AP (modèle, firmware, creds par défaut)."""
    net = db.query(WifiNetwork).filter(WifiNetwork.bssid == bssid.upper()).first()
    ssid = net.ssid or "" if net else ""
    vendor = net.vendor or "" if net else ""
    return _scanner.fingerprint_ap(bssid, ssid, vendor)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers serialisation
# ═══════════════════════════════════════════════════════════════════════════════

def _net_to_dict(r: WifiNetwork) -> Dict:
    return {
        "id": r.id, "wifi_id": r.wifi_id, "bssid": r.bssid, "ssid": r.ssid,
        "hidden": r.hidden, "channel": r.channel, "frequency": r.frequency,
        "signal": r.signal, "quality": r.quality, "encryption": r.encryption,
        "cipher": r.cipher, "auth": r.auth, "wps_enabled": r.wps_enabled,
        "wps_locked": r.wps_locked, "vendor": r.vendor,
        "beacon_count": r.beacon_count, "data_count": r.data_count,
        "clients": r.clients, "first_seen": str(r.first_seen),
        "last_seen": str(r.last_seen), "simulated": r.simulated,
    }

def _cli_to_dict(r: WifiClient) -> Dict:
    return {
        "id": r.id, "mac": r.mac, "bssid": r.bssid, "ssid": r.ssid,
        "signal": r.signal, "probed_ssids": r.probed_ssids, "vendor": r.vendor,
        "first_seen": str(r.first_seen), "last_seen": str(r.last_seen),
    }

def _scan_to_dict(r: WifiScan) -> Dict:
    return {
        "scan_id": r.scan_id, "interface": r.interface, "duration": r.duration,
        "channels": r.channels, "networks_found": r.networks_found,
        "clients_found": r.clients_found, "status": r.status,
        "started_at": str(r.started_at), "finished_at": str(r.finished_at) if r.finished_at else None,
    }

def _hs_to_dict(r: WifiHandshake) -> Dict:
    return {
        "hs_id": r.hs_id, "bssid": r.bssid, "ssid": r.ssid,
        "capture_type": r.capture_type, "cap_file": r.cap_file,
        "status": r.status, "passphrase": r.passphrase,
        "captured_at": str(r.captured_at),
        "cracked_at": str(r.cracked_at) if r.cracked_at else None,
    }

def _job_to_dict(r: WifiCrackJob) -> Dict:
    return {
        "job_id": r.job_id, "bssid": r.bssid, "ssid": r.ssid,
        "method": r.method, "wordlist": r.wordlist, "status": r.status,
        "progress": r.progress, "speed": r.speed, "result": r.result,
        "started_at": str(r.started_at) if r.started_at else None,
        "finished_at": str(r.finished_at) if r.finished_at else None,
    }

def _conn_to_dict(r: WifiConnection) -> Dict:
    return {
        "conn_id": r.conn_id, "bssid": r.bssid, "ssid": r.ssid,
        "interface": r.interface, "local_ip": r.local_ip, "gateway": r.gateway,
        "dns": r.dns, "status": r.status, "hosts_found": r.hosts_found,
        "connected_at": str(r.connected_at) if r.connected_at else None,
    }
