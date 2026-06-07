"""
Routes /api/ble — BLE Scanner module.

Scan BLE devices, fingerprint, vuln-scan, track (RSSI), GATT read/write,
tracker detection and location.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models_ble import BLEDevice, BLELog
from services.ble.ble_scanner_service import BLEScannerService

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton service instance
ble_service = BLEScannerService()


# ── Pydantic request/response models ─────────────────────────────────────────

class GATTWriteRequest(BaseModel):
    service_uuid: str
    char_uuid: str
    data: str   # hex string, e.g. "0102ff"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_device(db: Session, dev: Dict[str, Any]) -> BLEDevice:
    """Insert or update a BLEDevice row from a scan result dict."""
    mac = dev.get("mac", "").upper()
    if not mac:
        raise ValueError("Device dict missing 'mac' field")

    row = db.query(BLEDevice).filter(BLEDevice.mac_address == mac).first()
    if row is None:
        row = BLEDevice(
            mac_address=mac,
            first_seen=datetime.utcnow(),
        )
        db.add(row)

    row.name = dev.get("name") or row.name
    row.rssi = dev.get("rssi", row.rssi)
    row.manufacturer = dev.get("manufacturer") or row.manufacturer
    row.device_type = dev.get("device_type", row.device_type)
    row.services = dev.get("services", row.services or [])
    row.is_tracker = dev.get("is_tracker", row.is_tracker)
    row.tracker_type = dev.get("tracker_type") or row.tracker_type
    row.simulated = dev.get("simulated", row.simulated)
    row.last_seen = datetime.utcnow()

    db.commit()
    db.refresh(row)
    return row


def _log_action(db: Session, mac: str, action: str, details: Any = None, success: bool = True):
    entry = BLELog(
        mac_address=mac.upper(),
        action=action,
        details=details,
        success=success,
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


def _device_to_dict(row: BLEDevice) -> Dict[str, Any]:
    return {
        "id": row.id,
        "ble_id": row.ble_id,
        "mac_address": row.mac_address,
        "name": row.name,
        "rssi": row.rssi,
        "manufacturer": row.manufacturer,
        "device_type": row.device_type,
        "services": row.services or [],
        "first_seen": row.first_seen.isoformat() if row.first_seen else None,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        "is_tracker": row.is_tracker,
        "tracker_type": row.tracker_type,
        "gatt_services": row.gatt_services or [],
        "vulns": row.vulns or [],
        "simulated": row.simulated,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── Scan ──────────────────────────────────────────────────────────────────────

@router.get("/scan")
async def scan_ble(
    duration: int = Query(10, ge=3, le=120),
    interface: str = Query("hci0"),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Synchronous BLE scan — blocks for `duration` seconds, saves results, returns list."""
    try:
        devices = await ble_service.scan_devices(duration=duration, interface=interface)
    except Exception as exc:
        logger.exception("BLE scan failed")
        raise HTTPException(status_code=500, detail=str(exc))

    saved = []
    for dev in devices:
        try:
            row = _upsert_device(db, dev)
            _log_action(db, dev.get("mac", ""), "scan", {"rssi": dev.get("rssi")})
            saved.append(_device_to_dict(row))
        except Exception as exc:
            logger.warning("Could not save device %s: %s", dev.get("mac"), exc)

    simulation = ble_service._is_simulation_mode()
    return {
        "success": True,
        "count": len(saved),
        "simulation": simulation,
        "devices": saved,
    }


@router.post("/scan-async")
async def scan_ble_async(
    duration: int = Query(10, ge=3, le=120),
    interface: str = Query("hci0"),
    _: Any = Depends(get_current_user),
):
    """Start a BLE scan in the background; returns task_id immediately."""
    task_id = str(uuid.uuid4())

    async def _background():
        import asyncio
        from database.db import SessionLocal
        try:
            devices = await ble_service.scan_devices(duration=duration, interface=interface)
            db = SessionLocal()
            try:
                for dev in devices:
                    try:
                        _upsert_device(db, dev)
                    except Exception:
                        pass
            finally:
                db.close()
        except Exception as exc:
            logger.exception("Background BLE scan error: %s", exc)

    import asyncio
    asyncio.create_task(_background())

    return {"task_id": task_id, "status": "started", "duration": duration}


# ── Device list ───────────────────────────────────────────────────────────────

