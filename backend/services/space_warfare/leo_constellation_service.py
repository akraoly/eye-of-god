"""
LEO Constellation Disruption — Starlink, OneWeb, Kuiper, Iridium.
Terminal attack, crosslink disruption, ground station targeting.
"""
import uuid, random
from datetime import datetime, timezone

CONSTELLATIONS = {
    "starlink": {
        "operator": "SpaceX",
        "total_sats": 5500,
        "active_sats": 4800,
        "altitude_km": 550,
        "orbit": "LEO",
        "freq_uplink_ghz": 14.0,
        "freq_downlink_ghz": 12.0,
        "crosslink": True,
        "crosslink_freq_ghz": 60.0,
        "ground_stations": 200,
        "terminal_count_est": 2800000,
        "military_contract": True,
        "mil_contract_details": "Ukraine SATCOM, US DoD Starshield",
    },
    "oneweb": {
        "operator": "Eutelsat OneWeb",
        "total_sats": 648,
        "active_sats": 588,
        "altitude_km": 1200,
        "orbit": "LEO",
        "freq_uplink_ghz": 14.0,
        "freq_downlink_ghz": 10.7,
        "crosslink": False,
        "ground_stations": 50,
        "terminal_count_est": 500000,
        "military_contract": False,
    },
    "kuiper": {
        "operator": "Amazon",
        "total_sats": 3236,
        "active_sats": 100,
        "altitude_km": 590,
        "orbit": "LEO",
        "freq_uplink_ghz": 17.7,
        "freq_downlink_ghz": 17.8,
        "crosslink": False,
        "ground_stations": 30,
        "terminal_count_est": 50000,
        "military_contract": False,
    },
    "iridium_next": {
        "operator": "Iridium",
        "total_sats": 66,
        "active_sats": 66,
        "altitude_km": 780,
        "orbit": "LEO_polar",
        "freq_uplink_ghz": 1.616,
        "freq_downlink_ghz": 1.616,
        "crosslink": True,
        "crosslink_freq_ghz": 23.0,
        "ground_stations": 12,
        "terminal_count_est": 1500000,
        "military_contract": True,
        "mil_contract_details": "US DoD voice/data — Push-To-Talk mil use",
    },
    "o3b_mpower": {
        "operator": "SES",
        "total_sats": 11,
        "active_sats": 7,
        "altitude_km": 8062,
        "orbit": "MEO",
        "freq_uplink_ghz": 30.0,
        "freq_downlink_ghz": 20.2,
        "crosslink": False,
        "ground_stations": 20,
        "terminal_count_est": 200000,
        "military_contract": True,
        "mil_contract_details": "NATO broadband connectivity",
    },
}

ATTACK_VECTORS = {
    "terminal_jamming":       "Jam Ku/Ka uplink from terminal to satellite — deny user access",
    "ground_station_attack":  "Cyber/physical attack on gateway ground stations",
    "crosslink_disruption":   "Target inter-satellite crosslink frequencies",
    "uplink_spoofing":        "Inject spoofed commands via uplink impersonation",
    "constellation_blinding": "Coordinated jamming of multiple birds simultaneously",
    "terminal_firmware_hack": "Exploit terminal update mechanism (as in Viasat/AcidRain)",
}

_disruption_ops: dict = {}


