"""
Routes /api/capture — Network Packet Sniffer.

List interfaces, start/stop captures, analyze pcaps, extract credentials,
live packet streaming via WebSocket.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.engines.packet_capture import packet_capture_engine
from database.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic request models ───────────────────────────────────────────────────

class StartCaptureRequest(BaseModel):
    interface: str
    bpf_filter: str = ""
    max_packets: int = 10000
    capture_id: Optional[str] = None


# ── Interfaces ────────────────────────────────────────────────────────────────

@router.get("/interfaces")
async def list_interfaces():
    """
    List all available network interfaces.
    Parses 'ip link show' with /proc/net/dev fallback.
    """
    try:
        interfaces = await packet_capture_engine.get_interfaces()
        return {"success": True, "interfaces": interfaces, "count": len(interfaces)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Start / stop capture ──────────────────────────────────────────────────────

@router.post("/start")
async def start_capture(req: StartCaptureRequest, db: Session = Depends(get_db)):
    """
    Start a packet capture using tcpdump.
    Supports optional BPF filter expressions (e.g. 'port 80', 'host 192.168.1.1').
    Returns capture_id to reference the running session.
    """
    if not req.interface.strip():
        raise HTTPException(status_code=400, detail="interface cannot be empty")
    if req.max_packets < 1:
        raise HTTPException(status_code=400, detail="max_packets must be >= 1")

    result = await packet_capture_engine.start_capture(
        interface=req.interface.strip(),
        bpf_filter=req.bpf_filter.strip(),
        max_packets=req.max_packets,
        capture_id=req.capture_id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Capture failed to start"))

    return result


@router.post("/stop/{capture_id}")
async def stop_capture(capture_id: str, db: Session = Depends(get_db)):
    """
    Stop a running packet capture.
    Finalizes the pcap file and updates DB status.
    """
    result = await packet_capture_engine.stop_capture(capture_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Capture not found"))
    return result


# ── Analysis ──────────────────────────────────────────────────────────────────

@router.get("/{capture_id}/analyze")
async def analyze_capture(
    capture_id: str,
    type: str = Query(default="all", description="all | http | dns | smb | ftp | credentials"),
):
    """
    Analyze a pcap file using tshark.
    Specify ?type= to filter by protocol: http, dns, smb, ftp, credentials, all.
    """
    valid_types = ("all", "http", "dns", "smb", "ftp", "credentials")
    if type not in valid_types:
        raise HTTPException(status_code=400, detail=f"type must be one of: {', '.join(valid_types)}")

    result = await packet_capture_engine.analyze_capture(capture_id, analysis_type=type)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Analysis failed"))
    return result


@router.get("/{capture_id}/credentials")
async def extract_credentials(capture_id: str):
    """
    Extract plaintext credentials from a pcap file.
    Searches for HTTP Basic Auth, FTP USER/PASS, SMTP AUTH, POP3, Telnet login prompts.
    """
    creds = await packet_capture_engine.extract_credentials(capture_id)
    return {
        "success": True,
        "capture_id": capture_id,
        "credentials": creds,
        "count": len(creds),
    }


@router.get("/{capture_id}/search")
async def search_packets(
    capture_id: str,
    q: str = Query(..., description="String to search in packet payloads"),
):
    """
    Search packets by string content in payload.
    Uses tshark 'frame contains' display filter.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="q cannot be empty")

    results = await packet_capture_engine.search_packets(capture_id, q.strip())
    return {
        "success": True,
        "capture_id": capture_id,
        "query": q,
        "matches": results,
        "count": len(results),
    }


@router.get("/{capture_id}/stats")
async def get_capture_stats(capture_id: str):
    """
    Get live statistics for an active or completed capture.
    Returns packet count, file size, protocol breakdown.
    """
    stats = await packet_capture_engine.get_live_stats(capture_id)
    return stats


@router.get("/{capture_id}/dns")
async def get_dns_queries(capture_id: str):
    """
    Extract all DNS queries from a pcap file.
    Returns query names, types, and resolved addresses.
    """
    queries = await packet_capture_engine.get_dns_queries(capture_id)
    return {
        "success": True,
        "capture_id": capture_id,
        "dns_queries": queries,
        "count": len(queries),
    }


@router.get("/{capture_id}/http")
async def get_http_requests(capture_id: str):
    """Extract HTTP requests with method, host, URI, headers, cookies."""
    requests = await packet_capture_engine.get_http_requests(capture_id)
    return {
        "success": True,
        "capture_id": capture_id,
        "http_requests": requests,
        "count": len(requests),
    }


# ── List captures ─────────────────────────────────────────────────────────────

@router.get("/list")
async def list_captures(db: Session = Depends(get_db)):
    """List all captures from the database."""
    captures = await packet_capture_engine.list_captures()
    return {"success": True, "captures": captures, "count": len(captures)}


# ── Download pcap ─────────────────────────────────────────────────────────────

@router.get("/download/{capture_id}")
async def download_capture(capture_id: str):
    """Download a pcap file for offline analysis in Wireshark."""
    # Try standard path
    p = packet_capture_engine.CAPTURES_DIR / f"{capture_id}.pcap"
    if p.exists():
        return FileResponse(str(p), media_type="application/vnd.tcpdump.pcap", filename=p.name)

    # Try DB lookup
    pcap_path = await packet_capture_engine._get_pcap_path(capture_id)
    if pcap_path and Path(pcap_path).exists():
        return FileResponse(pcap_path, media_type="application/vnd.tcpdump.pcap",
                            filename=Path(pcap_path).name)

    raise HTTPException(status_code=404, detail=f"Capture file {capture_id}.pcap not found")


# ── Live packet stream WebSocket ──────────────────────────────────────────────

@router.websocket("/stream/{interface}")
async def live_packet_stream(
    websocket: WebSocket,
    interface: str,
    token: Optional[str] = Query(default=None),
):
    """
    Live packet stream WebSocket.
    Authenticate via ?token= query parameter (JWT).
    Streams tcpdump output lines as JSON text frames.
    Each frame: {"type": "packet", "line": "<tcpdump output>"}
    """
    # JWT authentication via query parameter
    if token:
        try:
            from core.auth.jwt_handler import decode_access_token
            decode_access_token(token)
        except Exception:
            await websocket.close(code=4001)
            return
    else:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    stream_id = await packet_capture_engine.start_live_stream(interface)

    try:
        import json as _json
        await websocket.send_text(_json.dumps({
            "type": "stream_started",
            "stream_id": stream_id,
            "interface": interface,
        }))

        while True:
            line = await packet_capture_engine.get_stream_packet(stream_id, timeout=2.0)
            if line:
                await websocket.send_text(_json.dumps({
                    "type": "packet",
                    "line": line,
                    "interface": interface,
                }))
            else:
                # Keepalive
                try:
                    await websocket.send_text(_json.dumps({"type": "ping"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Packet stream WS error: {e}")
    finally:
        await packet_capture_engine.stop_live_stream(stream_id)
