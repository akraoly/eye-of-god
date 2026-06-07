"""
Routes /api/rfid — RFID Badge Cloning via Proxmark3.

Toutes les routes sont protégées par get_current_user.
Le service singleton rfid_service bascule automatiquement en mode simulation
si Proxmark3 n'est pas connecté.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models_rfid import RFIDCard, RFIDLog
from services.rfid.rfid_service import RFIDService

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Singleton service ─────────────────────────────────────────────────────────

rfid_service = RFIDService()


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _log(db: Session, action: str, card_uid: Optional[str], details: dict, success: bool = True) -> None:
    try:
        entry = RFIDLog(action=action, card_uid=card_uid, details=details, success=success)
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.warning("RFID log DB error: %s", exc)
        db.rollback()


def _card_to_dict(card: RFIDCard) -> dict:
    return {
        "id":             card.id,
        "card_id":        card.card_id,
        "uid":            card.uid,
        "card_type":      card.card_type,
        "protocol":       card.protocol,
        "atqa":           card.atqa,
        "sak":            card.sak,
        "size":           card.size,
        "data_hex":       card.data_hex,
        "blocks_count":   card.blocks_count,
        "keys_found":     card.keys_found or [],
        "site_code":      card.site_code,
        "badge_number":   card.badge_number,
        "facility_code":  card.facility_code,
        "vulnerabilities": card.vulnerabilities or [],
        "cloned":         card.cloned,
        "clone_date":     card.clone_date.isoformat() if card.clone_date else None,
        "simulated":      card.simulated,
        "first_seen":     card.first_seen.isoformat() if card.first_seen else None,
        "created_at":     card.created_at.isoformat() if card.created_at else None,
    }


# ── Pydantic models ───────────────────────────────────────────────────────────

class DumpRequest(BaseModel):
    card_type: str = "hf_mifare_classic"


class CloneRequest(BaseModel):
    source_uid:  str
    data_hex:    str
    target_type: str = "lf_t55xx"


class WriteBlockRequest(BaseModel):
    block:    int
    data:     str
    key:      str = "FFFFFFFFFFFF"
    key_type: str = "A"


class BruteForceRequest(BaseModel):
    known_keys: List[str] = []


class SniffRequest(BaseModel):
    duration: int = 30


class SimulateRequest(BaseModel):
    uid:       str
    data_hex:  str
    card_type: str = "hf_mifare_classic"
    duration:  int = 30


class AnalyzeRequest(BaseModel):
    raw_data: str


class VulnScanRequest(BaseModel):
    card_type: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(_user=Depends(get_current_user)):
    """Détecte Proxmark3 et retourne son statut."""
    try:
        status = await rfid_service.detect_proxmark()
        return {"success": True, **status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scan")
async def scan_card(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Scan une carte RFID, la sauvegarde en DB et retourne les infos."""
    try:
        result = await rfid_service.scan_card()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.get("success") or not result.get("uid"):
        _log(db, "scan", None, result, success=False)
        raise HTTPException(status_code=404, detail="Aucune carte détectée")

    uid = result["uid"]

    # Upsert en DB
    card = db.query(RFIDCard).filter(RFIDCard.uid == uid).first()
    if card:
        card.card_type = result.get("type", card.card_type)
        card.protocol  = result.get("protocol", card.protocol)
        card.atqa      = result.get("atqa", card.atqa)
        card.sak       = result.get("sak", card.sak)
        card.simulated = result.get("simulated", False)
    else:
        card = RFIDCard(
            uid       = uid,
            card_type = result.get("type", "unknown"),
            protocol  = result.get("protocol"),
            atqa      = result.get("atqa"),
            sak       = result.get("sak"),
            simulated = result.get("simulated", False),
        )
        db.add(card)

    try:
        db.commit()
        db.refresh(card)
    except Exception as exc:
        db.rollback()
        logger.warning("DB commit scan: %s", exc)

    _log(db, "scan", uid, result)
    return {"success": True, "card": _card_to_dict(card)}


