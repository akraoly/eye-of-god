"""
Satellite Intelligence — Bloc 6 OSINT Géopolitique
Sources : Sentinel-2 (ESA Copernicus), Landsat-9 (USGS), Planet Labs,
          Maxar WorldView, SPOT, SAR (Sentinel-1), Capella Space
Capacités : analyse changement, détection activité militaire, surveillance installations
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/geoint/satellite")

_SATELLITES = {
    "sentinel2":  {"name": "Sentinel-2 (ESA)",    "resolution_m": 10,   "revisit_days": 5,  "free": True,  "bands": 13},
    "sentinel1":  {"name": "Sentinel-1 SAR (ESA)","resolution_m": 5,    "revisit_days": 6,  "free": True,  "bands": 1, "sar": True},
    "landsat9":   {"name": "Landsat-9 (USGS)",    "resolution_m": 30,   "revisit_days": 16, "free": True,  "bands": 11},
    "planet":     {"name": "Planet Labs (PlanetScope)", "resolution_m": 3, "revisit_days": 1, "free": False, "bands": 4},
    "maxar":      {"name": "Maxar WorldView-3",   "resolution_m": 0.31, "revisit_days": 2,  "free": False, "bands": 8},
    "capella":    {"name": "Capella SAR",          "resolution_m": 0.5,  "revisit_days": 1,  "free": False, "bands": 1, "sar": True},
    "skysat":     {"name": "SkySat (Planet)",      "resolution_m": 0.5,  "revisit_days": 1,  "free": False, "bands": 4},
}

_CHANGE_TYPES = [
    "new_construction", "vehicle_movement", "vegetation_change",
    "water_level_change", "crater_formation", "military_buildup",
    "port_activity", "airstrip_activity", "industrial_emissions",
]

_ANALYSIS_TYPES = {
    "ndvi":      "Normalized Difference Vegetation Index — santé végétation",
    "ndwi":      "Normalized Difference Water Index — détection eau/inondation",
    "nbr":       "Normalized Burn Ratio — post-fire assessment",
    "change_det":"Change Detection — avant/après comparaison",
    "object_det":"Object Detection — véhicules, bâtiments, navires",
    "sar_coh":   "SAR Coherence — subsidence sol, déformation",
    "thermal":   "Thermal IR — chaleur industrielle, camouflage thermique",
}

_POI_TYPES = [
    "missile_silo", "military_base", "submarine_base", "airfield",
    "nuclear_facility", "radar_installation", "port_activity",
    "convoy_movement", "troop_concentration", "oil_terminal",
]


def _copernicus_available() -> bool:
    try:
        import sentinelsat
        return True
    except ImportError:
        return False


class SatelliteService:
    """Analyse imagerie satellite — surveillance géopolitique."""

    def acquire_image(self, lat: float, lon: float,
                       satellite: str = "sentinel2",
                       date_from: str = None,
                       date_to: str = None,
                       cloud_cover_max: int = 20) -> Dict:
        """Acquérir image satellite pour coordonnées cibles."""
        session_id = str(uuid.uuid4())
        sat = _SATELLITES.get(satellite, _SATELLITES["sentinel2"])

        if not date_to:
            date_to = datetime.utcnow().strftime("%Y-%m-%d")
        if not date_from:
            date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        has_real = _copernicus_available() and sat["free"]
        image_path = str(_OUTPUT / f"img_{session_id[:8]}.tif")

        if has_real:
            try:
                from sentinelsat import SentinelAPI
                api = SentinelAPI(
                    os.getenv("COPERNICUS_USER", "demo"),
                    os.getenv("COPERNICUS_PASS", "demo"),
                    "https://scihub.copernicus.eu/dhus"
                )
                from shapely.geometry import Point
                footprint = Point(lon, lat).buffer(0.05)
                products = api.query(footprint, date=(date_from, date_to),
                                     platformname="Sentinel-2",
                                     cloudcoverpercentage=(0, cloud_cover_max))
                if products:
                    pid = list(products.keys())[0]
                    meta = products[pid]
                    return {
                        "session_id": session_id,
                        "satellite": sat["name"],
                        "product_id": str(pid),
                        "cloud_cover": meta.get("cloudcoverpercentage", 0),
                        "date": str(meta.get("beginposition")),
                        "image_path": image_path,
                        "simulated": False,
                    }
            except Exception as e:
                logger.warning(f"Copernicus API: {e}")

        result = {
            "session_id": session_id,
            "coordinates": {"lat": lat, "lon": lon},
            "satellite": sat["name"],
            "resolution_m": sat["resolution_m"],
            "acquisition_date": (datetime.utcnow() - timedelta(days=random.randint(1, sat["revisit_days"]))).strftime("%Y-%m-%d"),
            "cloud_cover_pct": round(random.uniform(0, cloud_cover_max), 1),
            "image_path": image_path,
            "image_size_mb": round(random.uniform(10, 800), 1),
            "bands_available": sat["bands"],
            "sar": sat.get("sar", False),
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def analyze_change(self, lat: float, lon: float,
                        date_before: str, date_after: str,
                        analysis_type: str = "change_det",
                        satellite: str = "sentinel2") -> Dict:
        """Détecter changements entre deux dates sur une zone."""
        session_id = str(uuid.uuid4())
        changes = []
        num_changes = random.randint(0, 5)
        for _ in range(num_changes):
            changes.append({
                "type": random.choice(_CHANGE_TYPES),
                "confidence": round(random.uniform(0.65, 0.99), 2),
                "bbox": [lat + random.uniform(-0.01, 0.01),
                         lon + random.uniform(-0.01, 0.01),
                         lat + random.uniform(-0.01, 0.01),
                         lon + random.uniform(-0.01, 0.01)],
                "area_m2": round(random.uniform(100, 500000), 0),
                "significance": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
            })

        return {
            "session_id": session_id,
            "coordinates": {"lat": lat, "lon": lon},
            "analysis": _ANALYSIS_TYPES.get(analysis_type, analysis_type),
            "date_before": date_before,
            "date_after": date_after,
            "changes_detected": len(changes),
            "changes": changes,
            "overall_significance": "HIGH" if any(c["significance"] in ["HIGH","CRITICAL"] for c in changes) else "LOW",
            "report_path": str(_OUTPUT / f"change_{session_id[:8]}.json"),
            "simulated": True,
        }

    def detect_military_activity(self, lat: float, lon: float,
                                   radius_km: float = 50.0) -> Dict:
        """Détecter activité militaire dans un rayon autour de coordonnées."""
        session_id = str(uuid.uuid4())
        findings = []
        for _ in range(random.randint(0, 4)):
            poi_type = random.choice(_POI_TYPES)
            findings.append({
                "poi_type": poi_type,
                "lat": lat + random.uniform(-0.5, 0.5),
                "lon": lon + random.uniform(-0.5, 0.5),
                "confidence": round(random.uniform(0.60, 0.98), 2),
                "last_activity": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
                "change_vs_baseline": random.choice(["+15% vehicles", "new structure 200m×80m",
                                                      "runway extension", "3 new SAM batteries",
                                                      "submarine dock activity"]),
                "threat_level": random.choice(["ELEVATED", "HIGH", "CRITICAL"]),
            })
        return {
            "session_id": session_id,
            "center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "pois_detected": len(findings),
            "findings": findings,
            "intel_summary": f"{len(findings)} points d'intérêt militaires détectés dans rayon {radius_km}km",
            "simulated": True,
        }

    def monitor_installation(self, name: str,
                              lat: float, lon: float,
                              installation_type: str = "nuclear_facility",
                              satellites: Optional[List[str]] = None) -> Dict:
        """Surveillance continue d'une installation."""
        session_id = str(uuid.uuid4())
        sats = satellites or ["sentinel2", "sentinel1"]
        alerts = []
        if random.random() > 0.5:
            alerts.append({
                "type": "unusual_activity",
                "description": random.choice([
                    "Augmentation trafic véhicules +40%",
                    "Nouvelles structures temporaires",
                    "Activité nocturne détectée (thermal IR)",
                    "Camouflage réseau déployé",
                    "Navires de ravitaillement présents",
                ]),
                "severity": random.choice(["MEDIUM", "HIGH", "CRITICAL"]),
                "detected_at": datetime.utcnow().isoformat(),
            })
        return {
            "session_id": session_id,
            "installation": name,
            "type": installation_type,
            "coordinates": {"lat": lat, "lon": lon},
            "satellites_tasked": sats,
            "revisit_interval_days": min(_SATELLITES.get(s, {}).get("revisit_days", 5) for s in sats),
            "alerts": alerts,
            "status": "ACTIVE_MONITORING",
            "simulated": True,
        }

    def list_satellites(self) -> List[Dict]:
        return [{"id": k, **v} for k, v in _SATELLITES.items()]

    def list_analysis_types(self) -> List[Dict]:
        return [{"id": k, "description": v} for k, v in _ANALYSIS_TYPES.items()]
