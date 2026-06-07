"""
AEGIS — Surveillance passive des cibles (pentest autorisé uniquement)
Techniques exclusivement passives : DNS, crt.sh, WHOIS.
Aucune connexion directe à la cible.

IMPORTANT: L'ajout d'une cible requiert authorization_confirmed=True.
           L'opérateur certifie disposer d'une autorisation écrite.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime
from typing import Optional

import requests

try:
    from core.tools.logger import get_logger
    logger = get_logger("aegis.targets")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def passive_recon(target_value: str, target_type: str) -> dict:
    """
    Reconnaissance passive uniquement — aucune requête directe vers la cible.
    Utilise uniquement des sources publiques tierces.
    """
    results = {
        "subdomains": [],
        "dns_records": {},
        "technologies": [],
        "whois_info": "",
        "findings": [],
    }

    if target_type == "domain":
        results["subdomains"]  = _crtsh_subdomains(target_value)
        results["dns_records"] = _dns_lookup(target_value)
        results["whois_info"]  = _whois_lookup(target_value)

    elif target_type == "ip":
        results["dns_records"] = _reverse_dns(target_value)

    return results


def _crtsh_subdomains(domain: str) -> list[str]:
    """Sous-domaines via Certificate Transparency logs (crt.sh — source publique)."""
    try:
        resp = requests.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
            timeout=20,
            headers={"Accept": "application/json"},
        )
        if not resp.ok:
            return []
        entries = resp.json()
        subs = set()
        for e in entries:
            name = e.get("name_value", "")
            for sub in name.split("\n"):
                sub = sub.strip().lstrip("*.")
                if sub.endswith(domain) and sub != domain:
                    subs.add(sub)
        result = sorted(list(subs))[:50]
        logger.info("crt.sh: %d sous-domaines pour %s", len(result), domain)
        return result
    except Exception as e:
        logger.warning("crt.sh error (%s): %s", domain, e)
        return []


def _dns_lookup(domain: str) -> dict:
    """Résolution DNS standard (pas de connexion à la cible)."""
    records: dict[str, list[str]] = {}
    try:
        info = socket.getaddrinfo(domain, None)
        ips = list(set(r[4][0] for r in info))
        records["A"] = ips[:5]
    except Exception:
        records["A"] = []
    return records


def _reverse_dns(ip: str) -> dict:
    """DNS inverse pour une IP."""
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return {"PTR": [hostname]}
    except Exception:
        return {"PTR": []}


def _whois_lookup(domain: str) -> str:
    """WHOIS via l'API publique rdap (aucune connexion directe à la cible)."""
    try:
        resp = requests.get(
            f"https://rdap.verisign.com/com/v1/domain/{domain}",
            timeout=15,
        )
        if resp.ok:
            d = resp.json()
            registrar = ""
            for entity in d.get("entities", []):
                for role in entity.get("roles", []):
                    if role == "registrar":
                        registrar = entity.get("vcardArray", [[]])[1:] or ""
                        break
            expiry = ""
            for event in d.get("events", []):
                if event.get("eventAction") == "expiration":
                    expiry = event.get("eventDate", "")
                    break
            return f"Registrar: {registrar} | Expiry: {expiry}"
    except Exception:
        pass
    return ""


def detect_changes(old_data: dict, new_data: dict) -> list[str]:
    """Compare les résultats de reconnaissance pour détecter des changements."""
    changes = []

    old_subs = set(old_data.get("subdomains") or [])
    new_subs = set(new_data.get("subdomains") or [])
    for s in new_subs - old_subs:
        changes.append(f"Nouveau sous-domaine détecté: {s}")
    for s in old_subs - new_subs:
        changes.append(f"Sous-domaine disparu: {s}")

    old_ips = set(old_data.get("dns_records", {}).get("A") or [])
    new_ips = set(new_data.get("dns_records", {}).get("A") or [])
    for ip in new_ips - old_ips:
        changes.append(f"Nouvelle IP détectée: {ip}")
    for ip in old_ips - new_ips:
        changes.append(f"IP disparue: {ip}")

    return changes


def run_passive_recon(db, target_id: str) -> dict:
    """Lance la reconnaissance passive d'une cible autorisée."""
    from database.models import AegisTarget, AegisIntelLog

    target = db.query(AegisTarget).filter(AegisTarget.target_id == target_id).first()
    if not target:
        return {"error": "Cible introuvable"}

    # GATE DE SÉCURITÉ OBLIGATOIRE
    if not target.authorization_confirmed:
        logger.warning("Tentative de recon sur cible %s sans autorisation confirmée", target.target_value)
        return {"error": "Autorisation pentest non confirmée pour cette cible"}

    logger.info("Recon passive autorisée sur %s (%s)", target.target_value, target.target_type)

    # Données précédentes
    old_data = {
        "subdomains": json.loads(target.subdomains or "[]"),
        "dns_records": json.loads(target.dns_records or "{}"),
    }

    # Nouvelle reconnaissance
    new_data = passive_recon(target.target_value, target.target_type)
    changes  = detect_changes(old_data, new_data)

    # Mise à jour de la cible
    target.subdomains   = json.dumps(new_data["subdomains"])
    target.dns_records  = json.dumps(new_data["dns_records"])
    target.technologies = json.dumps(new_data["technologies"])
    target.whois_info   = new_data["whois_info"]
    target.last_checked = datetime.utcnow()

    existing_findings = json.loads(target.findings or "[]")
    for ch in changes:
        existing_findings.append({
            "change": ch,
            "detected_at": datetime.utcnow().isoformat(),
        })
    target.findings = json.dumps(existing_findings[-50:])

    # Journal si changements
    if changes:
        log = AegisIntelLog(
            entry_type="target_change",
            title=f"Changement détecté: {target.name}",
            content="\n".join(changes),
            target_id=target.target_id,
            severity="MEDIUM",
        )
        db.add(log)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("recon commit error: %s", e)
        return {"error": str(e)}

    return {
        "target_id":  target_id,
        "subdomains":  new_data["subdomains"],
        "dns_records": new_data["dns_records"],
        "changes":     changes,
        "checked_at":  datetime.utcnow().isoformat(),
    }
