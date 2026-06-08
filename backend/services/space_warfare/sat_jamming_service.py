"""
Satellite Communications Jamming — Uplink/Downlink, Frequency Hijack, Crosslink.
"""
import uuid, random
from datetime import datetime, timezone

SAT_COMM_BANDS = {
    "L":  {"range_ghz": [1.0,  2.0],  "use": "Mobile satellite, GPS"},
    "S":  {"range_ghz": [2.0,  4.0],  "use": "Weather sats, telemetry, ISS"},
    "C":  {"range_ghz": [4.0,  8.0],  "use": "Legacy TV/broadcast, some mil"},
    "X":  {"range_ghz": [8.0,  12.0], "use": "Military comms, SAR, weather"},
    "Ku": {"range_ghz": [12.0, 18.0], "use": "Direct broadcast TV, Starlink uplink"},
    "Ka": {"range_ghz": [26.5, 40.0], "use": "HTS broadband, mil SATCOM (WGS)"},
    "Q":  {"range_ghz": [33.0, 50.0], "use": "Military/government future systems"},
    "V":  {"range_ghz": [50.0, 75.0], "use": "Experimental HTS"},
    "EHF":{"range_ghz": [60.0, 300.0],"use": "MILSTAR, AEHF — LPI/LPD mil comms"},
}

JAMMING_MODES = {
    "uplink_jam": "Jam ground-to-satellite uplink — transponder saturation",
    "downlink_jam": "Jam satellite-to-ground downlink — receiver desensitization",
    "crosslink_jam": "Jam inter-satellite crosslinks (LEO constellations)",
    "transponder_hijack": "Transmit on satellite uplink freq to override legitimate signal",
    "lobe_jamming": "Target satellite sidelobe — lower power required",
    "swept_noise": "Swept wideband noise across full transponder bandwidth",
}

SATELLITE_COMMS = [
    {"sat_id": "WGS-9",       "operator": "USA-MIL",  "band": "Ka",  "uplink_ghz": 30.0, "downlink_ghz": 20.2, "coverage": "GLOBAL",       "military": True},
    {"sat_id": "AEHF-6",      "operator": "USA-MIL",  "band": "EHF", "uplink_ghz": 44.0, "downlink_ghz": 20.7, "coverage": "GLOBAL",       "military": True},
    {"sat_id": "MILSTAR-2",   "operator": "USA-MIL",  "band": "EHF", "uplink_ghz": 44.0, "downlink_ghz": 20.7, "coverage": "GLOBAL",       "military": True},
    {"sat_id": "Syracuse-4A", "operator": "FRA-MIL",  "band": "Ka",  "uplink_ghz": 30.5, "downlink_ghz": 20.7, "coverage": "EUR_AFRICA",   "military": True},
    {"sat_id": "Skynet-5D",   "operator": "GBR-MIL",  "band": "X",   "uplink_ghz": 8.05, "downlink_ghz": 7.25, "coverage": "EUR_ATLANTIC", "military": True},
    {"sat_id": "Yamal-401",   "operator": "RUS",       "band": "Ku",  "uplink_ghz": 14.0, "downlink_ghz": 11.7, "coverage": "RUSSIA_CIS",   "military": False},
    {"sat_id": "Meridian-8",  "operator": "RUS-MIL",  "band": "X",   "uplink_ghz": 8.0,  "downlink_ghz": 7.3,  "coverage": "POLAR",        "military": True},
    {"sat_id": "Starlink-G4", "operator": "SpaceX",   "band": "Ku",  "uplink_ghz": 14.0, "downlink_ghz": 12.0, "coverage": "GLOBAL_LEO",   "military": False},
    {"sat_id": "OneWeb-C01",  "operator": "OneWeb",   "band": "Ku",  "uplink_ghz": 14.0, "downlink_ghz": 10.7, "coverage": "GLOBAL_LEO",   "military": False},
    {"sat_id": "Intelsat-37e","operator": "Intelsat", "band": "C",   "uplink_ghz": 6.0,  "downlink_ghz": 4.0,  "coverage": "ATLANTIC",     "military": False},
]

