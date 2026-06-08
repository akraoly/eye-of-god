"""
Thermal Exfiltration — Bloc 4 Air-Gap
Techniques : BitWhisper (chaleur CPU → capteur thermique adjacent),
             FLIR/infrared reading (passwords via heat residue on keyboards),
             Thermal covert channel (modulation température CPU pour transmettre données),
             LED exfil (optical covert channels via diodes)
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/airgap/thermal")

_THERMAL_TECHNIQUES = {
    "bitwhisper": {
        "name": "BitWhisper — CPU Thermal Covert Channel",
        "desc": "Moduler charge CPU pour varier chaleur → senseur thermique PC adjacent",
        "range_cm": 40,
        "bandwidth_bps": 8,
        "success_rate": 0.65,
        "required": ["adjacent PC with thermal sensor"],
        "stealthy": True,
        "cvss_equiv": 6.8,
    },
    "flir_keyboard": {
        "name": "FLIR Keyboard Heat Residue",
        "desc": "Caméra thermique capture chaleur résiduelle clavier → reconstruction mot de passe",
        "range_m": 3,
        "bandwidth_bps": None,
        "success_rate": 0.78,
        "required": ["FLIR_camera", "time_window_60sec"],
        "stealthy": True,
        "cvss_equiv": 7.8,
    },
    "led_exfil": {
        "name": "LED Optical Exfil",
        "desc": "Moduler LED disque dur / réseau pour canal optique covert",
        "range_m": 30,
        "bandwidth_bps": 4000,
        "success_rate": 0.85,
        "required": ["line_of_sight", "telescope_camera"],
        "stealthy": True,
        "cvss_equiv": 7.5,
    },
    "airin": {
        "name": "aIR-Jumper — IR Camera Exfil",
        "desc": "Utiliser caméra IP IR (night vision) comme canal bidirectionnel covert",
        "range_m": 20,
        "bandwidth_bps": 100,
        "success_rate": 0.72,
        "required": ["IR_security_camera"],
        "stealthy": True,
        "cvss_equiv": 7.2,
    },
    "brightness": {
        "name": "BRIGHTNESS — Screen Exfil",
        "desc": "Moduler luminosité écran invisible à l'œil — capturé par caméra de surveillance",
        "range_m": 9,
        "bandwidth_bps": 5,
        "success_rate": 0.60,
        "required": ["security_camera_line_of_sight"],
        "stealthy": True,
        "cvss_equiv": 6.5,
    },
    "pixhell": {
        "name": "PIXHELL — LCD Pixel Noise",
        "desc": "Patterns LCD génèrent sons acoustiques → acoustic covert channel",
        "range_m": 2,
        "bandwidth_bps": 20,
        "success_rate": 0.55,
        "required": ["microphone"],
        "stealthy": False,
        "cvss_equiv": 5.5,
    },
}

_KEYBOARD_KEYS = "qwertyuiopasdfghjklzxcvbnm0123456789!@#$%^&*()_+-=[]{}|;':\",./<>?"
_THERMAL_DECAY = {15: 0.95, 30: 0.80, 45: 0.55, 60: 0.30, 90: 0.10}


class ThermalExfilService:
    """Thermal + optical covert channels — exfiltration sur air-gapped systems."""

    def flir_keyboard_read(self, elapsed_sec: int = 30,
                            keyboard_type: str = "membrane") -> Dict:
        """FLIR capture chaleur résiduelle clavier → reconstruit mot de passe."""
        session_id = str(uuid.uuid4())
        info = _THERMAL_TECHNIQUES["flir_keyboard"]

        decay = _THERMAL_DECAY.get(
            min(_THERMAL_DECAY.keys(), key=lambda k: abs(k - elapsed_sec)), 0.0
        )
        success = random.random() < (info["success_rate"] * decay)

        recovered_keys = []
        confidence = {}
        if success:
            pwd_len = random.randint(8, 16)
            pwd = ''.join(random.choices(_KEYBOARD_KEYS[:40], k=pwd_len))
            for char in pwd:
                if random.random() < decay:
                    recovered_keys.append(char)
                    confidence[char] = round(random.uniform(0.6, 0.98), 2)
                else:
                    recovered_keys.append('?')

        return {
            "session_id": session_id,
            "technique": "FLIR Keyboard Heat Residue",
            "elapsed_since_typing_sec": elapsed_sec,
            "thermal_decay_factor": decay,
            "keyboard_type": keyboard_type,
            "success": success,
            "keys_recovered": recovered_keys,
            "password_candidate": ''.join(recovered_keys) if recovered_keys else None,
            "confidence_per_key": confidence,
            "overall_confidence_pct": round(sum(confidence.values()) / max(len(confidence), 1) * 100, 1),
            "recommended_followup": "brute-force remaining ? characters" if '?' in recovered_keys else "use directly",
            "simulated": True,
        }

    def bitwhisper_channel(self, data: str = "KEY",
                            adjacent_distance_cm: float = 30.0,
                            mode: str = "transmit") -> Dict:
        """BitWhisper — canal thermique CPU→senseur PC adjacent."""
        session_id = str(uuid.uuid4())
        info = _THERMAL_TECHNIQUES["bitwhisper"]
        in_range = adjacent_distance_cm <= info["range_cm"]
        bw = info["bandwidth_bps"]
        duration = (len(data) * 8) / bw if bw else 0

        return {
            "session_id": session_id,
            "technique": "BitWhisper",
            "mode": mode,
            "data_bytes": len(data),
            "distance_cm": adjacent_distance_cm,
            "in_range": in_range,
            "bandwidth_bps": bw,
            "estimated_duration_sec": round(duration, 1),
            "cpu_load_pattern": "alternating 100%/20% every 20sec",
            "temp_delta_celsius": round(random.uniform(1.5, 8.0), 1),
            "success": in_range and random.random() < info["success_rate"],
            "received_data": data if mode == "receive" and random.random() < 0.6 else None,
            "simulated": True,
        }

    def led_exfil(self, data_path: str = "/etc/shadow",
                   led_source: str = "hdd_led",
                   modulation: str = "OOK") -> Dict:
        """LED optical covert channel — moduler diode pour exfiltrer données."""
        session_id = str(uuid.uuid4())
        info = _THERMAL_TECHNIQUES["led_exfil"]

        data_size = random.randint(1024, 65536)
        bw = info["bandwidth_bps"]
        duration = data_size * 8 / bw

        return {
            "session_id": session_id,
            "technique": "LED Optical Exfil",
            "led_source": led_source,
            "modulation": modulation,
            "data_path": data_path,
            "data_size_bytes": data_size,
            "bandwidth_bps": bw,
            "estimated_duration_sec": round(duration, 1),
            "line_of_sight_required": True,
            "visible_to_naked_eye": modulation == "OOK" and bw < 100,
            "receiver": "telescope + high-speed camera",
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def airin_camera_exfil(self, camera_ip: str = "192.168.1.100",
                            mode: str = "exfil",
                            data: str = "PASSWORD") -> Dict:
        """aIR-Jumper — utiliser caméra IR comme canal bidirectionnel."""
        session_id = str(uuid.uuid4())
        info = _THERMAL_TECHNIQUES["airin"]
        bw = info["bandwidth_bps"]
        duration = (len(data) * 8) / bw

        return {
            "session_id": session_id,
            "technique": "aIR-Jumper IR Camera",
            "camera_ip": camera_ip,
            "mode": mode,
            "data_bytes": len(data),
            "bandwidth_bps": bw,
            "estimated_duration_sec": round(duration, 2),
            "ir_wavelength_nm": 850,
            "range_m": info["range_m"],
            "bidirectional": True,
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def screen_brightness_exfil(self, data: str = "SECRET_KEY",
                                  brightness_min: int = 0,
                                  brightness_max: int = 100) -> Dict:
        """BRIGHTNESS — moduler luminosité écran → exfil optique invisible."""
        session_id = str(uuid.uuid4())
        info = _THERMAL_TECHNIQUES["brightness"]
        bw = info["bandwidth_bps"]
        duration = (len(data) * 8) / bw

        return {
            "session_id": session_id,
            "technique": "BRIGHTNESS Screen Exfil",
            "data_bytes": len(data),
            "bandwidth_bps": bw,
            "estimated_duration_sec": round(duration, 1),
            "brightness_range": f"{brightness_min}-{brightness_max}%",
            "frequency_hz": round(bw / 2, 1),
            "human_detectable": brightness_max - brightness_min > 30,
            "range_m": info["range_m"],
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def list_techniques(self) -> List[Dict]:
        return [
            {
                "id": k, "name": v["name"], "description": v["desc"],
                "range": v.get("range_m") or f"{v.get('range_cm')}cm",
                "bandwidth_bps": v.get("bandwidth_bps"),
                "success_rate": v["success_rate"], "stealthy": v["stealthy"],
                "cvss_equiv": v["cvss_equiv"],
            }
            for k, v in _THERMAL_TECHNIQUES.items()
        ]
