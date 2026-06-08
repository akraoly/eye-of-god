"""
Drone Defense Service — Bloc 11 Guerre Électronique
Détection, classification, tracking, neutralisation de drones.
Simulation mode by default.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DRONE_CONTACTS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/ew/drones")
_OUTPUT.mkdir(parents=True, exist_ok=True)

DRONE_SIGNATURES = {
    "DJI_Mini3":     {"protocol": "OcuSync3",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-60, -30)},
    "DJI_Mini4Pro":  {"protocol": "OcuSync3",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-65, -25)},
    "DJI_Mavic3":    {"protocol": "OcuSync3",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-70, -20)},
    "DJI_Air3":      {"protocol": "OcuSync3",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-68, -22)},
    "DJI_Phantom4":  {"protocol": "OcuSync2",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-75, -25)},
    "DJI_Matrice":   {"protocol": "OcuSync2",  "freq_mhz": [2400, 5800], "video_port": 8803,  "ctrl_port": 8883,  "rssi_range": (-70, -15)},
    "Autel_EVO2":    {"protocol": "SkyLink2",  "freq_mhz": [2400, 5800], "video_port": 9090,  "ctrl_port": 9091,  "rssi_range": (-72, -28)},
    "Parrot_Anafi":  {"protocol": "WIFIP2P",   "freq_mhz": [2400, 5800], "video_port": 55004, "ctrl_port": 44444, "rssi_range": (-80, -35)},
    "Yuneec_H520":   {"protocol": "ST16",      "freq_mhz": [2400, 5800], "video_port": 7060,  "ctrl_port": 7070,  "rssi_range": (-78, -30)},
    "FPV_ExpressLRS":{"protocol": "ELRS",      "freq_mhz": [868, 915, 2400], "video_port": 0, "ctrl_port": 0,     "rssi_range": (-90, -40)},
    "FPV_Crossfire": {"protocol": "CRSF",      "freq_mhz": [869], "video_port": 0, "ctrl_port": 0, "rssi_range": (-95, -45)},
    "Generic_RC":    {"protocol": "FCC_ISM",   "freq_mhz": [433, 868, 2400], "video_port": 0, "ctrl_port": 0,     "rssi_range": (-85, -40)},
}

NO_FLY_ZONES_SAMPLE = [
    {"name": "Aéroport CDG", "lat": 49.0097, "lon": 2.5479, "radius_km": 5.0, "max_alt_m": 0},
    {"name": "Palais Élysée", "lat": 48.8699, "lon": 2.3167, "radius_km": 1.0, "max_alt_m": 0},
    {"name": "Centrale nucléaire", "lat": 47.2789, "lon": 1.1703, "radius_km": 3.0, "max_alt_m": 0},
    {"name": "Base militaire", "lat": 43.5760, "lon": 1.3800, "radius_km": 2.5, "max_alt_m": 0},
]

HIJACK_METHODS = {
    "dji_protocol":   "DJI OcuSync command injection via UDP — requires same network segment",
    "gps_spoof":      "GPS position spoofing — forces drone to recalculate position",
    "signal_takeover":"RF signal dominance — override legitimate controller signal",
    "battery_drain":  "Trigger continuous high-power maneuver loop — deplete battery",
}

NEUTRALIZATION_METHODS = {
    "gps_spoof_land":  "Spoof GPS coordinates to trigger RTH/land at false home point",
    "ctl_jam_land":    "Jam control link — drone enters failsafe landing mode",
    "cmd_inject":      "Command injection — send land/disarm command directly",
    "rth_force":       "Trigger Return-To-Home via protocol manipulation",
    "net_gun_sim":     "Simulates physical net capture (conceptual).",
    "drone_gun_sim":   "Directional RF pulse — forces crash of RF-dependent components",
}


class DroneDefenseService:

    def __init__(self):
        self.is_simulation = True
        self._scan_counter = 0

    # ── Detection & Classification ────────────────────────────────────────────

    def detect_drones(self, scan_area_m: float = 500.0) -> Dict:
        self._scan_counter += 1
        detected = []
        num_drones = random.randint(0, 4)
        for _ in range(num_drones):
            model = random.choice(list(DRONE_SIGNATURES.keys()))
            sig = DRONE_SIGNATURES[model]
            rssi = round(random.uniform(*sig["rssi_range"]), 1)
            dist = round(random.uniform(50, scan_area_m), 0)
            angle = random.uniform(0, 360)
            lat = 48.8566 + (dist / 111000) * math.cos(math.radians(angle))
            lon = 2.3522 + (dist / 111000) * math.sin(math.radians(angle))
            drone_id = f"drone_{uuid.uuid4().hex[:8]}"
            contact = {
                "drone_id":      drone_id,
                "manufacturer":  model.split("_")[0],
                "model":         model,
                "protocol":      sig["protocol"],
                "frequency_mhz": random.choice(sig["freq_mhz"]),
                "rssi_dbm":      rssi,
                "lat":           round(lat, 6),
                "lon":           round(lon, 6),
                "altitude_m":    round(random.uniform(20, 400), 0),
                "speed_ms":      round(random.uniform(0, 15), 1),
                "heading":       round(random.uniform(0, 360), 0),
                "distance_m":    dist,
                "status":        "detected",
                "detected_at":   datetime.utcnow().isoformat(),
                "last_seen":     datetime.utcnow().isoformat(),
                "threat_level":  self._assess_drone_threat(rssi, dist),
                "is_simulation": True,
            }
            _DRONE_CONTACTS[drone_id] = contact
            detected.append(contact)
        return {
            "scan_id":      f"scan_{self._scan_counter:04d}",
            "scan_area_m":  scan_area_m,
            "drones_found": len(detected),
            "contacts":     detected,
            "timestamp":    datetime.utcnow().isoformat(),
            "is_simulation": True,
        }

    def classify_drone(self, rssi: float, freq_mhz: float, protocol: Optional[str] = None) -> Dict:
        matches = []
        for model, sig in DRONE_SIGNATURES.items():
            score = 0
            if freq_mhz in sig["freq_mhz"]:
                score += 40
            if protocol and protocol.upper() in sig["protocol"].upper():
                score += 50
            rmin, rmax = sig["rssi_range"]
            if rmin <= rssi <= rmax:
                score += 10
            if score > 0:
                matches.append({"model": model, "confidence": min(0.99, score / 100),
                                 "manufacturer": model.split("_")[0], "protocol": sig["protocol"]})
        matches.sort(key=lambda x: -x["confidence"])
        return {"rssi_dbm": rssi, "freq_mhz": freq_mhz, "top_matches": matches[:3],
                "best_guess": matches[0] if matches else None, "is_simulation": True}

    def _assess_drone_threat(self, rssi: float, dist_m: float) -> str:
        if dist_m < 100 or rssi > -40:
            return "HIGH"
        if dist_m < 250 or rssi > -60:
            return "MEDIUM"
        return "LOW"

    # ── Tracking ──────────────────────────────────────────────────────────────

    def track_drone(self, drone_id: str) -> Dict:
        contact = _DRONE_CONTACTS.get(drone_id)
        if not contact:
            return {"error": "drone_not_found", "drone_id": drone_id}
        # Simulate movement
        contact["lat"] = round(contact["lat"] + random.uniform(-0.0005, 0.0005), 6)
        contact["lon"] = round(contact["lon"] + random.uniform(-0.0005, 0.0005), 6)
        contact["altitude_m"] = round(max(0, contact["altitude_m"] + random.uniform(-10, 10)), 0)
        contact["speed_ms"]   = round(max(0, contact["speed_ms"] + random.uniform(-2, 2)), 1)
        contact["heading"]    = round((contact["heading"] + random.uniform(-15, 15)) % 360, 0)
        contact["last_seen"]  = datetime.utcnow().isoformat()
        trajectory = [
            {"lat": round(contact["lat"] + i * 0.0001, 6),
             "lon": round(contact["lon"] + i * 0.0001, 6),
             "alt": contact["altitude_m"], "t_plus_s": i * 5}
            for i in range(1, 7)
        ]
        return {**contact, "trajectory_prediction": trajectory, "is_simulation": True}

    def locate_drone(self, rssi_measurements: List[Dict]) -> Dict:
        if len(rssi_measurements) < 3:
            return {"error": "Need at least 3 RSSI measurements for triangulation"}
        # Simplified centroid
        lat = sum(m["station_lat"] for m in rssi_measurements) / len(rssi_measurements)
        lon = sum(m["station_lon"] for m in rssi_measurements) / len(rssi_measurements)
        return {
            "estimated_lat":    round(lat + random.uniform(-0.001, 0.001), 6),
            "estimated_lon":    round(lon + random.uniform(-0.001, 0.001), 6),
            "accuracy_m":       round(random.uniform(10, 80), 0),
            "method":           "RSSI_trilateration",
            "stations_used":    len(rssi_measurements),
            "confidence":       round(random.uniform(0.60, 0.90), 2),
            "is_simulation":    True,
        }

    # ── Neutralization ────────────────────────────────────────────────────────

    def hijack_dji(self, drone_id: str, drone_ip: str = "192.168.1.1") -> Dict:
        contact = _DRONE_CONTACTS.get(drone_id, {})
        success = random.random() > 0.3
        if success:
            contact["status"] = "hijacked"
            contact["hijack_method"] = "dji_protocol"
            _DRONE_CONTACTS[drone_id] = contact
        return {
            "drone_id":   drone_id,
            "method":     "DJI_UDP_command_injection",
            "target_ip":  drone_ip,
            "ports_tried": [8883, 8803, 5803],
            "success":    success,
            "commands_available": ["land", "rth", "hover", "disarm", "photo"] if success else [],
            "note":       HIJACK_METHODS["dji_protocol"],
            "is_simulation": True,
        }

    def forced_landing(self, drone_id: str, method: str = "gps_spoof_land") -> Dict:
        contact = _DRONE_CONTACTS.get(drone_id, {})
        available = list(NEUTRALIZATION_METHODS.keys())
        if method not in available:
            return {"error": f"Unknown method. Available: {available}"}
        success_prob = {"gps_spoof_land": 0.80, "ctl_jam_land": 0.75, "cmd_inject": 0.65,
                        "rth_force": 0.70, "net_gun_sim": 0.90, "drone_gun_sim": 0.55}
        success = random.random() < success_prob.get(method, 0.6)
        if success:
            contact["status"] = "landed"
            contact["altitude_m"] = 0
            _DRONE_CONTACTS[drone_id] = contact
        return {
            "drone_id":      drone_id,
            "method":        method,
            "description":   NEUTRALIZATION_METHODS[method],
            "success":       success,
            "time_to_land_s": round(random.uniform(15, 120), 0) if success else None,
            "is_simulation": True,
        }

    def jam_drone_control(self, drone_id: str, freq_hop_pattern: Optional[List[float]] = None) -> Dict:
        contact = _DRONE_CONTACTS.get(drone_id, {})
        model = contact.get("model", "Unknown")
        sig = DRONE_SIGNATURES.get(model, DRONE_SIGNATURES["Generic_RC"])
        jam_freqs = freq_hop_pattern or sig["freq_mhz"]
        return {
            "drone_id":      drone_id,
            "jammed_freqs":  jam_freqs,
            "expected_effect": "Control link loss → failsafe (land/RTH)",
            "activation_delay_ms": random.randint(100, 500),
            "is_simulation": True,
        }

    def jam_drone_video(self, drone_id: str) -> Dict:
        contact = _DRONE_CONTACTS.get(drone_id, {})
        model = contact.get("model", "Unknown")
        sig = DRONE_SIGNATURES.get(model, DRONE_SIGNATURES["Generic_RC"])
        return {
            "drone_id":      drone_id,
            "video_freq_mhz": sig["freq_mhz"],
            "video_port":    sig.get("video_port", 0),
            "jam_bandwidth": 100,
            "expected_effect": "Video link loss — operator loses FPV — may trigger RTH",
            "is_simulation": True,
        }

    def geofence_violation_detect(self, lat: float, lon: float, altitude_m: float) -> Dict:
        violations = []
        for zone in NO_FLY_ZONES_SAMPLE:
            dist = self._haversine(lat, lon, zone["lat"], zone["lon"])
            if dist <= zone["radius_km"] * 1000:
                violations.append({
                    "zone_name":    zone["name"],
                    "distance_m":   round(dist, 0),
                    "max_alt_m":    zone["max_alt_m"],
                    "drone_alt_m":  altitude_m,
                    "severity":     "CRITICAL" if dist < zone["radius_km"] * 500 else "HIGH",
                })
        return {
            "lat": lat, "lon": lon, "altitude_m": altitude_m,
            "violations": violations, "violation_count": len(violations),
            "status": "VIOLATION" if violations else "CLEAR",
        }

    def swarm_detect(self, drone_ids: List[str]) -> Dict:
        contacts = [_DRONE_CONTACTS.get(did, {}) for did in drone_ids if did in _DRONE_CONTACTS]
        if len(contacts) < 2:
            return {"swarm_detected": False, "reason": "Insufficient contacts"}
        lats = [c["lat"] for c in contacts if "lat" in c]
        lons = [c["lon"] for c in contacts if "lon" in c]
        spread_m = self._haversine(min(lats), min(lons), max(lats), max(lons))
        return {
            "swarm_detected":    len(contacts) >= 3 and spread_m < 500,
            "drone_count":       len(contacts),
            "spread_m":          round(spread_m, 0),
            "coordination_prob": round(random.uniform(0.6, 0.95), 2),
            "threat_level":      "CRITICAL" if len(contacts) >= 5 else "HIGH",
            "recommendation":    "Activate area jamming — multi-freq sweep",
            "is_simulation":     True,
        }

    def list_contacts(self) -> Dict:
        return {"contacts": list(_DRONE_CONTACTS.values()), "total": len(_DRONE_CONTACTS)}

    def return_to_home(self, drone_id: str) -> Dict:
        success = random.random() > 0.25
        if success and drone_id in _DRONE_CONTACTS:
            _DRONE_CONTACTS[drone_id]["status"] = "returning"
        return {"drone_id": drone_id, "command": "RTH", "success": success, "is_simulation": True}

    def drone_gun_emulation(self, drone_id: str) -> Dict:
        return {
            "drone_id":        drone_id,
            "gun_type":        "directional_RF_pulse_emulation",
            "effective_range_m": random.randint(200, 1500),
            "beam_width_deg":  random.randint(15, 45),
            "pulse_power_w":   random.randint(50, 500),
            "expected_effect": "Temporary control loss + video loss + possible motor ESC reset",
            "is_simulation":   True,
        }

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