_jam_ops: dict = {}


class SatJammingService:

    def list_bands(self):
        return {"bands": SAT_COMM_BANDS, "jamming_modes": JAMMING_MODES}

    def list_satellites(self, military_only: bool = False):
        sats = SATELLITE_COMMS if not military_only else [s for s in SATELLITE_COMMS if s["military"]]
        return {"satellites": sats, "total": len(sats), "is_simulation": True}

    def analyze_target(self, sat_id: str):
        sat = next((s for s in SATELLITE_COMMS if s["sat_id"] == sat_id), None)
        if not sat:
            return {"error": "not_found"}
        band = SAT_COMM_BANDS.get(sat["band"], {})
        lpi_lpd = sat["band"] in ("EHF",)
        return {
            "satellite": sat,
            "band_details": band,
            "lpi_lpd_protected": lpi_lpd,
            "jamming_difficulty": "EXTREME" if lpi_lpd else "HIGH" if sat["military"] else "MODERATE",
            "recommended_mode": "lobe_jamming" if lpi_lpd else "uplink_jam",
            "estimated_power_kw": round(random.uniform(0.5, 50.0), 1),
            "ground_footprint_km": round(random.uniform(200, 800), 0),
            "is_simulation": True,
        }

    def jam_satellite(self, sat_id: str, mode: str, power_kw: float,
                      authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        sat = next((s for s in SATELLITE_COMMS if s["sat_id"] == sat_id), None)
        if not sat:
            return {"error": "not_found"}
        if mode not in JAMMING_MODES:
            return {"error": "unknown_mode", "available": list(JAMMING_MODES.keys())}

        op_id = f"SATJAM-{uuid.uuid4().hex[:8].upper()}"
        success_prob = min(0.95, power_kw / 100)
        _jam_ops[op_id] = {
            "op_id": op_id,
            "satellite": sat_id,
            "mode": mode,
            "mode_description": JAMMING_MODES[mode],
            "power_kw": power_kw,
            "jammer_to_signal_ratio_db": round(10 * (power_kw ** 0.3), 1),
            "estimated_success": round(success_prob, 2),
            "uplink_freq_ghz": sat["uplink_ghz"],
            "downlink_freq_ghz": sat["downlink_ghz"],
            "affected_area_km2": round(3.14159 * (power_kw * 5) ** 2, 0),
            "status": "JAMMING",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }
        return _jam_ops[op_id]

    def transponder_hijack(self, sat_id: str, target_freq_ghz: float,
                           authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        sat = next((s for s in SATELLITE_COMMS if s["sat_id"] == sat_id), None)
        if not sat:
            return {"error": "not_found"}
        return {
            "op_id": f"HIJACK-{uuid.uuid4().hex[:8].upper()}",
            "satellite": sat_id,
            "hijack_freq_ghz": target_freq_ghz,
            "uplink_power_needed_w": round(random.uniform(50, 500), 0),
            "eirp_dbw": round(random.uniform(40, 65), 1),
            "takeover_time_s": random.randint(10, 120),
            "interference_to_legit_db": round(random.uniform(10, 30), 1),
            "detection_risk": "HIGH" if sat["military"] else "MEDIUM",
            "status": "ACTIVE",
            "is_simulation": True,
        }

    def stop_operation(self, op_id: str):
        if op_id in _jam_ops:
            _jam_ops[op_id]["status"] = "STOPPED"
            _jam_ops[op_id]["stopped_at"] = datetime.now(timezone.utc).isoformat()
            return _jam_ops[op_id]
        return {"error": "not_found"}

    def list_operations(self):
        return {"operations": list(_jam_ops.values()), "total": len(_jam_ops), "is_simulation": True}
