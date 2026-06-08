"""
EM Injection & TEMPEST — Bloc 4 Air-Gap
Techniques : Van Eck phreaking, TEMPEST eavesdropping, EM injection,
             ODINI (HDD EM covert channel), MAGNETO (gyroscope via EM)
Outils réels : HackRF One, USRP B200, RTL-SDR, custom TEMPEST antennas
"""
from __future__ import annotations

import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/airgap/em")

_EM_TECHNIQUES = {
    "van_eck": {
        "name": "Van Eck Phreaking",
        "desc": "Reconstruction d'affichage via émissions EM du câble vidéo/GPU",
        "target": "CRT/LCD monitors, HDMI/VGA cables",
        "range_m": 30,
        "success_rate": 0.75,
        "required_hw": ["HackRF One", "directional_antenna_yagi"],
        "cvss_equiv": 7.5,
    },
    "tempest_keyboard": {
        "name": "TEMPEST Keyboard Eavesdrop",
        "desc": "Keylogging passif via émissions EM du clavier filaire",
        "target": "PS/2 keyboards, USB keyboards",
        "range_m": 20,
        "success_rate": 0.80,
        "required_hw": ["USRP_B200", "loop_antenna"],
        "cvss_equiv": 8.1,
    },
    "tempest_screen": {
        "name": "TEMPEST Screen Reconstruction",
        "desc": "Reconstruction de l'écran via HDMI/VGA EM side-channel",
        "target": "HDMI/DisplayPort/VGA display cables",
        "range_m": 50,
        "success_rate": 0.65,
        "required_hw": ["USRP_N210", "wideband_antenna"],
        "cvss_equiv": 7.8,
    },
    "odini": {
        "name": "ODINI — HDD EM Covert Channel",
        "desc": "Exfiltration de données via modulation EM des têtes HDD",
        "target": "Air-gapped PC with spinning HDD",
        "range_m": 2,
        "success_rate": 0.60,
        "required_hw": ["RFID_reader_LF", "smartphone_magnetometer"],
        "cvss_equiv": 6.5,
        "bandwidth_bps": 2,
    },
    "magneto": {
        "name": "MAGNETO — CPU→Smartphone Covert Channel",
        "desc": "Exfil via champ magnétique CPU modulé, capturé par gyroscope smartphone",
        "target": "Air-gapped PC near smartphone",
        "range_m": 0.5,
        "success_rate": 0.55,
        "required_hw": ["none_passive"],
        "cvss_equiv": 6.0,
        "bandwidth_bps": 10,
    },
    "em_injection": {
        "name": "EM Fault Injection (EMFI)",
        "desc": "Injection EM pour glitching — bypass secure boot, extrait clés crypto",
        "target": "Embedded systems, HSM, smart cards, MCU",
        "range_m": 0.05,
        "success_rate": 0.70,
        "required_hw": ["ChipWhisperer", "EM_probe", "oscilloscope"],
        "cvss_equiv": 9.0,
    },
    "gairoscope": {
        "name": "GAIROSCOPE — EM→Gyroscope",
        "desc": "Induit résonance gyroscope smartphone via signaux EM PC",
        "target": "Nearby smartphone within 8m",
        "range_m": 8,
        "success_rate": 0.50,
        "required_hw": ["none_software_only"],
        "cvss_equiv": 6.8,
        "bandwidth_bps": 8,
    },
}

_FREQUENCY_BANDS = {
    "VHF": (30e6, 300e6),
    "UHF": (300e6, 3e9),
    "HDMI_clock": (165e6, 600e6),
    "USB_2.0": (480e6, 480e6),
    "USB_3.0": (5e9, 5e9),
    "DDR4_clock": (1.6e9, 3.2e9),
}


def _simulate_spectrum_scan() -> List[Dict]:
    """Simuler scan spectre EM — détection sources."""
    leaks = []
    for name, (fmin, fmax) in _FREQUENCY_BANDS.items():
        if random.random() > 0.4:
            freq = random.uniform(fmin, fmax)
            leaks.append({
                "band": name,
                "frequency_mhz": round(freq / 1e6, 2),
                "signal_dbm": round(random.uniform(-80, -30), 1),
                "snr_db": round(random.uniform(5, 40), 1),
                "modulated": random.random() > 0.5,
                "data_recoverable": random.random() > 0.4,
            })
    return leaks


