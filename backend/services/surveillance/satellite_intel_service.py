"""
Satellite Intelligence Service — Bloc 12 Surveillance Stratégique
Suivi orbites, ISR optique/SAR/SIGINT satellite, prédiction passages.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SATELLITE_DB: Dict[str, Dict] = {}
_PASSES: Dict[str, Dict] = {}
_OUTPUT = Path("./data/surveillance/satellite")
_OUTPUT.mkdir(parents=True, exist_ok=True)

KNOWN_SATELLITES = {
    "SENTINEL_2A":  {"norad": 40697, "type": "EO",    "res_m": 10,  "revisit_days": 5,  "owner": "ESA",    "orbit": "SSO"},
    "SENTINEL_1A":  {"norad": 39634, "type": "SAR",   "res_m": 5,   "revisit_days": 12, "owner": "ESA",    "orbit": "SSO"},
    "PLEIADES_1A":  {"norad": 38012, "type": "EO",    "res_m": 0.5, "revisit_days": 1,  "owner": "CNES/Airbus","orbit":"SSO"},
    "PLEIADES_1B":  {"norad": 40053, "type": "EO",    "res_m": 0.5, "revisit_days": 1,  "owner": "CNES/Airbus","orbit":"SSO"},
    "PLEIADES_NEO3":{"norad": 49494, "type": "EO",    "res_m": 0.3, "revisit_days": 1,  "owner": "Airbus", "orbit": "SSO"},
    "WORLDVIEW3":   {"norad": 40115, "type": "EO",    "res_m": 0.31,"revisit_days": 1,  "owner": "Maxar",  "orbit": "SSO"},
    "STARLINK_GEN1":{"norad": 44235, "type": "COMMS", "res_m": None,"revisit_days": 0,  "owner": "SpaceX", "orbit": "LEO"},
    "COSMO_SKYMED": {"norad": 31598, "type": "SAR",   "res_m": 1,   "revisit_days": 1,  "owner": "Italy",  "orbit": "SSO"},
    "LACROSSE_5":   {"norad": 28646, "type": "SAR",   "res_m": 0.3, "revisit_days": 3,  "owner": "NRO",    "orbit": "LEO"},
    "KH_13_USA_245":{"norad": 39232, "type": "OPTICAL","res_m":0.1, "revisit_days": 3,  "owner": "NRO",    "orbit": "LEO"},
    "SPOT6":        {"norad": 38755, "type": "EO",    "res_m": 1.5, "revisit_days": 1,  "owner": "Airbus", "orbit": "SSO"},
    "ICEYE_X2":     {"norad": 43749, "type": "SAR",   "res_m": 1,   "revisit_days": 1,  "owner": "ICEYE",  "orbit": "SSO"},
    "MUSIS_CSO1":   {"norad": 44637, "type": "EO",    "res_m": 0.35,"revisit_days": 2,  "owner": "France DGA","orbit":"SSO"},
    "HELIOS2A":     {"norad": 29297, "type": "EO",    "res_m": 0.35,"revisit_days": 3,  "owner": "France DGA","orbit":"SSO"},
    "NROL_71":      {"norad": 43958, "type": "SIGINT","res_m": None,"revisit_days": 0,  "owner": "NRO",    "orbit": "GEO"},
    "INTRUDER_6":   {"norad": 33274, "type": "SIGINT","res_m": None,"revisit_days": 0,  "owner": "NSA/NRO","orbit": "GEO"},
    "MERIDIAN_5":   {"norad": 36605, "type": "COMMS", "res_m": None,"revisit_days": 0,  "owner": "Russia", "orbit": "HEO"},
    "YAOGAN_30A":   {"norad": 43137, "type": "SIGINT","res_m": None,"revisit_days": 0,  "owner": "China",  "orbit": "LEO"},
}

ORBIT_TYPES = {
    "LEO": {"alt_km": (300, 1200),  "period_min": (90, 105),  "desc": "Low Earth Orbit"},
    "SSO": {"alt_km": (400, 900),   "period_min": (90, 103),  "desc": "Sun-Synchronous Orbit"},
    "MEO": {"alt_km": (2000, 20000),"period_min": (200, 720), "desc": "Medium Earth Orbit"},
    "GEO": {"alt_km": (35786,35786),"period_min": (1440,1440),"desc": "Geostationary Orbit"},
    "HEO": {"alt_km": (500, 40000), "period_min": (700, 720), "desc": "Highly Elliptical Orbit"},
}

SATELLITE_TASKING_MODES = {
    "strip_map":    "Linear strip imaging — high revisit, lower resolution",
    "spotlight":    "Focused area imaging — highest resolution, small footprint",
    "scan_sar":     "SAR wide-area scan — all-weather, day/night",
    "push_broom":   "Continuous nadir strip — pushbroom sensor",
    "stereo":       "Stereo pair — 3D reconstruction / DSM generation",
    "video":        "Persistent video — target motion tracking",
    "night_ir":     "Thermal IR — heat signatures, night ops",
}


class SatelliteIntelService:

    def __init__(self):
        self.is_simulation = True
        self._build_db()

    def _build_db(self):
        for name, data in KNOWN_SATELLITES.items():
            orbit_type = data.get("orbit", "LEO")
            orbit_params = ORBIT_TYPES.get(orbit_type, ORBIT_TYPES["LEO"])
            alt_min, alt_max = orbit_params["alt_km"]
            _SATELLITE_DB[name] = {
                "name":       name,
                "norad_id":   data["norad"],
                "type":       data["type"],
                "owner":      data["owner"],
                "orbit_type": orbit_type,
                "altitude_km": round(random.uniform(alt_min, alt_max), 0),
                "inclination_deg": round(random.uniform(60, 98) if orbit_type == "SSO" else random.uniform(0, 98), 1),
                "resolution_m":    data.get("res_m"),
                "revisit_days":    data.get("revisit_days"),
                "status":     random.choice(["OPERATIONAL","OPERATIONAL","OPERATIONAL","DEGRADED"]),
            }

    def list_satellites(self, sat_type: Optional[str] = None) -> Dict:
        sats = list(_SATELLITE_DB.values())
        if sat_type:
            sats = [s for s in sats if s["type"].upper() == sat_type.upper()]
        return {"satellites": sats, "total": len(sats), "is_simulation": True}

    def get_satellite_detail(self, name: str) -> Dict:
        sat = _SATELLITE_DB.get(name.upper())
        if not sat:
            return {"error": "not_found", "name": name}
        return {**sat, "current_lat": round(random.uniform(-80,80), 3),
                       "current_lon": round(random.uniform(-180,180), 3),
                       "is_simulation": True}

    def predict_pass(self, observer_lat: float, observer_lon: float,
                      sat_name: str, time_horizon_hours: int = 24) -> Dict:
        sat = _SATELLITE_DB.get(sat_name.upper(), {})
        orbit_type = sat.get("orbit_type", "LEO")
        if orbit_type in ["GEO", "HEO"]:
            return {"error": "GEO/HEO satellite — continuously visible above horizon",
                    "sat_name": sat_name, "is_simulation": True}
        passes = []
        orbit_params = ORBIT_TYPES.get(orbit_type, ORBIT_TYPES["LEO"])
        period_min = random.uniform(*orbit_params["period_min"])
        num_passes = int((time_horizon_hours * 60) / period_min * random.uniform(0.2, 0.8))
        base_time = datetime.utcnow()
        for i in range(num_passes):
            pass_time = base_time + timedelta(minutes=period_min * (i + random.uniform(0.3, 0.9)))
            duration_s = random.randint(240, 600)
            max_el = round(random.uniform(10, 88), 1)
            passes.append({
                "aos": pass_time.isoformat(),
                "los": (pass_time + timedelta(seconds=duration_s)).isoformat(),
                "duration_s":    duration_s,
                "max_elevation_deg": max_el,
                "quality":       "EXCELLENT" if max_el > 60 else ("GOOD" if max_el > 30 else "MARGINAL"),
                "azimuth_aos_deg": round(random.uniform(0, 360), 0),
            })
        pass_id = f"pass_{uuid.uuid4().hex[:8]}"
        result = {
            "pass_id":       pass_id,
            "sat_name":      sat_name,
            "observer_lat":  observer_lat,
            "observer_lon":  observer_lon,
            "time_horizon_h": time_horizon_hours,
            "passes_count":  len(passes),
            "passes":        passes[:10],
            "next_pass":     passes[0] if passes else None,
            "is_simulation": True,
        }
        _PASSES[pass_id] = result
        return result

    def area_coverage_windows(self, lat_min: float, lat_max: float,
                               lon_min: float, lon_max: float,
                               sat_types: Optional[List[str]] = None) -> Dict:
        types = sat_types or ["EO", "SAR"]
        sats = [s for s in _SATELLITE_DB.values()
                if s["type"] in types and s.get("revisit_days", 999) <= 3]
        windows = []
        base_time = datetime.utcnow()
        for sat in sats[:8]:
            pass_time = base_time + timedelta(hours=random.uniform(0, 48))
            windows.append({
                "satellite":     sat["name"],
                "type":          sat["type"],
                "resolution_m":  sat.get("resolution_m"),
                "acquisition_time": pass_time.isoformat(),
                "cloud_cover_pct": round(random.uniform(0, 60), 0),
                "usable":        random.random() > 0.3,
            })
        windows.sort(key=lambda x: x["acquisition_time"])
        return {
            "bbox":    [lat_min, lat_max, lon_min, lon_max],
            "windows": windows,
            "count":   len(windows),
            "next_acquisition": windows[0]["acquisition_time"] if windows else None,
            "is_simulation": True,
        }

    def task_satellite(self, sat_name: str, target_lat: float, target_lon: float,
                        mode: str = "spotlight") -> Dict:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        sat = _SATELLITE_DB.get(sat_name.upper(), {})
        mode_desc = SATELLITE_TASKING_MODES.get(mode, "Unknown mode")
        result = {
            "task_id":       task_id,
            "satellite":     sat_name,
            "target_lat":    target_lat,
            "target_lon":    target_lon,
            "mode":          mode,
            "mode_desc":     mode_desc,
            "resolution_m":  sat.get("resolution_m", 1),
            "estimated_access": (datetime.utcnow() + timedelta(hours=random.uniform(2,24))).isoformat(),
            "priority":      random.choice(["ROUTINE","PRIORITY","URGENT"]),
            "status":        "QUEUED",
            "is_simulation": True,
        }
        return result

    def sar_analysis(self, target_lat: float, target_lon: float,
                      pre_event_date: Optional[str] = None) -> Dict:
        return {
            "target":          {"lat": target_lat, "lon": target_lon},
            "analysis_type":   "SAR Change Detection (Coherence + Intensity)",
            "satellites_used": ["SENTINEL_1A", "COSMO_SKYMED", "ICEYE_X2"],
            "pre_event":       pre_event_date or (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "post_event":      datetime.utcnow().strftime("%Y-%m-%d"),
            "changes_detected": random.randint(0, 15),
            "change_types":    random.sample(["Vehicle movement","Construction","Vegetation change",
                                               "Water level","Soil displacement","Structure damage"], k=3),
            "confidence":      round(random.uniform(0.7, 0.95), 2),
            "is_simulation":   True,
        }

    def isr_collection_plan(self, target_name: str, lat: float, lon: float,
                              priority: str = "HIGH") -> Dict:
        plan_id = f"isr_{uuid.uuid4().hex[:8]}"
        assets = []
        for sat_name, sat in list(_SATELLITE_DB.items())[:6]:
            if sat.get("revisit_days", 999) <= 5:
                assets.append({
                    "asset":         sat_name,
                    "type":          sat["type"],
                    "tasking_window": (datetime.utcnow() + timedelta(hours=random.uniform(1,24))).isoformat(),
                    "resolution_m":  sat.get("resolution_m"),
                    "remarks":       f"Cloud cover forecast: {random.randint(0,50)}%",
                })
        return {
            "plan_id":       plan_id,
            "target_name":   target_name,
            "lat":           lat, "lon": lon,
            "priority":      priority,
            "collection_assets": assets,
            "total_passes":  sum(1 for a in assets),
            "first_collection": assets[0]["tasking_window"] if assets else None,
            "is_simulation": True,
        }

    def list_orbit_types(self) -> Dict:
        return ORBIT_TYPES

    def list_tasking_modes(self) -> Dict:
        return SATELLITE_TASKING_MODES
