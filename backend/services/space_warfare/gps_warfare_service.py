"""
GPS Warfare — Spoofing, Jamming, Navigation Denial.
Simulation uniquement.
"""
import uuid, random
from datetime import datetime, timezone
from pathlib import Path

Path("./data/space_warfare").mkdir(parents=True, exist_ok=True)

GNSS_SYSTEMS = {
    "gps":     {"nation": "USA", "freq_l1_mhz": 1575.42, "freq_l2_mhz": 1227.60, "freq_l5_mhz": 1176.45, "satellites": 31},
    "glonass": {"nation": "RUS", "freq_l1_mhz": 1602.0,  "freq_l2_mhz": 1246.0,  "freq_l5_mhz": None,    "satellites": 24},
    "beidou":  {"nation": "CHN", "freq_b1_mhz": 1561.098,"freq_b2_mhz": 1207.14, "freq_b3_mhz": 1268.52, "satellites": 48},
    "galileo": {"nation": "EU",  "freq_e1_mhz": 1575.42, "freq_e5_mhz": 1191.795,"freq_e6_mhz": 1278.75, "satellites": 30},
    "navic":   {"nation": "IND", "freq_l5_mhz": 1176.45, "freq_s_mhz": 2492.028, "satellites": 8},
}

JAMMING_TYPES = ["spot_jammer", "swept_jammer", "chirp_jammer", "noise_jammer", "pulsed_jammer"]

SPOOFING_TECHNIQUES = {
    "meaconing": {
        "description": "Rebroadcast authentic GNSS signals with delay → position drift",
        "difficulty": "LOW",
        "detection_risk": "MEDIUM",
    },
    "simplistic_spoof": {
        "description": "Generate false PRN codes with controlled position offset",
        "difficulty": "MEDIUM",
        "detection_risk": "MEDIUM",
    },
    "sophisticated_spoof": {
        "description": "Multi-signal synchronized spoofing with smooth takeover",
        "difficulty": "HIGH",
        "detection_risk": "LOW",
    },
    "relay_attack": {
        "description": "Real-time relay with amplification and phase manipulation",
        "difficulty": "HIGH",
        "detection_risk": "LOW",
    },
    "time_attack": {
        "description": "Clock manipulation only — disrupts crypto/finance/telecom timing",
        "difficulty": "MEDIUM",
        "detection_risk": "LOW",
    },
}

TARGET_CATEGORIES = [
    "military_navigation", "commercial_aviation", "maritime_shipping",
    "precision_agriculture", "financial_timing", "mobile_networks",
    "autonomous_vehicles", "drone_swarms",
]

_spoof_sessions: dict = {}
_jam_sessions: dict = {}