@router.post("/dump")
async def dump_card(
    req: DumpRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Dump complet de la carte."""
    try:
        result = await rfid_service.dump_card(req.card_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.get("success"):
        raise HTTPException(status_code=500, detail="Dump échoué")

    _log(db, "dump", None, {"card_type": req.card_type, "blocks_count": result.get("blocks_count")})
    return {"success": True, **result}


@router.post("/clone")
async def clone_card(
    req: CloneRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Clone les données d'une carte source vers une carte cible."""
    try:
        result = await rfid_service.clone_card(req.source_uid, req.data_hex, req.target_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Met à jour le flag cloned en DB
    if result.get("success"):
        card = db.query(RFIDCard).filter(RFIDCard.uid == req.source_uid).first()
        if card:
            card.cloned     = True
            card.clone_date = datetime.utcnow()
            try:
                db.commit()
            except Exception:
                db.rollback()

    _log(db, "clone", req.source_uid, {"target_type": req.target_type, "success": result.get("success")})
    return {"success": result.get("success", False), **result}


@router.post("/write-block")
async def write_block(
    req: WriteBlockRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Écrit un bloc MIFARE Classic."""
    try:
        result = await rfid_service.write_mifare_block(req.block, req.data, req.key, req.key_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log(db, "write_block", None, {"block": req.block, "success": result.get("success")})
    return result


@router.get("/read-block/{block}")
async def read_block(
    block: int,
    key: str = Query(default="FFFFFFFFFFFF"),
    key_type: str = Query(default="A"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lit un bloc MIFARE Classic."""
    try:
        result = await rfid_service.read_mifare_block(block, key, key_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log(db, "read_block", None, {"block": block})
    return result


@router.post("/bruteforce")
async def bruteforce_keys(
    req: BruteForceRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Brute-force des clés MIFARE."""
    try:
        result = await rfid_service.brute_force_keys(req.known_keys)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log(db, "bruteforce", None, {"keys_found": result.get("keys_found", [])})
    return result


@router.post("/sniff")
async def sniff_rfid(
    req: SniffRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Capture les échanges RFID."""
    if req.duration < 1 or req.duration > 300:
        raise HTTPException(status_code=400, detail="duration doit être entre 1 et 300 secondes")

    try:
        result = await rfid_service.sniff_rfid(req.duration)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log(db, "sniff", None, {"duration": req.duration, "frames": result.get("count", 0)})
    return result


@router.post("/simulate")
async def simulate_card(
    req: SimulateRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Émule une carte RFID."""
    try:
        result = await rfid_service.simulate_card(req.uid, req.data_hex, req.card_type, req.duration)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    _log(db, "simulate", req.uid, {"card_type": req.card_type, "duration": req.duration})
    return result


@router.post("/analyze")
async def analyze_card(
    req: AnalyzeRequest,
    _user=Depends(get_current_user),
):
    """Analyse les données brutes d'une carte."""
    result = rfid_service.analyze_card_type(req.raw_data)
    return {"success": True, **result}


@router.post("/vuln-scan")
async def vuln_scan(
    req: VulnScanRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Retourne les vulnérabilités connues pour un type de carte."""
    vulns = rfid_service.detect_vulnerabilities(req.card_type)
    _log(db, "vuln_scan", None, {"card_type": req.card_type, "vulns_count": len(vulns)})
    return {"success": True, "card_type": req.card_type, "vulnerabilities": vulns}


# ── CRUD cartes ───────────────────────────────────────────────────────────────

@router.get("/cards")
async def list_cards(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Liste toutes les cartes scannées."""
    cards = db.query(RFIDCard).order_by(RFIDCard.created_at.desc()).all()
    return {"success": True, "cards": [_card_to_dict(c) for c in cards], "count": len(cards)}


@router.get("/cards/{card_id}")
async def get_card(
    card_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Détail d'une carte."""
    card = db.query(RFIDCard).filter(RFIDCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    return {"success": True, "card": _card_to_dict(card)}


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Supprime une carte de la DB."""
    card = db.query(RFIDCard).filter(RFIDCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    uid = card.uid
    db.delete(card)
    db.commit()
    _log(db, "delete_card", uid, {"card_id": card_id})
    return {"success": True, "deleted": card_id}


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    action:   Optional[str] = Query(default=None),
    card_uid: Optional[str] = Query(default=None),
    limit:    int            = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Liste les logs d'actions RFID."""
    q = db.query(RFIDLog).order_by(RFIDLog.timestamp.desc())
    if action:
        q = q.filter(RFIDLog.action == action)
    if card_uid:
        q = q.filter(RFIDLog.card_uid == card_uid)
    logs = q.limit(limit).all()
    return {
        "success": True,
        "logs": [
            {
                "id":        log.id,
                "action":    log.action,
                "card_uid":  log.card_uid,
                "details":   log.details,
                "success":   log.success,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
        "count": len(logs),
    }
