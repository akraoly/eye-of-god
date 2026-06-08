"""
ASAT — Anti-Satellite Warfare Service
KE interceptors, laser dazzling/blinding, co-orbital, microwave DEW.
Simulation uniquement — aucune interaction matériel réel.
"""
import uuid, random, math
from datetime import datetime, timezone, timedelta
from pathlib import Path

Path("./data/space_warfare").mkdir(parents=True, exist_ok=True)

ASAT_METHODS = {
    "ke_interceptor": {
        "name": "Kinetic Energy Interceptor",
        "description": "Direct-ascent ballistic missile with KE kill vehicle",
        "altitude_limit_km": 2000,
        "warning_time_min": 15,
        "debris_risk": "CATASTROPHIC",
        "nations": ["USA", "RUS", "CHN", "IND"],
    },
    "laser_dazzle": {
        "name": "Laser Dazzling",
        "description": "Temporary sensor blinding — reversible",
        "altitude_limit_km": 36000,
        "warning_time_min": 0,
        "debris_risk": "NONE",
        "nations": ["USA", "RUS", "CHN", "FRA"],
    },
    "laser_blind": {
        "name": "Laser Blinding",
        "description": "Permanent optical sensor destruction",
        "altitude_limit_km": 36000,
        "warning_time_min": 0,
        "debris_risk": "NONE",
        "nations": ["USA", "RUS", "CHN"],
    },
    "co_orbital": {
        "name": "Co-Orbital Interceptor",
        "description": "Satellite with maneuvering kill vehicle — rendezvous & proximity ops",
        "altitude_limit_km": 36000,
        "warning_time_min": 1440,
        "debris_risk": "HIGH",
        "nations": ["USA", "RUS", "CHN"],
    },
    "co_orbital_shadow": {
        "name": "Co-Orbital Shadowing",
        "description": "Persistent proximity surveillance / electronic attack",
        "altitude_limit_km": 36000,
        "warning_time_min": 2880,
        "debris_risk": "LOW",
        "nations": ["USA", "RUS", "CHN"],
    },
    "microwave_dew": {
        "name": "High-Power Microwave DEW",
        "description": "Electronics disruption via HPM pulse",
        "altitude_limit_km": 2000,
        "warning_time_min": 0,
        "debris_risk": "NONE",
        "nations": ["USA", "RUS", "CHN"],
    },
    "cyberattack": {
        "name": "Cyber Attack on Satellite C2",
        "description": "Ground segment intrusion / uplink spoofing / command injection",
        "altitude_limit_km": 99999,
        "warning_time_min": 0,
        "debris_risk": "NONE",
        "nations": ["USA", "RUS", "CHN", "PRK", "IRN"],
    },
    "nuclear_emp": {
        "name": "Nuclear EMP (High-Altitude)",
        "description": "HEMP — destroys all LEO satellites in affected bands",
        "altitude_limit_km": 500,
        "warning_time_min": 5,
        "debris_risk": "CATASTROPHIC",
        "nations": ["USA", "RUS", "CHN"],
    },
}

SATELLITE_TARGETS = [
    {"norad_id": 25544, "name": "ISS", "type": "space_station", "altitude_km": 408,  "orbit": "LEO", "nation": "INT", "military": False},
    {"norad_id": 43013, "name": "USA-281 (KH-11)",  "type": "recon_optical", "altitude_km": 320,  "orbit": "LEO", "nation": "USA", "military": True},
    {"norad_id": 44937, "name": "USA-290 (KH-11)",  "type": "recon_optical", "altitude_km": 295,  "orbit": "LEO", "nation": "USA", "military": True},
    {"norad_id": 37601, "name": "Lacrosse-5 (SAR)", "type": "recon_radar",   "altitude_km": 710,  "orbit": "LEO", "nation": "USA", "military": True},
    {"norad_id": 39232, "name": "NROL-39",          "type": "sigint",        "altitude_km": 1000, "orbit": "LEO", "nation": "USA", "military": True},
    {"norad_id": 43641, "name": "Kosmos-2530",      "type": "recon_optical", "altitude_km": 480,  "orbit": "LEO", "nation": "RUS", "military": True},
    {"norad_id": 44903, "name": "Kosmos-2543",      "type": "co_orbital_inspector", "altitude_km": 550, "orbit": "LEO", "nation": "RUS", "military": True},
    {"norad_id": 45026, "name": "Yaogan-31C",       "type": "sigint_cluster","altitude_km": 1100, "orbit": "LEO", "nation": "CHN", "military": True},
    {"norad_id": 44703, "name": "Shiyan-6",         "type": "co_orbital",    "altitude_km": 600,  "orbit": "LEO", "nation": "CHN", "military": True},
    {"norad_id": 46826, "name": "CSO-2 (Pléiades)", "type": "recon_optical", "altitude_km": 480,  "orbit": "SSO", "nation": "FRA", "military": True},
    {"norad_id": 27651, "name": "GPS IIR-11",       "type": "navigation",    "altitude_km": 20200,"orbit": "MEO", "nation": "USA", "military": False},
    {"norad_id": 37256, "name": "GLONASS-M 730",    "type": "navigation",    "altitude_km": 19100,"orbit": "MEO", "nation": "RUS", "military": False},
    {"norad_id": 40128, "name": "Beidou-3 IGSO-1",  "type": "navigation",    "altitude_km": 35786,"orbit": "GEO", "nation": "CHN", "military": False},
    {"norad_id": 41866, "name": "WGS-9",            "type": "military_comms","altitude_km": 35786,"orbit": "GEO", "nation": "USA", "military": True},
    {"norad_id": 44235, "name": "Starlink-1007",    "type": "broadband_leo", "altitude_km": 550,  "orbit": "LEO", "nation": "USA", "military": False},
]

