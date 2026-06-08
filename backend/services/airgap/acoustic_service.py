"""
Acoustic Covert Channels — Bloc 4 Air-Gap
Techniques : Laser microphone, MOSQUITO (ultrasonic exfil),
             FANSMITTER (ventilateur → acoustic), DISKFILTRATION (HDD seek noise)
             PowerHammer (power-line acoustic), AirHopper (FM audio)
"""
from __future__ import annotations

import logging
import os
import random
import struct
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/airgap/acoustic")

_ACOUSTIC_TECHNIQUES = {
    "laser_mic": {
        "name": "Laser Microphone",
        "desc": "Microphone laser — capture vibrations fenêtres/objets à distance",
        "range_m": 500,
        "bandwidth_hz": 20000,
        "success_rate": 0.82,
        "required_hw": ["laser_650nm", "photodetector", "lock_in_amplifier"],
        "stealthy": True,
        "cvss_equiv": 8.5,
    },
    "mosquito": {
        "name": "MOSQUITO — Ultrasonic Exfil",
        "desc": "Exfil via ultrasons entre haut-parleurs (TX) et casque/mic (RX)",
        "range_m": 9,
        "bandwidth_bps": 166,
        "success_rate": 0.75,
        "required_hw": ["speakers", "headphones_as_mic"],
        "stealthy": True,
        "cvss_equiv": 7.2,
    },
    "fansmitter": {
        "name": "FANSMITTER — CPU Fan Acoustic",
        "desc": "Moduler vitesse ventilateur CPU pour émettre données acoustiques",
        "range_m": 8,
        "bandwidth_bps": 15,
        "success_rate": 0.65,
        "required_hw": ["smartphone_microphone"],
        "stealthy": False,
        "cvss_equiv": 6.5,
    },
    "diskfiltration": {
        "name": "DiskFiltration — HDD Seek Noise",
        "desc": "Moduler mouvements tête HDD pour émettre acoustic covert channel",
        "range_m": 2,
        "bandwidth_bps": 180,
        "success_rate": 0.60,
        "required_hw": ["smartphone_microphone"],
        "stealthy": False,
        "cvss_equiv": 6.8,
    },
    "airhopper": {
        "name": "AirHopper — FM Acoustic Exfil",
        "desc": "GPU génère fréquences FM, reçu par radio FM smartphone",
        "range_m": 7,
        "bandwidth_bps": 100,
        "success_rate": 0.70,
        "required_hw": ["FM_radio_receiver", "smartphone"],
        "stealthy": True,
        "cvss_equiv": 7.0,
    },
    "powerhammer": {
        "name": "PowerHammer — Power Line",
        "desc": "Exfil via modulation consommation CPU → ligne électrique",
        "range_m": 1000,
        "bandwidth_bps": 10,
        "success_rate": 0.55,
        "required_hw": ["power_line_probe", "oscilloscope"],
        "stealthy": True,
        "cvss_equiv": 7.5,
    },
}


def _generate_wav_header(sample_rate: int = 44100, num_samples: int = 44100) -> bytes:
    """Générer header WAV minimal pour fichier audio simulé."""
    data_size = num_samples * 2
    return struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size,
    )


