"""
AEGIS — Collecteur NVD NIST v2 + CISA KEV
Ingestion automatique des CVE toutes les heures.
Alerte immédiate si CVSS ≥ seuil configuré.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import requests

try:
    from core.tools.logger import get_logger
    logger = get_logger("aegis.nvd")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

NVD_BASE  = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CISA_KEV  = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

SEVERITY_MAP = {
    "CRITICAL": 9.0, "HIGH": 7.0, "MEDIUM": 4.0, "LOW": 0.1,
}


def _cvss_to_severity(score: float) -> str:
    if score >= 9.0: return "CRITICAL"
    if score >= 7.0: return "HIGH"
    if score >= 4.0: return "MEDIUM"
    return "LOW"


def _parse_nvd_item(item: dict) -> dict:
    cve = item.get("cve", {})
    cve_id = cve.get("id", "")
    metrics = cve.get("metrics", {})

    # Score CVSS v3 en priorité, sinon v2
    score = 0.0
    vector = ""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if key in metrics and metrics[key]:
            data = metrics[key][0].get("cvssData", {})
            score = data.get("baseScore", 0.0)
            vector = data.get("vectorString", "")
            break

    desc = ""
    for d in cve.get("descriptions", []):
        if d.get("lang") == "en":
            desc = d.get("value", "")
            break

    # Produits affectés
    products = []
    for conf in cve.get("configurations", []):
        for node in conf.get("nodes", []):
            for match in node.get("cpeMatch", []):
                cpe = match.get("criteria", "")
                parts = cpe.split(":")
                if len(parts) > 4:
                    products.append(f"{parts[3]} {parts[4]}")
    products = list(set(products))[:20]

    # CWE
    cwes = [w.get("value", "") for w in cve.get("weaknesses", [])
            for w in w.get("description", []) if w.get("lang") == "en"]

    # Références
    refs = [r.get("url", "") for r in cve.get("references", [])][:10]

    return {
        "cve_id": cve_id,
        "title": cve_id,
        "description": desc[:2000] if desc else "",
        "cvss_score": float(score),
        "cvss_vector": vector,
        "severity": _cvss_to_severity(float(score)),
        "cwe_ids": json.dumps(list(set(cwes))),
        "affected_products": json.dumps(products),
        "references": json.dumps(refs),
        "source": "nvd",
        "published_at": datetime.fromisoformat(
            cve.get("published", datetime.utcnow().isoformat()).replace("Z", "+00:00")
        ).replace(tzinfo=None),
        "modified_at": datetime.fromisoformat(
            cve.get("lastModified", datetime.utcnow().isoformat()).replace("Z", "+00:00")
        ).replace(tzinfo=None),
    }


def fetch_nvd_recent(days: int = 1, api_key: str = "") -> list[dict]:
    """Récupère les CVE publiés/modifiés dans les N derniers jours."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    params = {
        "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "pubEndDate":   end.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "resultsPerPage": 100,
    }
    headers = {}
    if api_key:
        headers["apiKey"] = api_key

    all_cves = []
    start_index = 0
    while True:
        try:
            params["startIndex"] = start_index
            resp = requests.get(NVD_BASE, params=params, headers=headers, timeout=30)
            if resp.status_code == 403:
                logger.warning("nvd: quota atteint (403)")
                break
            resp.raise_for_status()
            data = resp.json()
            vulns = data.get("vulnerabilities", [])
            all_cves.extend([_parse_nvd_item(v) for v in vulns])
            total = data.get("totalResults", 0)
            start_index += len(vulns)
            if start_index >= total or not vulns:
                break
        except Exception as e:
            logger.warning("nvd fetch error: %s", e)
            break

    logger.info("nvd: %d CVE récupérés (%d jours)", len(all_cves), days)
    return all_cves


def fetch_cisa_kev() -> list[dict]:
    """Récupère le catalogue CISA Known Exploited Vulnerabilities."""
    try:
        resp = requests.get(CISA_KEV, timeout=30)
        resp.raise_for_status()
        vulns = resp.json().get("vulnerabilities", [])
        result = []
        for v in vulns:
            score = 9.5  # CISA KEV = exploités, donc toujours critique
            result.append({
                "cve_id":            v.get("cveID", ""),
                "title":             v.get("vulnerabilityName", v.get("cveID", "")),
                "description":       f"{v.get('vendorProject', '')} {v.get('product', '')} — {v.get('shortDescription', '')}",
                "cvss_score":        score,
                "cvss_vector":       "",
                "severity":          "CRITICAL",
                "cwe_ids":           json.dumps([]),
                "affected_products": json.dumps([f"{v.get('vendorProject', '')} {v.get('product', '')}"]),
                "references":        json.dumps([]),
                "source":            "cisa_kev",
                "published_at":      _parse_date(v.get("dateAdded", "")),
                "modified_at":       datetime.utcnow(),
            })
        logger.info("cisa_kev: %d entrées récupérées", len(result))
        return result
    except Exception as e:
        logger.warning("cisa_kev fetch error: %s", e)
        return []


def _parse_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return datetime.utcnow()


def ingest_cves(db, new_cves: list[dict], cvss_threshold: float = 9.0) -> tuple[int, int]:
    """
    Insère les nouveaux CVE en DB, évite les doublons.
    Retourne (nb_ajoutés, nb_alertes).
    """
    from database.models import AegisCVE, SecurityEventLog
    added = 0
    alerts = 0

    for c in new_cves:
        if not c.get("cve_id"):
            continue
        existing = db.query(AegisCVE).filter(AegisCVE.cve_id == c["cve_id"]).first()
        if existing:
            continue

        row = AegisCVE(**{k: v for k, v in c.items() if hasattr(AegisCVE, k)})
        db.add(row)
        added += 1

        # Alerte si CVSS ≥ seuil
        if row.cvss_score >= cvss_threshold:
            evt = SecurityEventLog(
                category="AEGIS_CVE",
                severity="CRITICAL" if row.cvss_score >= 9 else "HIGH",
                title=f"[AEGIS] {row.cve_id} — CVSS {row.cvss_score}",
                description=row.description[:300] if row.description else "",
            )
            db.add(evt)

            # Publier dans le bus Sentinel
            try:
                from core.monitor.event_bus import sentinel_bus
                sentinel_bus.publish({
                    "type":     "security_event",
                    "category": "AEGIS_CVE",
                    "severity": evt.severity,
                    "title":    evt.title,
                    "description": evt.description,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception:
                pass
            alerts += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("ingest_cves commit error: %s", e)

    if added:
        logger.info("aegis: %d CVE ajoutés, %d alertes critiques", added, alerts)
    return added, alerts


def correlate_with_projects(db, cve: "AegisCVE") -> bool:
    """
    Vérifie si les produits affectés par ce CVE correspondent
    à des technologies connues dans les projets de Mr Vitch.
    """
    KNOWN_STACK = {
        "python", "fastapi", "uvicorn", "sqlalchemy", "mariadb", "mysql",
        "node", "react", "vite", "npm", "nginx", "linux", "debian", "ubuntu",
        "openssl", "ssh", "openssh", "bash", "chromium",
    }
    try:
        products = json.loads(cve.affected_products or "[]")
        for p in products:
            for known in KNOWN_STACK:
                if known.lower() in p.lower():
                    return True
    except Exception:
        pass
    return False
