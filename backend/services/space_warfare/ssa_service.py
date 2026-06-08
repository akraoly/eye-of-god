"""
SSA — Space Situational Awareness.
Debris tracking, satellite cataloguing, conjunction analysis, maneuver detection.
"""
import uuid, random, math
from datetime import datetime, timezone, timedelta

OBJECT_TYPES = ["payload", "rocket_body", "debris", "unknown", "fragmentation", "co_orbital_inspector"]
ORBIT_SHELLS = {
    "LEO_low":  {"alt_range": [200,  600],  "object_count": 14000},
    "LEO_mid":  {"alt_range": [600,  1200], "object_count": 8500},
    "LEO_high": {"alt_range": [1200, 2000], "object_count": 3200},
    "MEO":      {"alt_range": [2000, 35000],"object_count": 450},
    "GEO_belt": {"alt_range": [35600,36200],"object_count": 1850},
    "GEO_graveyard": {"alt_range": [36200, 37000], "object_count": 320},
    "HEO":      {"alt_range": [500,  50000],"object_count": 260},
}

SENSOR_NETWORK = [
    {"name": "Eglin AN/FPS-85",   "location": "Florida, USA",  "type": "phased_array_radar", "range_km": 4600},
    {"name": "Haystack LRIR",     "location": "Massachusetts", "type": "radar",               "range_km": 900},
    {"name": "GEODSS Diego Garcia","location": "Indian Ocean", "type": "optical",             "range_km": 1000},
    {"name": "GRAVES",            "location": "France",        "type": "bistatic_radar",      "range_km": 2500},
    {"name": "TIRA",              "location": "Germany",       "type": "radar",               "range_km": 800},
    {"name": "Eftelsberg",        "location": "Germany",       "type": "radio_telescope",     "range_km": 2000},
    {"name": "Kourou SST",        "location": "French Guiana", "type": "optical",             "range_km": 1200},
    {"name": "Roscosmos SKKP",    "location": "Russia",        "type": "network",             "range_km": 4000},
    {"name": "PLA SST Net",       "location": "China",         "type": "network",             "range_km": 3500},
]

_tracked_objects: dict = {}
_conjunction_events: list = []


def _gen_object(orbit_shell: str = "LEO_low") -> dict:
    shell = ORBIT_SHELLS.get(orbit_shell, ORBIT_SHELLS["LEO_low"])
    alt = random.uniform(*shell["alt_range"])
    incl = random.uniform(0, 105)
    return {
        "norad_id": random.randint(10000, 99999),
        "name": f"OBJECT {random.randint(1000,9999)}",
        "type": random.choice(OBJECT_TYPES),
        "altitude_km": round(alt, 1),
        "inclination_deg": round(incl, 2),
        "rcs_m2": round(random.uniform(0.001, 10.0), 4),
        "size_class": "LARGE" if alt > 0.1 else "SMALL",
        "nation": random.choice(["USA", "RUS", "CHN", "EU", "UNKNOWN"]),
        "launched": str(random.randint(1970, 2025)),
        "last_tracked": datetime.now(timezone.utc).isoformat(),
    }


