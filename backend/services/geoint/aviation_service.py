"""
Aviation Intelligence — Bloc 6 OSINT Géopolitique
Sources : ADS-B (FlightRadar24, OpenSky Network, ADS-B Exchange),
          Mode-S transponder, MLAT, ACARS, Flightaware
Capacités : tracking jets privés, avions militaires, aéronefs non coopératifs,
            détection vols clandestins, analyse routes diplomatiques
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

_AIRCRAFT_TYPES = {
    "B737":  {"name": "Boeing 737", "category": "commercial", "range_km": 5765},
    "A320":  {"name": "Airbus A320", "category": "commercial", "range_km": 6300},
    "G550":  {"name": "Gulfstream G550", "category": "private_jet", "range_km": 12500},
    "G700":  {"name": "Gulfstream G700", "category": "private_jet", "range_km": 13890},
    "C-130": {"name": "Lockheed C-130", "category": "military_transport", "range_km": 6850},
    "RC-135":{"name": "Boeing RC-135 (SIGINT)", "category": "military_surveillance", "range_km": 5550},
    "P-8A":  {"name": "Boeing P-8A Poseidon", "category": "military_maritime_patrol", "range_km": 7600},
    "U-2":   {"name": "Lockheed U-2", "category": "military_recon", "range_km": 10000},
    "RQ-4":  {"name": "Northrop Grumman RQ-4 Global Hawk", "category": "military_drone", "range_km": 22779},
    "E-3":   {"name": "Boeing E-3 Sentry (AWACS)", "category": "military_aew", "range_km": 9265},
    "BBD":   {"name": "Bombardier Global 6000", "category": "private_jet", "range_km": 11112},
}

_MILITARY_CALLSIGNS = {
    "FORTE":  "USAF reconnaissance aircraft",
    "HAVOC":  "US Navy EP-3 SIGINT",
    "JAKE":   "USAF RC-135 Rivet Joint",
    "ATLAS":  "NATO surveillance mission",
    "COBRA":  "US Army surveillance",
    "MAGMA":  "USAF special ops infiltration",
    "SPAR":   "US Government/VIP transport",
    "SAM":    "USAF Special Air Mission (VIP)",
    "AZAZ":   "UK RAF surveillance",
    "RRR":    "French Military",
}

_SQUAWK_CODES = {
    "7500": "HIJACKING",
    "7600": "RADIO FAILURE",
    "7700": "EMERGENCY",
    "0000": "NON-COOPERATIVE",
    "1200": "VFR US",
    "2000": "IFR default",
}

_COVERT_AIRLINES = [
    {"icao": "N264DB", "known_as": "CIA rendition aircraft", "last_op": "2006-2010"},
    {"icao": "N168BF", "known_as": "NSA front company aviation", "last_op": "2014-2020"},
    {"icao": "TC-IYA", "known_as": "Linked to intelligence services (unverified)", "last_op": "2023"},
]


def _gen_aircraft(icao: str = None) -> Dict:
    icao = icao or "".join(random.choices("0123456789ABCDEF", k=6))
    atype = random.choice(list(_AIRCRAFT_TYPES.keys()))
    info = _AIRCRAFT_TYPES[atype]
    return {
        "icao24": icao,
        "callsign": "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3)) + str(random.randint(100, 9999)),
        "registration": random.choice(["N", "F-", "G-", "D-", "OE-", "HB-"]) + "".join(random.choices("ABCXYZ123456", k=4)),
        "aircraft_type": atype,
        "aircraft_name": info["name"],
        "category": info["category"],
        "owner": f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))} Holdings LLC",
        "country": random.choice(["USA", "UK", "France", "Germany", "UAE", "Russia", "China"]),
        "altitude_ft": random.randint(0, 45000),
        "speed_knots": random.randint(150, 550),
        "squawk": random.choice(list(_SQUAWK_CODES.keys())[2:]),
        "transponder": random.choice(["Mode-S", "ADS-B", "Mode-C", "None"]),
    }


def _gen_flight_path(num_points: int = 30) -> List[Dict]:
    lat, lon = random.uniform(-60, 70), random.uniform(-180, 180)
    path = []
    for i in range(num_points):
        lat += random.uniform(-1, 1)
        lon += random.uniform(-1, 1)
        path.append({
            "lat": round(lat, 4), "lon": round(lon, 4),
            "altitude_ft": random.randint(0, 45000),
            "speed_knots": random.randint(200, 550),
            "timestamp": (datetime.utcnow() - timedelta(minutes=(num_points - i) * 5)).isoformat(),
            "adsb_visible": random.random() > 0.05,
        })
    return path


class AviationService:
    """Aviation intelligence — ADS-B tracking, surveillance militaire, jets privés."""

    def track_aircraft(self, identifier: str,
                        id_type: str = "icao24",
                        history_hours: int = 24) -> Dict:
        """Tracker un aéronef via ICAO24, callsign ou immatriculation."""
        session_id = str(uuid.uuid4())

        has_opensky = False
        try:
            import requests
            r = requests.get(f"https://opensky-network.org/api/states/all?icao24={identifier.lower()}",
                             timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("states"):
                    state = data["states"][0]
                    return {
                        "session_id": session_id,
                        "source": "OpenSky Network (LIVE)",
                        "icao24": state[0], "callsign": state[1],
                        "origin_country": state[2],
                        "lon": state[5], "lat": state[6], "altitude_m": state[7],
                        "on_ground": state[8], "speed_ms": state[9],
                        "heading": state[10], "vertical_rate": state[11],
                        "squawk": state[14],
                        "simulated": False,
                    }
        except Exception:
            pass

        aircraft = _gen_aircraft(identifier if id_type == "icao24" else None)
        path = _gen_flight_path(history_hours * 4)
        adsb_gaps = [p for p in path if not p["adsb_visible"]]
        military_callsign = next((v for k, v in _MILITARY_CALLSIGNS.items()
                                  if k in aircraft["callsign"]), None)

        return {
            "session_id": session_id,
            "aircraft": aircraft,
            "flight_path": path[:40],
            "adsb_gaps": len(adsb_gaps),
            "military_callsign_match": military_callsign,
            "covert_aircraft_match": any(c["icao"] == identifier for c in _COVERT_AIRLINES),
            "risk_flags": [
                *([f"Military SIGINT callsign pattern"] if military_callsign else []),
                *(["ADS-B gaps detected — possible evasion"] if adsb_gaps else []),
            ],
            "simulated": True,
        }

    def monitor_region(self, lat: float, lon: float,
                        radius_nm: float = 200.0,
                        filter_category: Optional[str] = None) -> Dict:
        """Surveiller tous les aéronefs dans une zone."""
        session_id = str(uuid.uuid4())

        try:
            import requests
            lat_min, lat_max = lat - 2, lat + 2
            lon_min, lon_max = lon - 3, lon + 3
            r = requests.get(
                f"https://opensky-network.org/api/states/all?lamin={lat_min}&lomin={lon_min}&lamax={lat_max}&lomax={lon_max}",
                timeout=8
            )
            if r.status_code == 200:
                states = r.json().get("states", [])
                aircraft_list = [{
                    "icao24": s[0], "callsign": s[1], "country": s[2],
                    "lon": s[5], "lat": s[6], "altitude_m": s[7],
                    "on_ground": s[8], "speed_ms": s[9],
                } for s in states if s[5] and s[6]]
                return {
                    "session_id": session_id,
                    "center": {"lat": lat, "lon": lon},
                    "radius_nm": radius_nm,
                    "aircraft_count": len(aircraft_list),
                    "aircraft": aircraft_list[:50],
                    "source": "OpenSky Network (LIVE)",
                    "simulated": False,
                }
        except Exception:
            pass

        count = random.randint(5, 40)
        aircraft_list = []
        for _ in range(count):
            a = _gen_aircraft()
            a["lat"] = round(lat + random.uniform(-2, 2), 4)
            a["lon"] = round(lon + random.uniform(-3, 3), 4)
            a["distance_nm"] = round(random.uniform(0, radius_nm), 1)
            aircraft_list.append(a)

        if filter_category:
            aircraft_list = [a for a in aircraft_list if filter_category in a["category"]]

        military = [a for a in aircraft_list if "military" in a["category"]]
        return {
            "session_id": session_id,
            "center": {"lat": lat, "lon": lon},
            "radius_nm": radius_nm,
            "aircraft_total": len(aircraft_list),
            "aircraft": aircraft_list[:30],
            "military_count": len(military),
            "military_aircraft": military,
            "simulated": True,
        }

    def detect_private_jet(self, owner_name: str = "",
                            tail_number: str = "",
                            history_days: int = 90) -> Dict:
        """Tracker jet privé d'un VIP/entité — historique routes."""
        session_id = str(uuid.uuid4())
        trips = []
        airports = ["EGLL", "LFPG", "EDDF", "LEMD", "LIRF", "UUEE", "ZUUU", "VHHH",
                    "OMDB", "OEJN", "KSFO", "KJFK", "KLAX", "MMEX", "SBGR"]
        for _ in range(random.randint(3, 15)):
            dep = random.choice(airports)
            arr = random.choice([a for a in airports if a != dep])
            trips.append({
                "date": (datetime.utcnow() - timedelta(days=random.randint(0, history_days))).strftime("%Y-%m-%d"),
                "departure": dep, "arrival": arr,
                "duration_min": random.randint(60, 840),
                "passengers_estimated": random.randint(1, 12),
                "notable": random.random() > 0.7,
                "notes": random.choice([
                    None, "Départ non annoncé — nuit", "Escale non typique",
                    "Coïncide avec événement géopolitique", "Retour rapide même jour",
                ])
            })

        notable = [t for t in trips if t["notable"]]
        return {
            "session_id": session_id,
            "subject": owner_name or tail_number or "Unknown",
            "aircraft": _gen_aircraft(tail_number),
            "period_days": history_days,
            "total_trips": len(trips),
            "trips": sorted(trips, key=lambda t: t["date"], reverse=True),
            "notable_trips": notable,
            "countries_visited": list(set(random.choice(["France", "UAE", "Russia", "China", "Switzerland"])
                                          for _ in trips)),
            "pattern": "IRREGULAR" if len(notable) > 3 else "NORMAL",
            "simulated": True,
        }

    def detect_military_ops(self, region: str = "Eastern Europe",
                             hours: int = 48) -> Dict:
        """Détecter activité aérienne militaire dans une région."""
        session_id = str(uuid.uuid4())
        mil_activity = []
        for _ in range(random.randint(2, 10)):
            atype = random.choice(["RC-135", "P-8A", "U-2", "RQ-4", "E-3"])
            info = _AIRCRAFT_TYPES[atype]
            mil_activity.append({
                "aircraft": info["name"],
                "category": info["category"],
                "callsign": random.choice(list(_MILITARY_CALLSIGNS.keys())) + str(random.randint(10, 99)),
                "mission_type": _MILITARY_CALLSIGNS.get(
                    random.choice(list(_MILITARY_CALLSIGNS.keys())), "Unknown"),
                "first_seen": (datetime.utcnow() - timedelta(hours=random.randint(1, hours))).isoformat(),
                "orbit_area": f"~{random.randint(50, 300)}km from border",
                "significance": random.choice(["ROUTINE", "ELEVATED", "HIGH", "CRITICAL"]),
            })

        return {
            "session_id": session_id,
            "region": region,
            "period_hours": hours,
            "military_activity_count": len(mil_activity),
            "activities": mil_activity,
            "intel_summary": f"{len(mil_activity)} mouvements militaires détectés — {region}",
            "nato_assets": sum(1 for a in mil_activity if "USAF" in a["mission_type"] or "NATO" in a["mission_type"]),
            "simulated": True,
        }

    def squawk_alert(self, squawk: str = "7700") -> Dict:
        """Alerter sur codes squawk d'urgence actifs."""
        meaning = _SQUAWK_CODES.get(squawk, "Unknown")
        active = []
        if squawk in ["7500", "7600", "7700"]:
            for _ in range(random.randint(0, 3)):
                a = _gen_aircraft()
                a["squawk"] = squawk
                active.append(a)
        return {
            "squawk": squawk, "meaning": meaning,
            "active_aircraft": active,
            "alert_level": "CRITICAL" if squawk == "7500" else "HIGH" if squawk in ["7600", "7700"] else "INFO",
            "simulated": True,
        }