class LeoConstellationService:

    def list_constellations(self):
        return {"constellations": CONSTELLATIONS, "is_simulation": True}

    def analyze_constellation(self, name: str):
        c = CONSTELLATIONS.get(name.lower())
        if not c:
            return {"error": "not_found", "available": list(CONSTELLATIONS.keys())}
        vuln_score = 0
        vulnerabilities = []
        if not c["crosslink"]:
            vulnerabilities.append("No crosslink — single ground station dependency")
            vuln_score += 2
        if c["freq_uplink_ghz"] < 5.0:
            vulnerabilities.append("Low-frequency uplink — easier to jam")
            vuln_score += 2
        if c.get("military_contract"):
            vulnerabilities.append("Military contract — high-value target")
            vuln_score += 1
        if c["total_sats"] > 1000:
            vulnerabilities.append("Large constellation — requires coordinated attack")
            vuln_score -= 1
        return {
            "constellation": name,
            "details": c,
            "vulnerability_score": max(1, vuln_score),
            "vulnerabilities": vulnerabilities,
            "attack_vectors": list(ATTACK_VECTORS.keys()),
            "recommended_vector": "ground_station_attack" if c["ground_stations"] < 20
                                  else "terminal_jamming" if c["freq_uplink_ghz"] < 15
                                  else "uplink_spoofing",
            "is_simulation": True,
        }

    def terminal_attack(self, constellation: str, target_region: str,
                        attack_type: str = "terminal_jamming",
                        authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        c = CONSTELLATIONS.get(constellation.lower())
        if not c:
            return {"error": "not_found"}
        if attack_type not in ATTACK_VECTORS:
            return {"error": "unknown_vector", "available": list(ATTACK_VECTORS.keys())}

        op_id = f"LEO-{uuid.uuid4().hex[:8].upper()}"
        terminals_affected = random.randint(1000, 50000)
        _disruption_ops[op_id] = {
            "op_id": op_id,
            "constellation": constellation,
            "target_region": target_region,
            "attack_type": attack_type,
            "description": ATTACK_VECTORS[attack_type],
            "terminals_affected": terminals_affected,
            "satellites_targeted": random.randint(3, 20),
            "coverage_denial_pct": round(random.uniform(60, 95), 1),
            "power_required_w": round(random.uniform(100, 5000), 0),
            "detection_risk": "HIGH" if attack_type in ("ground_station_attack", "uplink_spoofing") else "MEDIUM",
            "status": "ACTIVE",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "is_simulation": True,
        }
        return _disruption_ops[op_id]

    def ground_station_attack(self, constellation: str, station_id: str,
                               method: str = "cyber_intrusion",
                               authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        methods = {
            "cyber_intrusion": "Remote exploitation of GS management network",
            "supply_chain":    "Firmware trojan in GS equipment",
            "physical_access": "Direct access to GS hardware",
            "rf_injection":    "RF signal injection into GS antenna system",
        }
        return {
            "op_id": f"GS-{uuid.uuid4().hex[:8].upper()}",
            "constellation": constellation,
            "station_id": station_id,
            "method": method,
            "description": methods.get(method, "Unknown"),
            "satellites_affected": random.randint(50, 500),
            "outage_duration_hours": round(random.uniform(0.5, 24), 1),
            "recovery_time_hours": round(random.uniform(2, 72), 1),
            "cascading_outage": random.random() < 0.4,
            "status": "EXECUTING",
            "is_simulation": True,
        }

    def crosslink_jam(self, constellation: str, authorization_confirmed: bool = False):
        if not authorization_confirmed:
            return {"error": "authorization_required"}
        c = CONSTELLATIONS.get(constellation.lower())
        if not c:
            return {"error": "not_found"}
        if not c.get("crosslink"):
            return {"error": "no_crosslink", "message": f"{constellation} has no inter-satellite crosslinks"}
        return {
            "op_id": f"XL-{uuid.uuid4().hex[:8].upper()}",
            "constellation": constellation,
            "crosslink_freq_ghz": c.get("crosslink_freq_ghz"),
            "jammable": True,
            "power_required_kw": round(random.uniform(5, 50), 1),
            "network_partition_risk": True,
            "routing_degradation_pct": round(random.uniform(40, 85), 1),
            "is_simulation": True,
        }

    def impact_assessment(self, constellation: str, attack_type: str):
        c = CONSTELLATIONS.get(constellation.lower())
        if not c:
            return {"error": "not_found"}
        return {
            "constellation": constellation,
            "attack_type": attack_type,
            "terminals_at_risk": c["terminal_count_est"],
            "military_impact": "CRITICAL" if c.get("military_contract") else "LOW",
            "civilian_impact": "HIGH" if c["terminal_count_est"] > 1000000 else "MODERATE",
            "economic_impact_musd": round(c["terminal_count_est"] * 0.002 * random.uniform(0.5, 2.0), 0),
            "strategic_value": "TIER_1" if c.get("military_contract") and c["terminal_count_est"] > 1e6 else "TIER_2",
            "recovery_time_hours": round(random.uniform(4, 168), 0),
            "is_simulation": True,
        }

    def stop_operation(self, op_id: str):
        if op_id in _disruption_ops:
            _disruption_ops[op_id]["status"] = "STOPPED"
            return _disruption_ops[op_id]
        return {"error": "not_found"}

    def list_operations(self):
        return {"operations": list(_disruption_ops.values()), "total": len(_disruption_ops), "is_simulation": True}