@router.get("/devices")
async def list_devices(
    type: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    is_tracker: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """List all BLE devices with optional filters."""
    q = db.query(BLEDevice)
    if type:
        q = q.filter(BLEDevice.device_type == type)
    if manufacturer:
        q = q.filter(BLEDevice.manufacturer.ilike(f"%{manufacturer}%"))
    if is_tracker is not None:
        q = q.filter(BLEDevice.is_tracker == is_tracker)
    rows = q.order_by(BLEDevice.last_seen.desc()).all()
    return {"devices": [_device_to_dict(r) for r in rows], "count": len(rows)}


@router.get("/devices/{mac}")
async def get_device(
    mac: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Get a single BLE device by MAC + its recent logs."""
    mac_upper = mac.upper()
    row = db.query(BLEDevice).filter(BLEDevice.mac_address == mac_upper).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Device {mac} not found")

    logs = (
        db.query(BLELog)
        .filter(BLELog.mac_address == mac_upper)
        .order_by(BLELog.timestamp.desc())
        .limit(50)
        .all()
    )
    logs_list = [
        {
            "id": lg.id,
            "action": lg.action,
            "details": lg.details,
            "success": lg.success,
            "timestamp": lg.timestamp.isoformat() if lg.timestamp else None,
        }
        for lg in logs
    ]
    return {**_device_to_dict(row), "logs": logs_list}


# ── Fingerprint ───────────────────────────────────────────────────────────────

@router.post("/devices/{mac}/fingerprint")
async def fingerprint_device(
    mac: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Enumerate GATT services and save to DB."""
    mac_upper = mac.upper()
    try:
        result = await ble_service.fingerprint_device(mac_upper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    row = db.query(BLEDevice).filter(BLEDevice.mac_address == mac_upper).first()
    if row is None:
        row = BLEDevice(mac_address=mac_upper, first_seen=datetime.utcnow(), last_seen=datetime.utcnow())
        db.add(row)

    row.gatt_services = result.get("gatt_services", [])
    row.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(row)

    _log_action(db, mac_upper, "fingerprint", {"gatt_count": len(row.gatt_services)})
    return {"success": True, "mac": mac_upper, "gatt_services": row.gatt_services, "simulated": result.get("simulated")}


# ── Vuln scan ─────────────────────────────────────────────────────────────────

@router.post("/devices/{mac}/vuln-scan")
async def vuln_scan_device(
    mac: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Detect BLE vulnerabilities and save to DB."""
    mac_upper = mac.upper()
    try:
        vulns = await ble_service.detect_vulnerabilities(mac_upper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    row = db.query(BLEDevice).filter(BLEDevice.mac_address == mac_upper).first()
    if row is None:
        row = BLEDevice(mac_address=mac_upper, first_seen=datetime.utcnow(), last_seen=datetime.utcnow())
        db.add(row)

    row.vulns = vulns
    row.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(row)

    _log_action(db, mac_upper, "vuln-scan", {"vuln_count": len(vulns)})
    return {"success": True, "mac": mac_upper, "vulns": vulns, "count": len(vulns)}


# ── Track (RSSI) ──────────────────────────────────────────────────────────────

@router.post("/devices/{mac}/track")
async def track_device(
    mac: str,
    _: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track device via RSSI for ~15 s; returns {rssi, timestamp, distance_m} samples."""
    mac_upper = mac.upper()
    try:
        result = await ble_service.locate_device(mac_upper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log_action(db, mac_upper, "track", {"avg_rssi": result.get("avg_rssi")})
    return result


# ── GATT write ────────────────────────────────────────────────────────────────

@router.post("/devices/{mac}/gatt/write")
async def gatt_write(
    mac: str,
    body: GATTWriteRequest,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Write to a GATT characteristic."""
    mac_upper = mac.upper()
    try:
        result = await ble_service.write_gatt_characteristic(
            mac_upper, body.service_uuid, body.char_uuid, body.data
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log_action(
        db, mac_upper, "gatt-write",
        {"service": body.service_uuid, "char": body.char_uuid, "data": body.data},
        success=result.get("success", False),
    )
    return result


# ── GATT read ─────────────────────────────────────────────────────────────────

@router.get("/devices/{mac}/gatt/read/{service_uuid}/{char_uuid}")
async def gatt_read(
    mac: str,
    service_uuid: str,
    char_uuid: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Read a GATT characteristic."""
    mac_upper = mac.upper()
    try:
        result = await ble_service.read_gatt_characteristic(mac_upper, service_uuid, char_uuid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log_action(db, mac_upper, "gatt-read", {"service": service_uuid, "char": char_uuid})
    return result


# ── Trackers ──────────────────────────────────────────────────────────────────

@router.get("/trackers")
async def list_trackers(
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """List all known BLE trackers from DB."""
    rows = (
        db.query(BLEDevice)
        .filter(BLEDevice.is_tracker == True)  # noqa: E712
        .order_by(BLEDevice.last_seen.desc())
        .all()
    )
    return {"trackers": [_device_to_dict(r) for r in rows], "count": len(rows)}


@router.post("/trackers/locate/{mac}")
async def locate_tracker(
    mac: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Estimate tracker location via RSSI triangulation."""
    mac_upper = mac.upper()
    try:
        result = await ble_service.locate_device(mac_upper)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log_action(db, mac_upper, "locate", {"distance_m": result.get("estimated_distance_m")})
    return result


# ── Delete device ─────────────────────────────────────────────────────────────

@router.delete("/devices/{mac}")
async def delete_device(
    mac: str,
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Delete a BLE device and its logs from the DB."""
    mac_upper = mac.upper()
    row = db.query(BLEDevice).filter(BLEDevice.mac_address == mac_upper).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Device {mac} not found")
    db.query(BLELog).filter(BLELog.mac_address == mac_upper).delete()
    db.delete(row)
    db.commit()
    return {"success": True, "deleted": mac_upper}


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    device_mac: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Any = Depends(get_current_user),
):
    """Retrieve BLE action logs with optional filters."""
    q = db.query(BLELog)
    if device_mac:
        q = q.filter(BLELog.mac_address == device_mac.upper())
    if action:
        q = q.filter(BLELog.action == action)
    rows = q.order_by(BLELog.timestamp.desc()).limit(limit).all()
    logs = [
        {
            "id": lg.id,
            "mac_address": lg.mac_address,
            "action": lg.action,
            "details": lg.details,
            "success": lg.success,
            "timestamp": lg.timestamp.isoformat() if lg.timestamp else None,
        }
        for lg in rows
    ]
    return {"logs": logs, "count": len(logs)}
