"""
Missile Defense Simulation — Bloc 13 Neutralisation
Systèmes ABM, SAM, contre-mesures, simulation d'engagement.
100% simulation — aucun matériel réel contrôlé.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ENGAGEMENTS: Dict[str, Dict] = {}
_TRACKS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/neutralization/missile_defense")
_OUTPUT.mkdir(parents=True, exist_ok=True)

SAM_SYSTEMS = {
    "patriot_pac3":  {"max_range_km": 70,  "max_alt_km": 20, "type": "ABM/SAM", "nation": "US",
                      "intercept_pk": 0.85, "reload_min": 45, "targets": "SRBM,MRBM,aircraft,cruise"},
    "s400":          {"max_range_km": 400, "max_alt_km": 35, "type": "SAM",     "nation": "Russia",
                      "intercept_pk": 0.80, "reload_min": 30, "targets": "aircraft,cruise,SRBM"},
    "s500":          {"max_range_km": 600, "max_alt_km": 200,"type": "ABM/SAM", "nation": "Russia",
                      "intercept_pk": 0.88, "reload_min": 60, "targets": "MRBM,ICBM,aircraft,satellites"},
    "thaad":         {"max_range_km": 200, "max_alt_km": 150,"type": "ABM",     "nation": "US",
                      "intercept_pk": 0.90, "reload_min": 90, "targets": "MRBM,SRBM"},
    "arrow3":        {"max_range_km": 2400,"max_alt_km": 500,"type": "ABM",     "nation": "Israel",
                      "intercept_pk": 0.92, "reload_min": 120,"targets": "MRBM,ICBM,ASAT"},
    "iron_dome":     {"max_range_km": 70,  "max_alt_km": 10, "type": "SHORAD",  "nation": "Israel",
                      "intercept_pk": 0.90, "reload_min": 5,  "targets": "rockets,mortars,cruise"},
    "aster_30":      {"max_range_km": 120, "max_alt_km": 25, "type": "SAM",     "nation": "France/UK",
                      "intercept_pk": 0.80, "reload_min": 20, "targets": "aircraft,cruise,SRBM"},
    "aster_30_b1nt": {"max_range_km": 150, "max_alt_km": 35, "type": "ABM/SAM", "nation": "France",
                      "intercept_pk": 0.85, "reload_min": 30, "targets": "SRBM,aircraft,cruise"},
    "nasams":        {"max_range_km": 25,  "max_alt_km": 15, "type": "SHORAD",  "nation": "US/Norway",
                      "intercept_pk": 0.82, "reload_min": 10, "targets": "aircraft,cruise,UAV"},
    "crotale_ng":    {"max_range_km": 11,  "max_alt_km": 6,  "type": "VSHORAD", "nation": "France",
                      "intercept_pk": 0.78, "reload_min": 5,  "targets": "aircraft,UAV,cruise"},
}

THREAT_CLASSES = {
    "SRBM":     {"range_km": (300,1000),  "speed_mach": (4,7),   "rcs_m2": 0.05, "pk_modifier": 0.85},
    "MRBM":     {"range_km": (1000,3000), "speed_mach": (8,12),  "rcs_m2": 0.05, "pk_modifier": 0.75},
    "ICBM":     {"range_km": (5500,14000),"speed_mach": (20,25), "rcs_m2": 0.1,  "pk_modifier": 0.40},
    "cruise":   {"range_km": (500,3000),  "speed_mach": (0.7,1), "rcs_m2": 0.01, "pk_modifier": 0.90},
    "hypersonic":{"range_km":(1000,8000), "speed_mach": (5,25),  "rcs_m2": 0.02, "pk_modifier": 0.30},
    "aircraft": {"range_km": (500,5000),  "speed_mach": (0.8,2.5),"rcs_m2": 2.0, "pk_modifier": 0.92},
    "UAV":      {"range_km": (50,500),    "speed_mach": (0.1,0.5),"rcs_m2": 0.001,"pk_modifier": 0.85},
    "swarm_UAV":{"range_km": (10,100),    "speed_mach": (0.1,0.3),"rcs_m2": 0.001,"pk_modifier": 0.60},
}

COUNTERMEASURES = {
    "kinetic_intercept":  "KKV/fragmentation warhead — direct hit or proximity fuze",
    "direct_energy":      "High-Energy Laser (HEL) — C-UAS, speed-of-light engagement",
    "electronic_jamming": "Jam uplink/GPS guidance — disrupt terminal guidance",
    "chaff_flare":        "Passive CM — IR flares for IR-guided missiles, chaff for radar",
    "active_decoy":       "Towed decoy or expendable active jammer",
    "hard_kill_hpem":     "High Power EM pulse — fuse/electronics kill at range",
    "cyber_uplink":       "Uplink compromise — send destruct command to missile guidance",
}


class MissileDefenseService:

    def __init__(self):
        self.is_simulation = True

    def list_sam_systems(self) -> Dict:
        return {k: {**v, "is_simulation": True} for k, v in SAM_SYSTEMS.items()}

    def list_threat_classes(self) -> Dict:
        return {k: {**v, "is_simulation": True} for k, v in THREAT_CLASSES.items()}

    def list_countermeasures(self) -> Dict:
        return COUNTERMEASURES

    def track_threat(self, threat_type: str, launch_lat: float, launch_lon: float,
                      target_lat: float, target_lon: float) -> Dict:
        threat = THREAT_CLASSES.get(threat_type, THREAT_CLASSES["SRBM"])
        track_id = f"trk_{uuid.uuid4().hex[:8]}"

        dist_km = math.sqrt((target_lat - launch_lat)**2 + (target_lon - launch_lon)**2) * 111
        speed_mach = random.uniform(*threat["speed_mach"])
        speed_ms = speed_mach * 340
        flight_time_s = (dist_km * 1000) / speed_ms

        track = {
            "track_id":     track_id,
            "threat_type":  threat_type,
            "launch_lat":   launch_lat, "launch_lon": launch_lon,
            "target_lat":   target_lat, "target_lon": target_lon,
            "distance_km":  round(dist_km, 1),
            "speed_mach":   round(speed_mach, 1),
            "flight_time_s": round(flight_time_s, 0),
            "time_to_impact": (datetime.utcnow().timestamp() + flight_time_s),
            "current_lat":  round(launch_lat + (target_lat - launch_lat) * random.uniform(0.1, 0.5), 4),
            "current_lon":  round(launch_lon + (target_lon - launch_lon) * random.uniform(0.1, 0.5), 4),
            "altitude_km":  round(random.uniform(10, 500) if "ICBM" in threat_type else random.uniform(1, 50), 1),
            "rcs_m2":       threat["rcs_m2"],
            "status":       "INBOUND",
            "is_simulation": True,
        }
        _TRACKS[track_id] = track
        return track

    def engage_threat(self, track_id: str, sam_system: str,
                       salvo_size: int = 2) -> Dict:
        track = _TRACKS.get(track_id)
        if not track:
            return {"error": "track_not_found"}
        sam = SAM_SYSTEMS.get(sam_system)
        if not sam:
            return {"error": "sam_system_not_found"}

        threat_class = THREAT_CLASSES.get(track["threat_type"], THREAT_CLASSES["SRBM"])
        pk_single = sam["intercept_pk"] * threat_class["pk_modifier"]
        pk_salvo  = 1 - (1 - pk_single) ** salvo_size
        intercept = random.random() < pk_salvo

        engagement_id = f"eng_{uuid.uuid4().hex[:8]}"
        result = {
            "engagement_id":   engagement_id,
            "track_id":        track_id,
            "sam_system":      sam_system,
            "salvo_size":      salvo_size,
            "pk_single":       round(pk_single, 3),
            "pk_salvo":        round(pk_salvo, 3),
            "intercept_success": intercept,
            "intercept_altitude_km": round(random.uniform(5, sam["max_alt_km"]), 1) if intercept else None,
            "intercept_range_km":   round(random.uniform(5, sam["max_range_km"]), 1) if intercept else None,
            "track_status":    "DESTROYED" if intercept else "LEAKER",
            "reload_time_min": sam["reload_min"],
            "is_simulation":   True,
        }
        _TRACKS[track_id]["status"] = "DESTROYED" if intercept else "LEAKER"
        _ENGAGEMENTS[engagement_id] = result
        return result

    def multi_layer_defense(self, threat_type: str, available_systems: Optional[List[str]] = None) -> Dict:
        systems = available_systems or ["thaad", "patriot_pac3", "aster_30", "nasams"]
        threat = THREAT_CLASSES.get(threat_type, THREAT_CLASSES["SRBM"])
        layers = []
        surviving_prob = 1.0
        for sys_name in systems:
            sam = SAM_SYSTEMS.get(sys_name, {})
            if not sam:
                continue
            pk_layer = sam["intercept_pk"] * threat["pk_modifier"]
            pre_layer_prob = surviving_prob
            surviving_prob *= (1 - pk_layer)
            layers.append({
                "layer":        sys_name,
                "intercept_pk": round(pk_layer, 3),
                "cumulative_kill_prob": round(1 - surviving_prob, 3),
                "altitude_window_km": [5, sam["max_alt_km"]],
                "range_km":     sam["max_range_km"],
            })
        return {
            "threat_type":       threat_type,
            "layers":            layers,
            "total_systems":     len(layers),
            "final_kill_prob":   round(1 - surviving_prob, 4),
            "leakage_prob":      round(surviving_prob, 4),
            "expected_leakers":  round(surviving_prob * 10, 1),
            "recommendation":    "ADEQUATE" if (1 - surviving_prob) > 0.90 else "INSUFFICIENT — add layers",
            "is_simulation":     True,
        }

    def countermeasure_effectiveness(self, threat_type: str, cm_type: str) -> Dict:
        base_eff = {
            "kinetic_intercept":  0.85,
            "direct_energy":      0.95 if threat_type in ["UAV","swarm_UAV","cruise"] else 0.30,
            "electronic_jamming": 0.60 if "cruise" in threat_type else 0.20,
            "chaff_flare":        0.50,
            "active_decoy":       0.55,
            "hard_kill_hpem":     0.70 if threat_type in ["cruise","UAV"] else 0.40,
            "cyber_uplink":       0.30,
        }
        eff = base_eff.get(cm_type, 0.50)
        eff *= THREAT_CLASSES.get(threat_type, {}).get("pk_modifier", 0.80)
        return {
            "threat_type":     threat_type,
            "countermeasure":  cm_type,
            "description":     COUNTERMEASURES.get(cm_type, ""),
            "effectiveness_pk": round(min(0.99, eff), 3),
            "limitations":     f"Degraded against fast/small/stealthy targets",
            "is_simulation":   True,
        }

    def saturation_analysis(self, num_threats: int, sam_systems: List[str]) -> Dict:
        total_interceptors = sum(SAM_SYSTEMS[s].get("intercept_pk", 0.8) * 2
                                  for s in sam_systems if s in SAM_SYSTEMS)
        reload_bottleneck = min((SAM_SYSTEMS[s]["reload_min"] for s in sam_systems if s in SAM_SYSTEMS), default=999)
        return {
            "incoming_threats": num_threats,
            "defense_systems":  sam_systems,
            "engageable":       min(num_threats, int(total_interceptors)),
            "saturation_reached": num_threats > total_interceptors,
            "expected_leakers": max(0, num_threats - int(total_interceptors)),
            "reload_time_min":  reload_bottleneck,
            "recommendation":   "Engage priority threats first — radar emitters, C2 nodes" if num_threats > total_interceptors else "Sufficient capacity",
            "is_simulation":    True,
        }

    def get_engagement(self, engagement_id: str) -> Dict:
        return _ENGAGEMENTS.get(engagement_id, {"error": "not_found"})

    def list_tracks(self) -> Dict:
        return {"tracks": list(_TRACKS.values()), "total": len(_TRACKS), "is_simulation": True}
