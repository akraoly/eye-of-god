"""
Military Protocols Service — Bloc 13 Neutralisation
MIL-STD-1553, ARINC 429/664, Link 16, STANAG 4586, IFF.
Simulation uniquement — authorization_confirmed requis pour attaques.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/neutralization/mil_protocols")
_OUTPUT.mkdir(parents=True, exist_ok=True)

MIL_PROTOCOLS = {
    "mil_std_1553b": {
        "standard": "MIL-STD-1553B",
        "desc":     "Avionics data bus — dual redundant, 1 Mbps, BC/RT/BM topology",
        "layer":    "Serial Manchester encoded",
        "used_in":  "F-16, F-15, F-35 (legacy), C-130, naval systems",
        "security": "NONE — no authentication, no encryption",
    },
    "arinc_429": {
        "standard": "ARINC 429",
        "desc":     "Civil avionics one-way bus — 12.5/100 kbps",
        "layer":    "Differential bipolar serial",
        "used_in":  "Airbus A320/A380, Boeing 737/777, commercial transport",
        "security": "NONE",
    },
    "arinc_664": {
        "standard": "ARINC 664 AFDX",
        "desc":     "Avionics Full DupleX switched Ethernet — 100 Mbps",
        "layer":    "Deterministic Ethernet with VL (Virtual Links)",
        "used_in":  "A380, A350, B787",
        "security": "VL separation only — no crypto",
    },
    "link16": {
        "standard": "TADIL-J / Link 16",
        "desc":     "NATO tactical data link — JTIDS/MIDS terminals",
        "layer":    "TDMA FHSS — 960-1215 MHz, 51 hops/s",
        "used_in":  "NATO fighters, E-3, AWACS, destroyers",
        "security": "HAVE QUICK II + COMSEC keys (128-bit)",
    },
    "stanag_4586": {
        "standard": "STANAG 4586",
        "desc":     "NATO UAV interoperability standard — GCS/UAV interface",
        "layer":    "UDP/TCP over IP",
        "used_in":  "Predator, Reaper, Heron, Dassault PDM",
        "security": "Optional TLS — often disabled in field",
    },
    "iff_mode_s": {
        "standard": "IFF Mode S",
        "desc":     "Identification Friend or Foe — ICAO ADS-B compatible",
        "layer":    "1030/1090 MHz pulse position modulation",
        "used_in":  "All military aircraft, NATO naval vessels",
        "security": "Mode 4/5 encrypted — older Mode 3/A unencrypted",
    },
}

ATTACK_SCENARIOS = {
    "mil_std_1553b_bus_monitor":   "Passive monitoring of all RT/BC traffic on 1553 bus",
    "mil_std_1553b_bc_takeover":   "Spoof Bus Controller — inject spurious commands to RTs",
    "mil_std_1553b_rt_spoof":      "Spoof Remote Terminal — inject false sensor data",
    "arinc_429_wordspoof":         "Inject false ARINC 429 words (altitude, speed, attitude)",
    "afdx_vl_injection":           "Inject frames into AFDX Virtual Link — avionics data poisoning",
    "link16_jamming":              "Wideband FHSS jamming 960-1215 MHz — break JTIDS connectivity",
    "link16_replay":               "Replay captured JTIDS messages — fake track injection",
    "stanag4586_gcs_spoof":        "STANAG 4586 GCS command injection — hijack UAV waypoints",
    "iff_mode3a_spoof":            "Spoof IFF Mode 3/A — false friendly identification",
    "iff_mode5_replay":            "IFF Mode 5 replay attack — replay authenticated challenge-response",
}

LINK16_J_SERIES = {
    "J0":   "Network time reference",
    "J2":   "Indirect interface unit handoff",
    "J3.0": "Emergency point-to-point",
    "J3.2": "Fighter-to-fighter",
    "J3.5": "Air control",
    "J7.0": "Track management",
    "J7.2": "Air track",
    "J7.3": "Surface track",
    "J7.4": "Subsurface track",
    "J12.0":"Mission assignment",
    "J14.0":"Electronic warfare",
    "J20.0":"Weapons coordination",
}


class MilitaryProtocolsService:

    def __init__(self):
        self.is_simulation = True

    def _check_auth(self, authorization_confirmed: bool) -> Optional[Dict]:
        if not authorization_confirmed:
            return {"error": "authorization_required",
                    "message": "Military protocol attacks require authorization_confirmed: true"}
        return None

    def list_protocols(self) -> Dict:
        return {k: {"standard": v["standard"], "desc": v["desc"],
                    "security": v["security"], "used_in": v["used_in"]}
                for k, v in MIL_PROTOCOLS.items()}

    def protocol_detail(self, protocol: str) -> Dict:
        info = MIL_PROTOCOLS.get(protocol)
        if not info:
            return {"error": "not_found", "protocol": protocol}
        return {**info, "attack_vectors": [k for k in ATTACK_SCENARIOS if protocol.replace("_","") in k.replace("_","")]}

    def mil1553_bus_scan(self, bus_address: str = "/dev/ttyUSB0") -> Dict:
        rts = []
        for rt_addr in random.sample(range(0, 31), random.randint(4, 12)):
            rts.append({
                "rt_address":   rt_addr,
                "subaddresses": random.randint(1, 8),
                "description":  random.choice(["NAV computer","RADAR interface","FCS","SMS","EW system",
                                                "Engine controller","HUD","ECM pod","Data recorder"]),
                "message_rate_hz": random.randint(10, 100),
            })
        return {"bus": bus_address, "rts_found": len(rts), "rt_list": rts,
                "bc_detected": True, "bus_monitor_active": True, "is_simulation": True}

    def mil1553_inject(self, rt_address: int, subaddress: int, data_words: List[int],
                        authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        session_id = f"1553_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":   session_id,
            "rt_address":   rt_address,
            "subaddress":   subaddress,
            "data_words":   data_words[:32],
            "action":       "BC_TO_RT_WRITE",
            "consequence":  "Injected command to avionics subsystem — physical effect possible",
            "is_simulation": True,
        }
        _SESSIONS[session_id] = result
        return result

    def arinc429_spoof(self, label: int, value: float, sdi: int = 0,
                        authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        label_names = {0o001:"Speed",0o206:"Altitude",0o325:"Heading",0o174:"Latitude",0o175:"Longitude"}
        session_id = f"arinc_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":  session_id,
            "label_octal": f"{label:03o}",
            "label_name":  label_names.get(label, "Unknown parameter"),
            "value":       value,
            "sdi":         sdi,
            "encoded_word": f"0x{random.randint(0,0xFFFFFFFF):08X}",
            "consequence": "Spoofed avionics sensor reading injected — FMS/FCS may act on false data",
            "is_simulation": True,
        }
        _SESSIONS[session_id] = result
        return result

    def link16_analyze_traffic(self, freq_mhz: float = 1000.0) -> Dict:
        j_series_seen = random.sample(list(LINK16_J_SERIES.keys()), k=random.randint(3, 8))
        tracks = []
        for _ in range(random.randint(5, 20)):
            tracks.append({
                "track_id":    f"T{random.randint(1000,9999)}",
                "j_series":    random.choice(["J7.2","J7.3","J7.4"]),
                "lat":         round(random.uniform(40, 60), 3),
                "lon":         round(random.uniform(-10, 30), 3),
                "altitude_ft": random.randint(0, 45000),
                "speed_kts":   random.randint(0, 600),
                "iff_status":  random.choice(["FRIEND","UNKNOWN","HOSTILE","NEUTRAL"]),
            })
        return {
            "freq_mhz":      freq_mhz,
            "terminal_type": "MIDS-LVT",
            "j_series_seen": {j: LINK16_J_SERIES[j] for j in j_series_seen},
            "track_picture": tracks,
            "participants":  random.randint(3, 15),
            "is_simulation": True,
        }

    def link16_jam(self, authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        return {
            "action":      "LINK16_JAMMING",
            "freq_range":  "960-1215 MHz (JTIDS hopping band)",
            "technique":   "Wideband noise + reactive FHSS follower",
            "power_w":     round(random.uniform(20, 200), 0),
            "effect":      "NATO tactical picture degraded — track updates lost",
            "is_simulation": True,
        }

    def iff_spoof(self, mode: str = "3A", code: str = "7700",
                   authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        session_id = f"iff_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":   session_id,
            "mode":         mode,
            "squawk_code":  code,
            "freq_interrogation": 1030,
            "freq_reply":         1090,
            "method":       "SDR replayer — capture valid IFF waveform, retransmit with modified code",
            "consequence":  f"Aircraft appears as code {code} to ATC/military — identification spoof",
            "is_simulation": True,
        }
        _SESSIONS[session_id] = result
        return result

    def stanag4586_uav_hijack(self, uav_ip: str, port: int = 4586,
                               new_waypoint_lat: float = 48.85,
                               new_waypoint_lon: float = 2.35,
                               authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        session_id = f"stanag_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":   session_id,
            "uav_ip":       uav_ip,
            "protocol":     "STANAG 4586 VSM command",
            "action":       "INJECT_WAYPOINT",
            "new_waypoint": {"lat": new_waypoint_lat, "lon": new_waypoint_lon, "alt_m": 500},
            "consequence":  "UAV mission plan hijacked — redirected to attacker-specified coordinates",
            "is_simulation": True,
        }
        _SESSIONS[session_id] = result
        return result

    def list_attack_scenarios(self) -> Dict:
        return ATTACK_SCENARIOS

    def list_link16_j_series(self) -> Dict:
        return LINK16_J_SERIES

    def get_session(self, session_id: str) -> Dict:
        return _SESSIONS.get(session_id, {"error": "not_found"})