class EMInjectionService:
    """Van Eck / TEMPEST / EMFI — interception et injection EM."""

    def scan_em_spectrum(self, target_ip: str = "192.168.1.1",
                          duration_sec: int = 30) -> Dict:
        """Scanner spectre EM — détecter fuites electromagnétiques."""
        session_id = str(uuid.uuid4())
        leaks = _simulate_spectrum_scan()
        has_hackrf = os.path.exists("/dev/hackrf") or os.path.exists("/usr/bin/hackrf_info")

        result = {
            "session_id": session_id,
            "target": target_ip,
            "duration_sec": duration_sec,
            "hw_detected": "HackRF One" if has_hackrf else "none (simulation)",
            "simulated": not has_hackrf,
            "leakage_sources": leaks,
            "total_leaks": len(leaks),
            "exploitable_leaks": sum(1 for l in leaks if l["data_recoverable"]),
            "strongest_signal": max(leaks, key=lambda l: l["signal_dbm"])["band"] if leaks else None,
        }
        _SESSIONS[session_id] = result
        return result

    def van_eck_attack(self, target_distance_m: float = 5.0,
                        frequency_mhz: float = 165.0,
                        duration_sec: int = 60) -> Dict:
        """Van Eck phreaking — reconstruction écran via EM."""
        session_id = str(uuid.uuid4())
        info = _EM_TECHNIQUES["van_eck"]
        in_range = target_distance_m <= info["range_m"]
        success = in_range and random.random() < info["success_rate"]

        pixels_captured = random.randint(1920 * 600, 1920 * 1080) if success else 0
        output_path = None
        if success:
            output_path = str(_OUTPUT / f"van_eck_{session_id[:8]}.raw")
            with open(output_path, "wb") as f:
                f.write(os.urandom(min(pixels_captured * 3, 1024 * 1024)))

        result = {
            "session_id": session_id,
            "technique": "Van Eck Phreaking",
            "frequency_mhz": frequency_mhz,
            "distance_m": target_distance_m,
            "in_range": in_range,
            "success": success,
            "screen_resolution": "1920x1080" if success else None,
            "pixels_captured": pixels_captured,
            "output_path": output_path,
            "text_recovered": "login: admin\npassword: [RECOVERED]" if success else None,
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def tempest_keylog(self, duration_sec: int = 120,
                        antenna_gain_db: float = 12.0) -> Dict:
        """TEMPEST keyboard eavesdrop — keylogging EM passif."""
        session_id = str(uuid.uuid4())
        info = _EM_TECHNIQUES["tempest_keyboard"]
        success = random.random() < info["success_rate"]

        keystrokes = []
        if success:
            sample_keys = "ls -la /home/admin/secret\nssh root@10.0.0.1\npassword123\n"
            keystrokes = list(sample_keys)

        result = {
            "session_id": session_id,
            "technique": "TEMPEST Keyboard",
            "antenna_gain_db": antenna_gain_db,
            "duration_sec": duration_sec,
            "success": success,
            "keystrokes_captured": len(keystrokes),
            "reconstructed_text": "".join(keystrokes) if success else "",
            "confidence_pct": round(random.uniform(65, 95), 1) if success else 0,
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def em_fault_inject(self, target_device: str = "smartcard",
                         attack_type: str = "secure_boot_bypass") -> Dict:
        """EMFI — electromagnetic fault injection sur cible."""
        session_id = str(uuid.uuid4())
        info = _EM_TECHNIQUES["em_injection"]

        attack_results = {
            "secure_boot_bypass": {"success_prob": 0.65, "result": "Secure Boot bypassed — unsigned firmware loaded"},
            "key_extraction": {"success_prob": 0.55, "result": "AES-128 key recovered: 2b7e151628aed2a6abf7158809cf4f3c"},
            "privilege_escalation": {"success_prob": 0.70, "result": "ARM TrustZone bypassed — secure world accessible"},
            "rng_bias": {"success_prob": 0.80, "result": "RNG biased — ECDSA nonce predictable → key recovery"},
        }
        atk = attack_results.get(attack_type, attack_results["secure_boot_bypass"])
        success = random.random() < atk["success_prob"]

        result = {
            "session_id": session_id,
            "technique": "EM Fault Injection",
            "target_device": target_device,
            "attack_type": attack_type,
            "probe_distance_mm": round(random.uniform(0.5, 5.0), 1),
            "pulse_voltage_v": round(random.uniform(50, 200), 0),
            "success": success,
            "result": atk["result"] if success else "Injection failed — missed timing window",
            "attempts": random.randint(1, 50) if success else random.randint(50, 500),
            "cvss_equiv": info["cvss_equiv"],
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def odini_covert_channel(self, mode: str = "transmit",
                              data: str = "SECRET",
                              receiver_device: str = "smartphone") -> Dict:
        """ODINI — exfiltrer données via EM des têtes de disque dur."""
        session_id = str(uuid.uuid4())
        info = _EM_TECHNIQUES["odini"]
        bw = info["bandwidth_bps"]
        duration = len(data) * 8 / bw  # bits / bps

        result = {
            "session_id": session_id,
            "technique": "ODINI HDD EM Channel",
            "mode": mode,
            "data_size_bits": len(data) * 8,
            "bandwidth_bps": bw,
            "estimated_duration_sec": round(duration, 1),
            "receiver": receiver_device,
            "success": random.random() < info["success_rate"],
            "frequency_hz": 100,
            "range_m": info["range_m"],
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def list_techniques(self) -> List[Dict]:
        return [
            {
                "id": k, "name": v["name"], "description": v["desc"],
                "range_m": v["range_m"], "success_rate": v["success_rate"],
                "required_hw": v["required_hw"], "cvss_equiv": v["cvss_equiv"],
            }
            for k, v in _EM_TECHNIQUES.items()
        ]

    def get_session(self, session_id: str) -> Dict:
        return _SESSIONS.get(session_id, {"error": "not found"})