class GpsWarfareService:

    def list_gnss_systems(self):
        return {"systems": GNSS_SYSTEMS, "is_simulation": True}

    def scan_gnss_environment(self, lat: float = 48.85, lon: float = 2.35):
        signals = []
        for sys_name, sys in GNSS_SYSTEMS.items():
            sats_visible = random.randint(4, min(12, sys["satellites"]))
            signals.append({
                "system": sys_name,
                "sats_visible": sats_visible,
                "snr_db": round(random.uniform(28, 52), 1),
                "frequency_mhz": sys.get("freq_l1_mhz") or sys.get("freq_b1_mhz") or sys.get("freq_e1_mhz"),
                "fix_quality": "3D" if sats_visible >= 4 else "NO_FIX",
                "position_accuracy_m": round(random.uniform(0.5, 8.0), 2),
            })
        return {
            "location": {"lat": lat, "lon": lon},
            "gnss_signals": signals,
            "anomalies_detected": random.randint(0, 2),
            "spoofing_indicators": random.random() < 0.1,
            "is_simulation": True,
        }

    def jam_gnss(self, target_system: str, power_w: float, jamming_type: str,
                 authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        sys = GNSS_SYSTEMS.get(target_system.lower())
        if not sys:
            return {"error": "unknown_system", "available": list(GNSS_SYSTEMS.keys())}

        session_id = f"GJAM-{uuid.uuid4().hex[:8].upper()}"
        affected_area_km = round(math.sqrt(power_w) * 1.5, 1) if power_w > 0 else 0
        _jam_sessions[session_id] = {
            "session_id": session_id,
            "target_system": target_system,
            "jamming_type": jamming_type,
            "power_w": power_w,
            "effective_range_km": affected_area_km,
            "target_freq_mhz": sys.get("freq_l1_mhz") or sys.get("freq_b1_mhz"),
            "jnr_db": round(20 * (power_w ** 0.1), 1),
            "status": "ACTIVE",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }
        return _jam_sessions[session_id]

    def spoof_position(self, target_system: str, technique: str,
                       fake_lat: float, fake_lon: float, fake_alt_m: float = 0.0,
                       authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        t = SPOOFING_TECHNIQUES.get(technique)
        if not t:
            return {"error": "unknown_technique", "available": list(SPOOFING_TECHNIQUES.keys())}

        session_id = f"GSPF-{uuid.uuid4().hex[:8].upper()}"
        takeover_time_s = random.randint(5, 120)
        _spoof_sessions[session_id] = {
            "session_id": session_id,
            "target_system": target_system,
            "technique": technique,
            "technique_details": t,
            "fake_position": {"lat": fake_lat, "lon": fake_lon, "alt_m": fake_alt_m},
            "takeover_time_s": takeover_time_s,
            "signals_generated": random.randint(4, 12),
            "position_error_injected_m": round(random.uniform(100, 50000), 0),
            "time_error_injected_ns": random.randint(0, 10000),
            "detection_risk": t["detection_risk"],
            "status": "ACTIVE",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }
        return _spoof_sessions[session_id]

    def navigation_denial(self, target_area_km2: float, target_systems: list,
                          method: str = "combined", authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        return {
            "operation_id": f"NAVDEN-{uuid.uuid4().hex[:8].upper()}",
            "target_area_km2": target_area_km2,
            "target_systems": target_systems,
            "method": method,
            "coverage_achieved_pct": round(random.uniform(85, 99), 1),
            "affected_targets": random.sample(TARGET_CATEGORIES, k=min(4, len(TARGET_CATEGORIES))),
            "power_required_kw": round(target_area_km2 * 0.001 * random.uniform(0.5, 2.0), 2),
            "collateral_systems": ["civilian_aviation", "maritime"] if target_area_km2 > 5000 else [],
            "is_simulation": True,
        }

    def anti_spoofing_detect(self, lat: float = 48.85, lon: float = 2.35):
        indicators = []
        score = 0
        checks = [
            ("signal_strength_anomaly", random.random() < 0.3),
            ("multi_constellation_discrepancy", random.random() < 0.2),
            ("doppler_inconsistency", random.random() < 0.15),
            ("clock_jump", random.random() < 0.1),
            ("inertial_discrepancy", random.random() < 0.25),
            ("sky_model_mismatch", random.random() < 0.2),
        ]
        for name, detected in checks:
            if detected:
                indicators.append(name)
                score += 1
        return {
            "location": {"lat": lat, "lon": lon},
            "spoofing_detected": score >= 2,
            "confidence_pct": min(95, score * 20),
            "indicators": indicators,
            "recommendation": "TRUST_INERTIAL_ONLY" if score >= 3 else "MONITOR" if score >= 1 else "NOMINAL",
            "is_simulation": True,
        }

    def list_sessions(self):
        return {
            "spoof_sessions": list(_spoof_sessions.values()),
            "jam_sessions": list(_jam_sessions.values()),
            "is_simulation": True,
        }

    def stop_session(self, session_id: str):
        if session_id in _spoof_sessions:
            _spoof_sessions[session_id]["status"] = "STOPPED"
            return _spoof_sessions[session_id]
        if session_id in _jam_sessions:
            _jam_sessions[session_id]["status"] = "STOPPED"
            return _jam_sessions[session_id]
        return {"error": "not_found"}


import math
