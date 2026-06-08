"""
Maritime Intelligence — Bloc 6 OSINT Géopolitique
Sources : AIS (Automatic Identification System), MarineTraffic, VesselFinder,
          Spire Maritime, exactEarth, Dark Vessel Detection (SAR)
Capacités : tracking flotte, dark shipping, sanctions évasion, trafic détecté
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/geoint/maritime")

_VESSEL_TYPES = {
    "cargo":       "Cargo",
    "tanker":      "Pétrolier/Tanker",
    "container":   "Porte-conteneur",
    "warship":     "Navire de guerre",
    "submarine":   "Sous-marin",
    "fishing":     "Chalutier/Pêche",
    "research":    "Navire de recherche",
    "ro_ro":       "Ro-Ro (véhicules)",
    "gas_carrier": "Méthanier/LNG",
    "yacht":       "Yacht privé",
}

_FLAGS_OF_CONCERN = [
    "Liberia", "Panama", "Marshall Islands", "Comoros",
    "Palau", "Togo", "Belize", "Bolivia (landlocked)"
]

_SANCTIONS_ENTITIES = [
    {"name": "Pacific Gas Co", "mmsi": "538005678", "flag": "Marshall Islands", "sanctioned_by": "OFAC", "reason": "Iran oil trade"},
    {"name": "Eastern Shipping LLC", "mmsi": "511100234", "flag": "Comoros", "sanctioned_by": "EU", "reason": "Russia sanctions evasion"},
    {"name": "Arctic Pioneer", "mmsi": "273456789", "flag": "Russia", "sanctioned_by": "OFAC/EU/UK", "reason": "Ukraine invasion"},
    {"name": "Dark Trader", "mmsi": "667123456", "flag": "Togo", "sanctioned_by": "OFAC", "reason": "DPRK arms transfer"},
]

_AIS_GAPS_REASONS = ["AIS turned off voluntarily", "GPS jamming", "AIS spoofing",
                      "Territorial waters restriction", "Piracy zone avoidance"]

_PORTS_HIGH_RISK = [
    {"name": "Bandar Abbas", "country": "Iran", "risk": "CRITICAL", "reason": "Iran sanctions hub"},
    {"name": "Vladivostok", "country": "Russia", "risk": "HIGH", "reason": "Russia sanctions"},
    {"name": "Nampo", "country": "North Korea", "risk": "CRITICAL", "reason": "DPRK arms/coal"},
    {"name": "Port Sudan", "country": "Sudan", "risk": "HIGH", "reason": "Arms transfer point"},
    {"name": "Tartus", "country": "Syria", "risk": "HIGH", "reason": "Russian naval base"},
]


def _gen_vessel(mmsi: str = None) -> Dict:
    """Générer données AIS réalistes pour un navire."""
    mmsi = mmsi or str(random.randint(200000000, 799999999))
    vtype = random.choice(list(_VESSEL_TYPES.keys()))
    flag = random.choice(list(["France", "USA", "UK", "Germany", "China", "Greece",
                                "Singapore"] + _FLAGS_OF_CONCERN))
    return {
        "mmsi": mmsi,
        "imo": str(random.randint(1000000, 9999999)),
        "name": random.choice(["NORDIC STAR", "PACIFIC TRADER", "SEA EAGLE", "EVER GIVEN",
                                "SHADOW WIND", "DARK OCEAN", "ARCTIC PIONEER", "EASTERN SKY"]),
        "vessel_type": _VESSEL_TYPES[vtype],
        "flag": flag,
        "length_m": random.randint(50, 400),
        "gross_tonnage": random.randint(1000, 200000),
        "built_year": random.randint(1990, 2023),
        "owner": f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))} Shipping Ltd",
        "ais_class": random.choice(["A", "B"]),
    }


def _gen_position(lat_center: float = 0, lon_center: float = 0) -> Dict:
    return {
        "lat": round(lat_center + random.uniform(-5, 5), 5),
        "lon": round(lon_center + random.uniform(-5, 5), 5),
        "speed_knots": round(random.uniform(0, 18), 1),
        "course_deg": random.randint(0, 359),
        "heading": random.randint(0, 359),
        "nav_status": random.choice(["underway", "at anchor", "moored", "constrained by draught"]),
        "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 60))).isoformat(),
    }


class MaritimeService:
    """Maritime intelligence — AIS tracking + dark shipping + sanctions."""

    def track_vessel(self, identifier: str,
                      id_type: str = "mmsi",
                      history_days: int = 30) -> Dict:
        """Tracker un navire via MMSI, IMO ou nom."""
        session_id = str(uuid.uuid4())
        vessel = _gen_vessel(mmsi=identifier if id_type == "mmsi" else None)
        if id_type == "name":
            vessel["name"] = identifier.upper()
        elif id_type == "imo":
            vessel["imo"] = identifier

        # Historique de positions
        positions = []
        current = datetime.utcnow()
        lat, lon = random.uniform(-60, 70), random.uniform(-180, 180)
        for i in range(min(history_days * 4, 200)):
            lat += random.uniform(-0.3, 0.3)
            lon += random.uniform(-0.3, 0.3)
            ts = current - timedelta(hours=i * 6)
            positions.append({
                "lat": round(lat, 5), "lon": round(lon, 5),
                "speed_knots": round(random.uniform(0, 16), 1),
                "course": random.randint(0, 359),
                "timestamp": ts.isoformat(),
                "ais_signal": random.random() > 0.1,
            })

        ais_gaps = [p for p in positions if not p["ais_signal"]]
        sanctioned = vessel["mmsi"] in [s["mmsi"] for s in _SANCTIONS_ENTITIES]
        flag_concern = vessel["flag"] in _FLAGS_OF_CONCERN

        return {
            "session_id": session_id,
            "vessel": vessel,
            "current_position": _gen_position(),
            "track_history": positions[:50],
            "ais_gaps": len(ais_gaps),
            "ais_gap_reason": random.choice(_AIS_GAPS_REASONS) if ais_gaps else None,
            "sanctions_hit": sanctioned,
            "flag_of_concern": flag_concern,
            "risk_score": round(random.uniform(0.1, 0.9), 2),
            "dark_shipping_suspected": len(ais_gaps) > 10,
            "simulated": True,
        }

    def search_area(self, lat: float, lon: float,
                     radius_nm: float = 50.0,
                     filter_type: Optional[str] = None) -> Dict:
        """Rechercher navires dans une zone géographique."""
        session_id = str(uuid.uuid4())
        count = random.randint(3, 25)
        vessels = []
        for _ in range(count):
            v = _gen_vessel()
            v["position"] = _gen_position(lat, lon)
            v["distance_nm"] = round(random.uniform(0, radius_nm), 1)
            v["flag_concern"] = v["flag"] in _FLAGS_OF_CONCERN
            vessels.append(v)

        if filter_type:
            vessels = [v for v in vessels if filter_type.lower() in v["vessel_type"].lower()]

        suspicious = [v for v in vessels if v.get("flag_concern")]
        return {
            "session_id": session_id,
            "search_center": {"lat": lat, "lon": lon},
            "radius_nm": radius_nm,
            "vessels_found": len(vessels),
            "vessels": vessels[:20],
            "suspicious_flags": len(suspicious),
            "high_risk_vessels": [v for v in suspicious],
            "simulated": True,
        }

    def detect_dark_shipping(self, region: str = "Persian Gulf",
                              days: int = 30) -> Dict:
        """Détecter navires pratiquant le 'dark shipping' (AIS désactivé)."""
        session_id = str(uuid.uuid4())
        region_coords = {
            "Persian Gulf":   (26.0, 53.0),
            "Arabian Sea":    (15.0, 65.0),
            "Black Sea":      (43.0, 34.0),
            "South China Sea":(12.0, 114.0),
            "Baltic Sea":     (58.0, 20.0),
            "Mediterranean":  (37.0, 16.0),
        }
        lat, lon = region_coords.get(region, (0.0, 0.0))

        dark_vessels = []
        for _ in range(random.randint(2, 12)):
            v = _gen_vessel()
            v["last_ais_signal"] = (datetime.utcnow() - timedelta(hours=random.randint(12, 72))).isoformat()
            v["ais_gap_hours"] = random.randint(12, 168)
            v["last_known_position"] = _gen_position(lat, lon)
            v["suspected_cargo"] = random.choice(["crude_oil", "arms", "dual_use_goods", "unknown"])
            v["sanctions_risk"] = random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
            dark_vessels.append(v)

        return {
            "session_id": session_id,
            "region": region,
            "analysis_period_days": days,
            "dark_vessels_detected": len(dark_vessels),
            "vessels": dark_vessels,
            "sanctions_evasion_suspected": sum(1 for v in dark_vessels if v["sanctions_risk"] in ["HIGH", "CRITICAL"]),
            "intel_confidence": "MEDIUM",
            "simulated": True,
        }

    def ship_to_ship_transfer(self, area: str = "Arabian Sea") -> Dict:
        """Détecter transferts de cargaison de navire à navire (STS)."""
        session_id = str(uuid.uuid4())
        events = []
        for _ in range(random.randint(1, 5)):
            events.append({
                "vessel_a": _gen_vessel(),
                "vessel_b": _gen_vessel(),
                "date": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
                "duration_hours": round(random.uniform(4, 48), 1),
                "location": {
                    "lat": round(random.uniform(-20, 25), 4),
                    "lon": round(random.uniform(45, 75), 4),
                },
                "cargo_type": random.choice(["oil", "LNG", "unknown", "arms_suspected"]),
                "ais_disabled_during": random.random() > 0.4,
                "risk": random.choice(["MEDIUM", "HIGH", "CRITICAL"]),
            })
        return {
            "session_id": session_id,
            "area": area,
            "sts_events_detected": len(events),
            "events": events,
            "simulated": True,
        }

    def sanctions_screening(self, mmsi_list: List[str]) -> Dict:
        """Vérifier liste de navires contre sanctions OFAC/EU/UN."""
        results = []
        for mmsi in mmsi_list:
            hit = next((s for s in _SANCTIONS_ENTITIES if s["mmsi"] == mmsi), None)
            results.append({
                "mmsi": mmsi,
                "sanctioned": hit is not None,
                "sanctions_body": hit["sanctioned_by"] if hit else None,
                "reason": hit["reason"] if hit else None,
                "risk": "CRITICAL" if hit else "CLEAR",
            })
        return {"results": results, "total_screened": len(mmsi_list),
                "hits": sum(1 for r in results if r["sanctioned"]), "simulated": True}

    def list_high_risk_ports(self) -> List[Dict]:
        return _PORTS_HIGH_RISK

    def get_session(self, session_id: str) -> Dict:
        return _SESSIONS.get(session_id, {"error": "not found"})
