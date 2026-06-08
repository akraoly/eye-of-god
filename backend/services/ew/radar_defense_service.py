"""
Radar Defense Service — Bloc 11 EW
Détection, classification, contre-mesures radar.
Simulation uniquement.
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

_RADAR_CONTACTS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/ew/radar")
_OUTPUT.mkdir(parents=True, exist_ok=True)

RADAR_TYPES = {
    "surveillance_atc":     {"band": "L/S", "freq_ghz": (1.0, 3.9), "prf_hz": (300, 1200),   "pw_us": (1, 5),   "threat": "LOW",    "notes": "ATC primary surveillance"},
    "military_ew":          {"band": "L",   "freq_ghz": (1.0, 2.0), "prf_hz": (200, 400),    "pw_us": (5, 20),  "threat": "MEDIUM", "notes": "Early warning"},
    "fire_control_xband":   {"band": "X",   "freq_ghz": (8.0,12.0), "prf_hz": (5000,20000),  "pw_us": (0.1,1),  "threat": "CRITICAL","notes": "Missile guidance"},
    "fire_control_kband":   {"band": "Ku",  "freq_ghz": (12.0,18.0),"prf_hz": (5000,20000),  "pw_us": (0.05,.5),"threat": "CRITICAL","notes": "AAA fire control"},
    "weather_sband":        {"band": "S/C", "freq_ghz": (2.7, 5.6), "prf_hz": (300, 1300),   "pw_us": (1, 4),   "threat": "LOW",    "notes": "Weather surveillance"},
    "navigation_marine":    {"band": "X",   "freq_ghz": (9.0, 9.5), "prf_hz": (1000, 4000),  "pw_us": (0.05,1), "threat": "LOW",    "notes": "Marine navigation"},
    "phased_array_aesa":    {"band": "Multi","freq_ghz":(2.0,18.0), "prf_hz": (100,100000),  "pw_us": (0.01,10),"threat": "CRITICAL","notes": "AESA — beam steering, LPI"},
    "airborne_aew":         {"band": "L/S", "freq_ghz": (1.0, 3.5), "prf_hz": (300, 1500),   "pw_us": (2, 10),  "threat": "HIGH",   "notes": "E-3 Sentry/A-50 type"},
    "gpr":                  {"band": "VHF", "freq_ghz": (0.1, 3.0), "prf_hz": (1000,50000),  "pw_us": (0.001,1),"threat": "LOW",    "notes": "Ground penetrating"},
}

JAMMING_TECHNIQUES = {
    "noise_spot":        "Narrow-band noise at exact radar frequency — high J/S ratio",
    "noise_barrage":     "Wide-band noise across radar band — lower J/S but covers hops",
    "sweep":             "Frequency sweep across radar band",
    "deception_rgpo":    "Range Gate Pull-Off — false target at same bearing, drifting range",
    "deception_vgpo":    "Velocity Gate Pull-Off — false doppler then drift",
    "false_targets":     "Multiple false echoes at different ranges and bearings",
    "cross_pol":         "Cross-polarization — exploits antenna polarization sensitivity",
    "smart_noise":       "Noise adapted to PRF and pulse width — reactive jamming",
    "mainlobe_deception":"Deceptive signal in main lobe — highest effectiveness",
    "sidelobe_blanking": "Exploit sidelobe blanking vulnerabilities",
}


class RadarService:

    def __init__(self):
        self.is_simulation = True

    def detect_radar_emissions(self, start_freq: float = 1.0, end_freq: float = 18.0) -> Dict:
        detected = []
        for rtype, params in RADAR_TYPES.items():
            fmin, fmax = params["freq_ghz"]
            if fmin > end_freq or fmax < start_freq:
                continue
            if random.random() > 0.55:
                freq = round(random.uniform(max(fmin, start_freq), min(fmax, end_freq)), 3)
                pmin, pmax = params["prf_hz"]
                pwmin, pwmax = params["pw_us"]
                contact = {
                    "radar_id":     f"radar_{uuid.uuid4().hex[:6]}",
                    "type":         rtype,
                    "band":         params["band"],
                    "freq_ghz":     freq,
                    "prf_hz":       round(random.uniform(pmin, pmax), 0),
                    "pulse_width_us": round(random.uniform(pwmin, pwmax), 3),
                    "scan_pattern": random.choice(["circular", "sector", "stare", "track"]),
                    "power_dbm":    round(random.uniform(50, 90), 0),
                    "rssi_dbm":     round(random.uniform(-80, -20), 0),
                    "threat_level": params["threat"],
                    "notes":        params["notes"],
                    "bearing_deg":  round(random.uniform(0, 360), 0),
                    "distance_km":  round(random.uniform(5, 300), 0),
                    "detected_at":  datetime.utcnow().isoformat(),
                    "is_simulation": True,
                }
                _RADAR_CONTACTS[contact["radar_id"]] = contact
                detected.append(contact)
        return {"scan_range_ghz": [start_freq, end_freq], "detected": detected,
                "count": len(detected), "is_simulation": True}

    def classify_radar(self, radar_id: str) -> Dict:
        contact = _RADAR_CONTACTS.get(radar_id)
        if not contact:
            return {"error": "not_found"}
        rt = RADAR_TYPES.get(contact["type"], {})
        return {
            "radar_id":    radar_id,
            "classification": contact["type"],
            "threat_level":   rt.get("threat", "UNKNOWN"),
            "notes":          rt.get("notes", ""),
            "lpi_probability": round(random.uniform(0.1, 0.9), 2),
            "is_simulation": True,
        }

    def noise_jamming(self, radar_id: str, waveform: str = "noise_spot") -> Dict:
        contact = _RADAR_CONTACTS.get(radar_id)
        if not contact:
            return {"error": "not_found"}
        j_s_ratio = round(random.uniform(10, 40), 1)
        return {
            "radar_id":      radar_id,
            "technique":     waveform,
            "description":   JAMMING_TECHNIQUES.get(waveform, ""),
            "freq_ghz":      contact["freq_ghz"],
            "j_s_ratio_db":  j_s_ratio,
            "effectiveness": "HIGH" if j_s_ratio > 25 else ("MEDIUM" if j_s_ratio > 15 else "LOW"),
            "required_power_w": round(10 ** ((j_s_ratio + contact["rssi_dbm"] - 30) / 10), 2),
            "is_simulation": True,
        }

    def deception_jamming(self, radar_id: str, technique: str = "deception_rgpo",
                          delay_time_us: float = 5.0, doppler_shift_hz: float = 500.0) -> Dict:
        contact = _RADAR_CONTACTS.get(radar_id)
        if not contact:
            return {"error": "not_found"}
        return {
            "radar_id":       radar_id,
            "technique":      technique,
            "description":    JAMMING_TECHNIQUES.get(technique, ""),
            "delay_us":       delay_time_us,
            "false_range_km": round(delay_time_us * 0.15, 1),
            "doppler_shift_hz": doppler_shift_hz,
            "false_velocity_ms": round(doppler_shift_hz * 3e8 / (2 * contact["freq_ghz"] * 1e9), 1),
            "jamming_active": True,
            "is_simulation":  True,
        }

    def false_target_generation(self, radar_id: str, num_targets: int = 10) -> Dict:
        contact = _RADAR_CONTACTS.get(radar_id)
        if not contact:
            return {"error": "not_found"}
        targets = []
        for i in range(num_targets):
            targets.append({
                "index":       i+1,
                "range_km":    round(random.uniform(10, 200), 1),
                "bearing_deg": round(random.uniform(0, 360), 0),
                "velocity_ms": round(random.uniform(-300, 300), 0),
                "rcs_m2":      round(random.uniform(0.5, 50), 1),
            })
        return {
            "radar_id":      radar_id,
            "false_targets": targets,
            "count":         num_targets,
            "description":   JAMMING_TECHNIQUES["false_targets"],
            "is_simulation": True,
        }

    def chaff_dispense_sim(self, location_lat: float, location_lon: float,
                            wind_vector: Optional[Dict] = None) -> Dict:
        wind = wind_vector or {"direction_deg": random.randint(0, 360), "speed_ms": random.uniform(2, 15)}
        return {
            "deploy_lat":  location_lat,
            "deploy_lon":  location_lon,
            "wind":        wind,
            "cloud_width_m":  round(random.uniform(200, 800), 0),
            "cloud_height_m": round(random.uniform(100, 1000), 0),
            "effective_duration_s": round(random.uniform(30, 300), 0),
            "radar_bands_covered": random.sample(["L","S","C","X","Ku"], k=3),
            "rcs_enhancement_db":  round(random.uniform(10, 30), 1),
            "is_simulation": True,
        }

    def threat_assessment(self, radar_list: Optional[List[str]] = None) -> Dict:
        contacts = list(_RADAR_CONTACTS.values()) if not radar_list else \
                   [_RADAR_CONTACTS[r] for r in radar_list if r in _RADAR_CONTACTS]
        critical = [c for c in contacts if c.get("threat_level") == "CRITICAL"]
        high     = [c for c in contacts if c.get("threat_level") == "HIGH"]
        return {
            "total_contacts": len(contacts),
            "critical":       len(critical),
            "high":           len(high),
            "medium":         len([c for c in contacts if c.get("threat_level") == "MEDIUM"]),
            "low":            len([c for c in contacts if c.get("threat_level") == "LOW"]),
            "overall_threat": "CRITICAL" if critical else ("HIGH" if high else "MEDIUM" if contacts else "LOW"),
            "priority_targets": [c["radar_id"] for c in critical[:3]],
            "recommended_action": "Activate multi-band noise jamming + chaff deployment" if critical else "Maintain surveillance",
            "is_simulation": True,
        }

    def radar_silence_mode(self) -> Dict:
        return {
            "mode":    "EMCON",
            "status":  "active",
            "all_tx_disabled": True,
            "passive_only":    True,
            "note":    "Emissions Control — no RF transmissions. Passive sensors only.",
        }

    def analyze_radar_lobes(self, radar_id: str) -> Dict:
        contact = _RADAR_CONTACTS.get(radar_id)
        if not contact:
            return {"error": "not_found"}
        return {
            "radar_id":         radar_id,
            "main_lobe_width_deg": round(random.uniform(1.5, 15), 1),
            "first_sidelobe_db": round(random.uniform(-15, -25), 1),
            "prf_hz":           contact.get("prf_hz", 1000),
            "pulse_width_us":   contact.get("pulse_width_us", 1),
            "duty_cycle_pct":   round(contact.get("prf_hz", 1000) * contact.get("pulse_width_us", 1) * 1e-6 * 100, 3),
            "range_resolution_m": round(150 / contact.get("prf_hz", 1000), 0),
            "is_simulation":    True,
        }

    def list_contacts(self) -> Dict:
        return {"contacts": list(_RADAR_CONTACTS.values()), "total": len(_RADAR_CONTACTS)}

    def list_jamming_techniques(self) -> Dict:
        return JAMMING_TECHNIQUES

    def list_radar_types(self) -> Dict:
        return {k: {"band": v["band"], "freq_ghz": v["freq_ghz"], "threat": v["threat"], "notes": v["notes"]}
                for k, v in RADAR_TYPES.items()}