class SsaService:

    def get_catalog_stats(self):
        total = sum(s["object_count"] for s in ORBIT_SHELLS.values())
        return {
            "total_tracked_objects": total,
            "shells": ORBIT_SHELLS,
            "sensor_network": SENSOR_NETWORK,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }

    def scan_shell(self, orbit_shell: str = "LEO_low", count: int = 20):
        if orbit_shell not in ORBIT_SHELLS:
            return {"error": "unknown_shell", "available": list(ORBIT_SHELLS.keys())}
        objects = [_gen_object(orbit_shell) for _ in range(min(count, 50))]
        for o in objects:
            _tracked_objects[o["norad_id"]] = o
        return {
            "orbit_shell": orbit_shell,
            "objects_detected": objects,
            "total": len(objects),
            "is_simulation": True,
        }

    def track_object(self, norad_id: int):
        obj = _tracked_objects.get(norad_id) or _gen_object()
        obj["norad_id"] = norad_id
        obj["track_quality"] = random.choice(["NOMINAL", "GOOD", "POOR"])
        obj["position_uncertainty_m"] = round(random.uniform(10, 500), 1)
        obj["velocity_ms"] = round(math.sqrt(3.986e14 / ((6371 + obj["altitude_km"]) * 1000)), 0)
        obj["orbital_period_min"] = round(2 * math.pi * math.sqrt(((6371 + obj["altitude_km"]) * 1000) ** 3 / 3.986e14) / 60, 1)
        _tracked_objects[norad_id] = obj
        return {"object": obj, "is_simulation": True}

    def conjunction_analysis(self, norad_id: int, look_ahead_hours: int = 72):
        obj = _tracked_objects.get(norad_id) or _gen_object()
        conjunctions = []
        n_events = random.randint(0, 5)
        for _ in range(n_events):
            tca = datetime.now(timezone.utc) + timedelta(hours=random.uniform(1, look_ahead_hours))
            miss_m = round(random.uniform(50, 5000), 0)
            conjunctions.append({
                "event_id": f"CONJ-{uuid.uuid4().hex[:6].upper()}",
                "secondary_object": f"COSMOS-{random.randint(1000,9999)}",
                "tca": tca.isoformat(),
                "miss_distance_m": miss_m,
                "pc": round(max(0, 1 / (miss_m * 10)), 8),
                "risk": "RED" if miss_m < 200 else "YELLOW" if miss_m < 1000 else "GREEN",
            })
            _conjunction_events.append(conjunctions[-1])
        return {
            "primary": norad_id,
            "look_ahead_hours": look_ahead_hours,
            "conjunctions": sorted(conjunctions, key=lambda x: x["miss_distance_m"]),
            "maneuver_recommended": any(c["risk"] == "RED" for c in conjunctions),
            "is_simulation": True,
        }

    def detect_maneuver(self, norad_id: int):
        return {
            "norad_id": norad_id,
            "maneuver_detected": random.random() < 0.35,
            "delta_v_ms": round(random.uniform(0.01, 2.5), 3) if random.random() < 0.35 else 0,
            "maneuver_time": (datetime.now(timezone.utc) - timedelta(hours=random.uniform(0, 24))).isoformat(),
            "new_altitude_km": round(random.uniform(300, 600), 1),
            "assessment": random.choice(["EVASIVE", "PROXIMITY_OPS", "STATION_KEEPING", "DEORBIT_PREP"]),
            "is_simulation": True,
        }

    def kessler_risk_assessment(self, altitude_km: float):
        shell_density = max(0, 14000 * math.exp(-((altitude_km - 800) ** 2) / (2 * 300 ** 2)))
        return {
            "altitude_km": altitude_km,
            "object_density_per_km3": round(shell_density / (4 * math.pi * (6371 + altitude_km) ** 2 * 100), 12),
            "collision_probability_per_year": round(shell_density * 1e-9, 8),
            "kessler_risk": "CRITICAL" if altitude_km in range(750, 850) else
                            "HIGH" if altitude_km in range(600, 1000) else
                            "MODERATE" if altitude_km < 1500 else "LOW",
            "fragmentation_cascade_threshold": shell_density > 5000,
            "is_simulation": True,
        }

    def list_conjunctions(self):
        return {"events": _conjunction_events, "total": len(_conjunction_events), "is_simulation": True}

    def anti_ssa(self, norad_id: int, technique: str = "stealth_maneuver"):
        techniques = {
            "stealth_maneuver": "Low-thrust maneuver below sensor threshold",
            "radar_absorb":     "RCS reduction via attitude change / coatings",
            "optical_camouflage": "Anti-reflective coating, tumble rate change",
            "decoy_deploy":     "Deploy decoys to confuse tracking solution",
        }
        return {
            "norad_id": norad_id,
            "technique": technique,
            "description": techniques.get(technique, "Unknown"),
            "detection_degradation_pct": round(random.uniform(40, 90), 1),
            "tracking_break_hours": round(random.uniform(1, 72), 1),
            "is_simulation": True,
        }