class AcousticService:
    """Acoustic covert channels — laser mic + ultrasonic + fan modulation."""

    def laser_mic_capture(self, target_surface: str = "window",
                           duration_sec: int = 60,
                           distance_m: float = 100.0) -> Dict:
        """Laser microphone — capture audio à distance via surface réfléchissante."""
        session_id = str(uuid.uuid4())
        info = _ACOUSTIC_TECHNIQUES["laser_mic"]
        in_range = distance_m <= info["range_m"]
        success = in_range and random.random() < info["success_rate"]

        audio_path = None
        if success:
            audio_path = str(_OUTPUT / f"laser_capture_{session_id[:8]}.wav")
            num_samples = duration_sec * 44100
            wav_header = _generate_wav_header(44100, num_samples)
            with open(audio_path, "wb") as f:
                f.write(wav_header)
                f.write(os.urandom(min(num_samples * 2, 512 * 1024)))

        return {
            "session_id": session_id,
            "technique": "Laser Microphone",
            "target_surface": target_surface,
            "distance_m": distance_m,
            "in_range": in_range,
            "success": success,
            "duration_sec": duration_sec,
            "audio_quality_db_snr": round(random.uniform(15, 40), 1) if success else 0,
            "audio_path": audio_path,
            "transcription": "Meeting at 14h tomorrow — use the server room key" if success else None,
            "simulated": True,
        }

    def mosquito_exfil(self, mode: str = "transmit",
                        data: str = "EXFIL_DATA",
                        frequency_khz: float = 18.0) -> Dict:
        """MOSQUITO — canal ultrasonic entre haut-parleurs et casque."""
        session_id = str(uuid.uuid4())
        info = _ACOUSTIC_TECHNIQUES["mosquito"]
        bw = info["bandwidth_bps"]
        duration = (len(data) * 8) / bw

        return {
            "session_id": session_id,
            "technique": "MOSQUITO Ultrasonic",
            "mode": mode,
            "frequency_khz": frequency_khz,
            "data_bytes": len(data),
            "estimated_duration_sec": round(duration, 1),
            "bandwidth_bps": bw,
            "range_m": info["range_m"],
            "success": random.random() < info["success_rate"],
            "decoded_data": data if mode == "receive" and random.random() < 0.7 else None,
            "undetectable_human": frequency_khz > 18.0,
            "simulated": True,
        }

    def fansmitter_exfil(self, data: str = "KEY:0xDEADBEEF",
                          fan_min_rpm: int = 1000,
                          fan_max_rpm: int = 3000) -> Dict:
        """FANSMITTER — moduler ventilateur CPU pour acoustic covert channel."""
        session_id = str(uuid.uuid4())
        info = _ACOUSTIC_TECHNIQUES["fansmitter"]
        duration = (len(data) * 8) / info["bandwidth_bps"]

        return {
            "session_id": session_id,
            "technique": "FANSMITTER",
            "data_bytes": len(data),
            "bandwidth_bps": info["bandwidth_bps"],
            "estimated_duration_sec": round(duration, 1),
            "fan_rpm_range": f"{fan_min_rpm}-{fan_max_rpm}",
            "frequency_hz": round((fan_min_rpm + fan_max_rpm) / 2 / 60, 1),
            "audible": True,
            "range_m": info["range_m"],
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def airhopper_exfil(self, data: str = "SECRET",
                         fm_freq_mhz: float = 107.5) -> Dict:
        """AirHopper — exfil via émissions FM générées par GPU."""
        session_id = str(uuid.uuid4())
        info = _ACOUSTIC_TECHNIQUES["airhopper"]
        duration = (len(data) * 8) / info["bandwidth_bps"]

        return {
            "session_id": session_id,
            "technique": "AirHopper FM Exfil",
            "fm_frequency_mhz": fm_freq_mhz,
            "data_bytes": len(data),
            "bandwidth_bps": info["bandwidth_bps"],
            "estimated_duration_sec": round(duration, 1),
            "range_m": info["range_m"],
            "receiver": "FM radio / smartphone tuner",
            "stealthy": True,
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def powerhammer_exfil(self, data: str = "AES_KEY",
                           circuit_type: str = "in_line") -> Dict:
        """PowerHammer — exfil via modulation consommation sur ligne électrique."""
        session_id = str(uuid.uuid4())
        info = _ACOUSTIC_TECHNIQUES["powerhammer"]
        duration = (len(data) * 8) / info["bandwidth_bps"]

        return {
            "session_id": session_id,
            "technique": "PowerHammer",
            "circuit_type": circuit_type,
            "data_bytes": len(data),
            "bandwidth_bps": info["bandwidth_bps"],
            "estimated_duration_sec": round(duration, 1),
            "range_m": info["range_m"],
            "undetectable": True,
            "success": random.random() < info["success_rate"],
            "simulated": True,
        }

    def list_techniques(self) -> List[Dict]:
        return [
            {
                "id": k, "name": v["name"], "description": v["desc"],
                "range_m": v["range_m"], "bandwidth_bps": v.get("bandwidth_bps"),
                "success_rate": v["success_rate"], "stealthy": v["stealthy"],
                "required_hw": v["required_hw"], "cvss_equiv": v["cvss_equiv"],
            }
            for k, v in _ACOUSTIC_TECHNIQUES.items()
        ]