_intercept_missions: dict = {}


def _threat_level(sat: dict, method: str) -> str:
    m = ASAT_METHODS.get(method, {})
    if sat["altitude_km"] > m.get("altitude_limit_km", 0):
        return "OUT_OF_RANGE"
    if sat["military"]:
        return "HIGH_VALUE"
    return "STRATEGIC"


class AsatService:

    def list_methods(self):
        return {"asat_methods": list(ASAT_METHODS.values()), "total": len(ASAT_METHODS)}

    def list_satellites(self, orbit_filter: str = None, military_only: bool = False):
        sats = SATELLITE_TARGETS
        if orbit_filter:
            sats = [s for s in sats if s["orbit"] == orbit_filter.upper()]
        if military_only:
            sats = [s for s in sats if s["military"]]
        return {"satellites": sats, "total": len(sats), "is_simulation": True}

    def assess_target(self, norad_id: int):
        sat = next((s for s in SATELLITE_TARGETS if s["norad_id"] == norad_id), None)
        if not sat:
            return {"error": "not_found", "norad_id": norad_id}
        viable = [m for m, d in ASAT_METHODS.items() if sat["altitude_km"] <= d["altitude_limit_km"]]
        return {
            "satellite": sat,
            "viable_methods": viable,
            "threat_level": "HIGH_VALUE" if sat["military"] else "STRATEGIC",
            "orbital_period_min": round(2 * math.pi * math.sqrt(((6371 + sat["altitude_km"]) * 1000) ** 3 / (3.986e14)) / 60, 1),
            "next_pass_estimate_min": random.randint(20, 110),
            "is_simulation": True,
        }

    def plan_intercept(self, norad_id: int, method: str, authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        sat = next((s for s in SATELLITE_TARGETS if s["norad_id"] == norad_id), None)
        if not sat:
            return {"error": "not_found"}
        m = ASAT_METHODS.get(method)
        if not m:
            return {"error": "unknown_method"}
        if sat["altitude_km"] > m["altitude_limit_km"]:
            return {"error": "out_of_range", "max_km": m["altitude_limit_km"], "target_km": sat["altitude_km"]}

        mission_id = f"ASAT-{uuid.uuid4().hex[:8].upper()}"
        debris_count = random.randint(500, 3000) if m["debris_risk"] == "CATASTROPHIC" else \
                       random.randint(50, 200) if m["debris_risk"] == "HIGH" else 0
        _intercept_missions[mission_id] = {
            "mission_id": mission_id,
            "target": sat,
            "method": method,
            "method_details": m,
            "status": "PLANNED",
            "pk": round(random.uniform(0.72, 0.97), 3),
            "tof_min": random.randint(8, 45),
            "debris_objects": debris_count,
            "planned_at": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }
        return _intercept_missions[mission_id]

    def execute_intercept(self, mission_id: str, authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        m = _intercept_missions.get(mission_id)
        if not m:
            return {"error": "not_found"}
        m["status"] = "EXECUTED"
        m["executed_at"] = datetime.now(timezone.utc).isoformat()
        m["intercept_success"] = random.random() < m["pk"]
        m["kill_assessment"] = "CONFIRMED_KILL" if m["intercept_success"] else "MISS — retargeting"
        return m

    def list_missions(self):
        return {"missions": list(_intercept_missions.values()), "total": len(_intercept_missions)}

    def debris_analysis(self, norad_id: int, method: str):
        sat = next((s for s in SATELLITE_TARGETS if s["norad_id"] == norad_id), None)
        if not sat:
            return {"error": "not_found"}
        m = ASAT_METHODS.get(method, {})
        debris_risk = m.get("debris_risk", "UNKNOWN")
        count = random.randint(1000, 3500) if debris_risk == "CATASTROPHIC" else \
                random.randint(50, 300) if debris_risk == "HIGH" else \
                random.randint(5, 30) if debris_risk == "LOW" else 0
        return {
            "norad_id": norad_id,
            "method": method,
            "debris_risk_level": debris_risk,
            "estimated_debris_objects": count,
            "affected_shells_km": [sat["altitude_km"] - 50, sat["altitude_km"] + 150] if count > 0 else [],
            "kessler_risk": debris_risk in ("CATASTROPHIC", "HIGH"),
            "deorbit_years": round(max(0, (sat["altitude_km"] - 200) / 40), 1),
            "affected_operators": random.randint(3, 12) if debris_risk == "CATASTROPHIC" else 0,
            "is_simulation": True,
        }
